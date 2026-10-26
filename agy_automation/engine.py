"""Container engine detection, validation, and naming utilities."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def verify_agy_installed() -> str:
    """Verify that Antigravity CLI (agy) is installed and available in PATH."""
    agy_bin = shutil.which("agy")
    if not agy_bin:
        raise RuntimeError(
            "Antigravity CLI (agy) is not installed or not in your PATH.\n"
            "Please install agy to proceed: https://antigravity.google/cli"
        )
    return agy_bin


def derive_container_names(target_repo: Path) -> Tuple[str, str]:
    """Derive container and image name from target project directory."""
    # Handle both Windows backslashes and POSIX slashes portably
    normalized = str(target_repo).replace("\\", "/").rstrip("/")
    leaf_name = normalized.split("/")[-1] if "/" in normalized else normalized
    clean_name = re.sub(r"[^a-z0-9_-]", "-", leaf_name.lower()).strip("-")
    if not clean_name:
        clean_name = "project"
    container_name = f"{clean_name}-sandbox"
    image_name = f"{clean_name}-sandbox:latest"
    return container_name, image_name


def detect_container_engine(forced_engine: str = "auto") -> Tuple[str, str]:
    """Detect available container engine (Podman preferred, Docker fallback).

    Returns:
        Tuple of (engine_type, version_description) where engine_type is 'podman' or 'docker'.
    """
    engine_choice = forced_engine or os.environ.get("CONTAINER_ENGINE", "auto")
    engine_choice = engine_choice.lower()

    podman_path = shutil.which("podman")
    docker_path = shutil.which("docker")

    def get_version(bin_path: str) -> str:
        try:
            res = subprocess.run([bin_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "version unknown"

    if engine_choice == "docker":
        if not docker_path:
            raise RuntimeError("Docker engine requested, but 'docker' was not found in PATH.")
        return "docker", f"Docker ({get_version(docker_path)})"

    if engine_choice == "podman":
        if not podman_path:
            raise RuntimeError("Podman engine requested, but 'podman' was not found in PATH.")
        return "podman", f"Podman ({get_version(podman_path)})"

    if podman_path:
        return "podman", f"Podman ({get_version(podman_path)})"

    if docker_path:
        return "docker", f"Docker ({get_version(docker_path)})"

    raise RuntimeError(
        "Neither Podman nor Docker was found in your PATH.\n"
        "Please install Podman (e.g. sudo apt install podman podman-compose) or Docker to run the sandbox."
    )


def resolve_compose_cmd(engine_type: str) -> List[str]:
    """Resolve the compose invocation list for the detected engine."""
    if engine_type == "podman":
        # Check podman compose first
        podman_path = shutil.which("podman")
        if podman_path:
            res = subprocess.run([podman_path, "compose", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return [podman_path, "compose"]

        # Check podman-compose binary
        podman_compose_path = shutil.which("podman-compose")
        if podman_compose_path:
            return [podman_compose_path]

        return ["podman", "compose"]

    if engine_type == "docker":
        docker_path = shutil.which("docker")
        if docker_path:
            res = subprocess.run([docker_path, "compose", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return [docker_path, "compose"]

        docker_compose_path = shutil.which("docker-compose")
        if docker_compose_path:
            return [docker_compose_path]

        return ["docker", "compose"]

    return [engine_type, "compose"]
