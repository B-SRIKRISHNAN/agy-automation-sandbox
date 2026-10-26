"""Tests for container engine detection and name sanitization."""

import unittest
from pathlib import Path
from agy_automation.engine import derive_container_names, detect_container_engine, resolve_compose_cmd


class TestEngine(unittest.TestCase):

    def test_derive_container_names(self):
        cases = [
            (Path("/home/user/my-cool-project"), ("my-cool-project-sandbox", "my-cool-project-sandbox:latest")),
            (Path("/home/user/My_Cool_Project!"), ("my_cool_project-sandbox", "my_cool_project-sandbox:latest")),
            (Path("D:\\Workspaces\\Project.Alpha 2026"), ("project-alpha-2026-sandbox", "project-alpha-2026-sandbox:latest")),
        ]
        for path_val, expected in cases:
            container_name, image_name = derive_container_names(path_val)
            self.assertEqual(container_name, expected[0])
            self.assertEqual(image_name, expected[1])

    def test_resolve_compose_cmd_podman_and_docker(self):
        podman_cmd = resolve_compose_cmd("podman")
        self.assertTrue(len(podman_cmd) >= 1)
        self.assertTrue("podman" in podman_cmd[0] or "podman-compose" in podman_cmd[0])

        docker_cmd = resolve_compose_cmd("docker")
        self.assertTrue(len(docker_cmd) >= 1)
        self.assertTrue("docker" in docker_cmd[0] or "docker-compose" in docker_cmd[0])


if __name__ == "__main__":
    unittest.main()
