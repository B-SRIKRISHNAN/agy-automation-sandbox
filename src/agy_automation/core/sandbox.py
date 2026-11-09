"""Container sandbox lifecycle, builds, and execution for agy-automation."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import Colors, find_agent_instructions, get_target_repo, get_toolkit_root
from .engine import derive_container_names, detect_container_engine, resolve_compose_cmd
from .git import run_git, worktree_repair


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
"""
    with open(config_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"{Colors.GREEN}[OK] Using Git sandbox configuration: {config_file}{Colors.RESET}")
    return config_file


def print_stream_line(text: str) -> None:
    """Print a terminal line with an explicit carriage return and immediate flush."""
    sys.stdout.write(f"\r{text}\n")
    sys.stdout.flush()


def format_stream_event_for_display(parsed: Dict[str, Any]) -> Optional[str]:
    """Format an agy NDJSON event into a concise, human-readable terminal line."""
    evt = parsed.get("event")
    if evt == "step_update":
        su = parsed.get("step_update") or {}
        stype = su.get("step_type")
        if stype == "tool":
            state = su.get("state")
            tool_name = su.get("tool_name", "")
            tinfo = su.get("tool_info") or {}
            params = tinfo.get("parameters") or {}
            if state == "ACTIVE":
                if tool_name == "run_command":
                    cmd = params.get("CommandLine") or params.get("command") or ""
                    return f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} run_command: {cmd}"
                elif tool_name in ("view_file", "read_file", "write_to_file", "write_file", "replace_file_content", "edit_file"):
                    path = params.get("Path") or params.get("path") or ""
                    return f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} {tool_name}: {path}"
                elif tool_name == "manage_task":
                    action = params.get("Action") or params.get("action") or ""
                    task_id = params.get("TaskId") or params.get("taskId") or ""
                    task_suffix = f" {task_id}" if task_id else ""
                    return f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} manage_task: {action}{task_suffix}" if action else f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} manage_task"
                elif tool_name == "search_web":
                    query = params.get("query") or ""
                    return f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} search_web: {query}" if query else f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} search_web"
                else:
                    return f"{Colors.YELLOW}[TOOL CALL]{Colors.RESET} {tool_name}"
            elif state == "DONE":
                out = tinfo.get("output", "")
                dur = su.get("duration_seconds")
                dur_str = f" ({dur:.2f}s)" if dur is not None else ""
                if out:
                    first_line = out.strip().splitlines()[0] if out.strip() else ""
                    if len(first_line) > 100:
                        first_line = first_line[:97] + "..."
                    return f"{Colors.GRAY}[TOOL OUTPUT]{Colors.RESET} {first_line}{dur_str}"
                return f"{Colors.GRAY}[TOOL DONE]{Colors.RESET}{dur_str}"
        elif stype == "agent_response":
            usage = su.get("usage") or {}
            if usage:
                in_tok = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                tot_tok = usage.get("total_tokens", 0)
                dur = su.get("duration_seconds")
                dur_str = f" in {dur:.2f}s" if dur is not None else ""
                return f"{Colors.CYAN}[STEP USAGE]{Colors.RESET} {tot_tok:,} tokens (in: {in_tok:,}, out: {out_tok:,}){dur_str}"
    elif evt == "result":
        res = parsed.get("result") or {}
        usage = res.get("usage") or {}
        tot_tok = usage.get("total_tokens", 0)
        turns = res.get("num_turns", 0)
        dur = res.get("duration_seconds", 0)
        return f"{Colors.GREEN}[AGENT RESULT]{Colors.RESET} Completed in {dur:.1f}s ({turns} turns, {tot_tok:,} total tokens)"
    return None


def run_sandbox(
    worktree_name: str = "",
    issue_file: str = "",
    target_repo: Optional[Path] = None,
    instructions_file: str = "",
    build: bool = False,
    interactive: bool = False,
    container_engine: str = "auto",
    session_logger: Optional[Any] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """Build and launch the container sandbox environment in automated or interactive mode."""
    toolkit_root = get_toolkit_root()
    if target_repo is None:
        target_repo = get_target_repo()

    container_name, image_name = derive_container_names(target_repo, worktree_name=worktree_name or "")
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
    custom_dockerfile = target_repo / ".agy" / "Dockerfile.sandbox"
    if custom_dockerfile.is_file():
        env["SANDBOX_DOCKERFILE"] = str(custom_dockerfile)
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
    if worktree_name:
        worktree_container_path = f"/workspace/.worktrees/{worktree_name}"
        if interactive:
            print(f"\n{Colors.CYAN}[INFO] Launching interactive permissionless sandbox session in: {worktree_container_path}{Colors.RESET}")
        else:
            print(f"\n{Colors.CYAN}[INFO] Starting automated agent scoped to: {worktree_container_path}{Colors.RESET}")

        issue_arg = issue_file.replace("\\", "/") if issue_file else f".worktrees/{worktree_name}/ISSUE_CONTEXT.md"

        resolved_instr = instructions_file
        if not resolved_instr:
            _, resolved_instr = find_agent_instructions(target_repo)

        runner_args = ["run"]
        if not interactive:
            runner_args.append("-T")
        runner_args.extend([
            "--name",
            container_name,
            "--rm",
            "-w",
            worktree_container_path,
            "sandbox",
            "bash",
            "/runner/container-agent-runner.sh",
            worktree_name,
            issue_arg,
        ])
        if resolved_instr:
            runner_args.append(resolved_instr.replace("\\", "/"))
        if interactive:
            runner_args.append("--interactive")

        run_cmd = build_compose_invocation(runner_args)

        if session_logger:
            session_logger.log_event("coordinator", "sandbox", "container_launching", {
                "container_name": container_name,
                "worktree": worktree_name,
                "interactive": interactive,
            })

        if not interactive and session_logger:
            try:
                proc = subprocess.Popen(
                    run_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        line_s = line.strip()
                        if not line_s:
                            continue
                        if stream_callback:
                            stream_callback(line_s)
                        if line_s.startswith("{") and line_s.endswith("}"):
                            parsed = session_logger.log_raw_agent_event(line_s)
                            if parsed:
                                disp = format_stream_event_for_display(parsed)
                                if disp:
                                    print_stream_line(disp)
                        else:
                            session_logger.log_event("container", "sandbox", "stdout", {"message": line_s})
                            print_stream_line(f"{Colors.GRAY}{line_s}{Colors.RESET}")

                    proc.stdout.close()
                proc.wait()
                exit_code = proc.returncode
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}[ABORT] User cancelled execution. Terminating sandbox container...{Colors.RESET}")
                session_logger.log_event("coordinator", "sandbox", "user_abort", {
                    "reason": "Process cancelled by user (SIGINT/KeyboardInterrupt)"
                })
                if engine_bin:
                    subprocess.run([engine_bin, "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                raise
        else:
            run_res = subprocess.run(run_cmd, env=env)
            exit_code = run_res.returncode

        worktree_host_dir = target_repo / ".worktrees" / worktree_name
        if worktree_host_dir.is_dir():
            worktree_repair(target_repo, worktree_host_dir)

        if exit_code != 0:
            if session_logger:
                session_logger.log_event("container", "sandbox", "container_terminated", {
                    "exit_code": exit_code,
                    "reason": f"Agent container exited with error code {exit_code}",
                })
            print(f"{Colors.RED}[ERROR] Agent container exited with error code {exit_code}.{Colors.RESET}")
            return exit_code

        if session_logger:
            session_logger.log_event("coordinator", "sandbox", "container_finished", {
                "exit_code": 0
            })
        print(f"{Colors.GREEN}[OK] Sandbox container session finished successfully.{Colors.RESET}")
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
        run_cmd = build_compose_invocation(["run", "--name", container_name, "--rm", "sandbox", "bash"])
        run_res = subprocess.run(run_cmd, env=env)
        return run_res.returncode


def main() -> int:
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
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
