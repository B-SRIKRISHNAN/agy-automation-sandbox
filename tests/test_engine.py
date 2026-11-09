"""Tests for container engine detection and name sanitization."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.engine import derive_container_names, detect_container_engine, resolve_compose_cmd


class TestEngine(unittest.TestCase):

    def test_derive_container_names(self):
        cases = [
            (Path("/home/user/my-cool-project"), ("agy-sandbox-my-cool-project", "agy-sandbox:latest")),
            (Path("/home/user/My_Cool_Project!"), ("agy-sandbox-my_cool_project", "agy-sandbox:latest")),
            (Path("D:\\Workspaces\\Project.Alpha 2026"), ("agy-sandbox-project-alpha-2026", "agy-sandbox:latest")),
        ]
        for path_val, expected in cases:
            container_name, image_name = derive_container_names(path_val)
            self.assertEqual(container_name, expected[0])
            self.assertEqual(image_name, expected[1])

    def test_derive_container_names_with_worktree(self):
        target = Path("/home/user/my-app")
        container_name, image_name = derive_container_names(target, worktree_name="worktree-issue-42")
        self.assertEqual(container_name, "agy-sandbox-my-app-worktree-issue-42")
        self.assertEqual(image_name, "agy-sandbox:latest")

    def test_derive_container_names_with_custom_dockerfile(self, tmp_path_factory=None):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "custom-app"
            custom_docker = project_dir / ".agy" / "Dockerfile.sandbox"
            custom_docker.parent.mkdir(parents=True)
            custom_docker.write_text("FROM agy-sandbox:latest\n")

            container_name, image_name = derive_container_names(project_dir, worktree_name="worktree-test")
            self.assertEqual(container_name, "agy-sandbox-custom-app-worktree-test")
            self.assertEqual(image_name, "agy-sandbox-custom-app:latest")

    def test_resolve_compose_cmd_podman_and_docker(self):
        podman_cmd = resolve_compose_cmd("podman")
        self.assertTrue(len(podman_cmd) >= 1)
        self.assertTrue("podman" in podman_cmd[0] or "podman-compose" in podman_cmd[0])

        docker_cmd = resolve_compose_cmd("docker")
        self.assertTrue(len(docker_cmd) >= 1)
        self.assertTrue("docker" in docker_cmd[0] or "docker-compose" in docker_cmd[0])


if __name__ == "__main__":
    unittest.main()
