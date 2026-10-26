"""Container sandbox lifecycle, builds, and execution."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .config import Colors, find_agent_instructions, get_target_repo, get_toolkit_root
from .engine import derive_container_names, detect_container_engine, resolve_compose_cmd
from .git_utils import run_git, worktree_repair


def get_gemini_credentials_path() -> Path:
    """Get the host Antigravity credentials directory (~/.gemini or %USERPROFILE%\\.gemini)."""
    if sys.platform == "win32" and "USERPROFILE" in os.environ:
        gemini_dir = Path(os.environ["USERPROFILE"]) / ".gemini"
    else:
        gemini_dir = Path.home() / ".gemini"

    if not gemini_dir.is_dir():
        print(f"{Colors.CYAN}[INFO] Creating host credentials directory at: {gemini_dir}{Colors.RESET}")
        gemini_dir.mkdir(parents=True, exist_ok=True)
    else:
        print(f"{Colors.GREEN}[OK] Found host Antigravity credentials: {gemini_dir}{Colors.RESET}")

    return gemini_dir


def ensure_gitconfig_sandbox(toolkit_root: Path) -> Path:
    """Ensure .gitconfig.sandbox exists in toolkit root with host identity and LF line endings."""
    config_file = toolkit_root / ".gitconfig.sandbox"
    if config_file.is_file():
        print(f"{Colors.GREEN}[OK] Using Git sandbox configuration: {config_file}{Colors.RESET}")
        return config_file

    host_user = ""
    host_email = ""
    res_user = run_git(["config", "user.name"])
    if res_user.returncode == 0 and res_user.stdout.strip():
        host_user = res_user.stdout.strip()
    else:
        host_user = os.environ.get("USER", os.environ.get("USERNAME", "developer"))

    res_email = run_git(["config", "user.email"])
    if res_email.returncode == 0 and res_email.stdout.strip():
        host_email = res_email.stdout.strip()
    else:
        host_email = f"{host_user}@localhost"

    print(f"{Colors.CYAN}[INFO] Generating default .gitconfig.sandbox from host identity: {host_user} <{host_email}>...{Colors.RESET}")
    content = f"""[user]
    name = {host_user}
    email = {host_email}

[safe]
    directory = *

[core]
    autocrlf = input
    fileMode = false
    preloadindex = true
    fscache = true
    untrackedCache = true

[worktree]
    useRelativePaths = true
"""
    with open(config_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"{Colors.GREEN}[OK] Using Git sandbox configuration: {config_file}{Colors.RESET}")
    return config_file


def run_sandbox(
    worktree_name: str = "",
    issue_file: str = "",
    target_repo: Optional[Path] = None,
    instructions_file: str = "",
    build: bool = False,
    interactive: bool = False,
    container_engine: str = "auto",
) -> int:
    """Build and launch the container sandbox environment in automated or interactive mode."""
    toolkit_root = get_toolkit_root()
    if target_repo is None:
        target_repo = get_target_repo()

    container_name, image_name = derive_container_names(target_repo)
    engine_type, engine_desc = detect_container_engine(container_engine)
    compose_base = resolve_compose_cmd(engine_type)

    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GREEN}   Container Sandbox Runner                               {Colors.RESET}")
    print(f"{Colors.CYAN}=========================================================={Colors.RESET}")
    print(f"{Colors.GRAY}Toolkit Root      : {toolkit_root}{Colors.RESET}")
    print(f"{Colors.GRAY}Target Repository : {target_repo}{Colors.RESET}")
    print(f"{Colors.GRAY}Container Name    : {container_name}{Colors.RESET}")
    print(f"{Colors.GRAY}Image Name        : {image_name}{Colors.RESET}")
    print(f"{Colors.GREEN}[INFO] Using container engine: {engine_desc}{Colors.RESET}")

    gemini_path = get_gemini_credentials_path()
    ensure_gitconfig_sandbox(toolkit_root)

    # Compose environment mapping
    env = os.environ.copy()
    env["TOOLKIT_DIR"] = str(toolkit_root)
    env["TARGET_REPO"] = str(target_repo)
    env["SANDBOX_CONTAINER"] = container_name
    env["SANDBOX_IMAGE"] = image_name
    env["GEMINI_PATH"] = str(gemini_path).replace("\\", "/")
    env["CONTAINER_ENGINE"] = engine_type

    compose_file = toolkit_root / "docker-compose.sandbox.yml"
    if not compose_file.is_file():
        raise RuntimeError(f"Missing docker-compose.sandbox.yml in toolkit root: {compose_file}")

    def build_compose_invocation(extra_args: List[str]) -> List[str]:
        cmd = list(compose_base)
        cmd.extend(["-f", str(compose_file)])
        if engine_type == "docker" and "compose" in compose_base:
            cmd.extend(["--project-directory", str(toolkit_root)])
        cmd.extend(extra_args)
        return cmd

    # Check if sandbox image exists
    engine_bin = shutil.which(engine_type)
    image_exists = False
    if engine_bin:
        res = subprocess.run(
            [engine_bin, "images", "-q", image_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            image_exists = True

    if build or not image_exists:
        if not image_exists and not build:
            print(f"\n{Colors.CYAN}[INFO] Sandbox image ({image_name}) not found. Building for first-time use...{Colors.RESET}")
        else:
            print(f"\n{Colors.CYAN}[INFO] Building sandbox image ({image_name})...{Colors.RESET}")

        build_cmd = build_compose_invocation(["build", "sandbox"])
        # Live streaming without capture_output
        build_res = subprocess.run(build_cmd, env=env)
        if build_res.returncode != 0:
            print(f"{Colors.RED}[ERROR] Container build failed with exit code {build_res.returncode}.{Colors.RESET}")
            return build_res.returncode

    # Clean up existing container with identical name if present
    if engine_bin:
        res = subprocess.run(
            [engine_bin, "ps", "-a", "-q", "--filter", f"name=^/{container_name}$"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            subprocess.run([engine_bin, "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Automated Mode vs Interactive Mode
    if worktree_name and not interactive:
        worktree_container_path = f"/workspace/.worktrees/{worktree_name}"
        print(f"\n{Colors.CYAN}[INFO] Starting automated agent scoped to: {worktree_container_path}{Colors.RESET}")

        issue_arg = issue_file.replace("\\", "/") if issue_file else f".worktrees/{worktree_name}/ISSUE_CONTEXT.md"

        # Resolve instructions file if not explicitly supplied
        resolved_instr = instructions_file
        if not resolved_instr:
            _, resolved_instr = find_agent_instructions(target_repo)

        runner_args = [
            "run",
            "--rm",
            "-w",
            worktree_container_path,
            "sandbox",
            "bash",
            "/runner/container-agent-runner.sh",
            worktree_name,
            issue_arg,
        ]
        if resolved_instr:
            runner_args.append(resolved_instr.replace("\\", "/"))

        run_cmd = build_compose_invocation(runner_args)

        # Execute container run with DIRECT terminal I/O (no capture_output) for live streaming
        run_res = subprocess.run(run_cmd, env=env)
        exit_code = run_res.returncode

        # Post-run: repair worktree on host
        worktree_host_dir = target_repo / ".worktrees" / worktree_name
        if worktree_host_dir.is_dir():
            worktree_repair(target_repo, worktree_host_dir)

        if exit_code != 0:
            print(f"{Colors.RED}[ERROR] Agent container exited with error code {exit_code}.{Colors.RESET}")
            return exit_code

        print(f"{Colors.GREEN}[OK] Sandbox container run finished successfully.{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.GRAY}----------------------------------------------------------{Colors.RESET}")
        print(f"{Colors.YELLOW}Tips inside the container:{Colors.RESET}")
        print(f"{Colors.GRAY}  1. Test agy CLI:         agy --version{Colors.RESET}")
        print(f"{Colors.GRAY}  2. Start agy agent:      agy{Colors.RESET}")
        print(f"{Colors.GRAY}  3. Fix cross-OS paths:   git worktree repair{Colors.RESET}")
        print(f"{Colors.GRAY}  4. List worktrees:       git worktree list{Colors.RESET}")
        print(f"{Colors.GRAY}----------------------------------------------------------\n{Colors.RESET}")

        print(f"{Colors.CYAN}[INFO] Entering sandbox container shell (exit or Ctrl+D to leave)...{Colors.RESET}")
        run_cmd = build_compose_invocation(["run", "--rm", "sandbox", "bash"])
        run_res = subprocess.run(run_cmd, env=env)
        return run_res.returncode


def main():
    """Standalone run-sandbox CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Container Sandbox Runner")
    parser.add_argument("-WorktreeName", "--worktree-name", dest="worktree_name", default="")
    parser.add_argument("-IssueFile", "--issue-file", dest="issue_file", default="")
    parser.add_argument("-TargetRepo", "--target-repo", dest="target_repo", default="")
    parser.add_argument("-InstructionsFile", "--instructions-file", dest="instructions_file", default="")
    parser.add_argument("-Build", "--build", dest="build", action="store_true")
    parser.add_argument("-Interactive", "--interactive", dest="interactive", action="store_true")

    args = parser.parse_args()
    repo_path = Path(args.target_repo).resolve() if args.target_repo else None

    exit_code = run_sandbox(
        worktree_name=args.worktree_name,
        issue_file=args.issue_file,
        target_repo=repo_path,
        instructions_file=args.instructions_file,
        build=args.build,
        interactive=args.interactive,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
