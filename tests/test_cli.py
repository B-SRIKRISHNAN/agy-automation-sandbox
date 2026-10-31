"""Tests for CLI parsing and flag normalization."""

import sys
import unittest
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agy_automation.cli import normalize_args, parse_cli_args


class TestCli(unittest.TestCase):

    def test_flag_normalization_single_dash_powershell(self):
        raw = ["42", "-Build", "-DryRun", "-Interactive", "-ContainerEngine", "docker"]
        normalized = normalize_args(raw)
        self.assertEqual(
            normalized,
            ["42", "--build", "--dry-run", "--interactive", "--engine", "docker"],
        )

    def test_flag_normalization_powershell_full_names(self):
        raw = ["-BuildSandbox", "-InteractiveSandbox", "-DryRun"]
        normalized = normalize_args(raw)
        self.assertEqual(normalized, ["--build", "--interactive", "--dry-run"])

    def test_flag_normalization_inline_engine(self):
        raw = ["-ContainerEngine=podman"]
        normalized = normalize_args(raw)
        self.assertEqual(normalized, ["--engine=podman"])

        raw2 = ["--containerengine=docker"]
        normalized2 = normalize_args(raw2)
        self.assertEqual(normalized2, ["--engine=docker"])

        raw3 = ["-engine=docker"]
        normalized3 = normalize_args(raw3)
        self.assertEqual(normalized3, ["--engine=docker"])

    def test_parse_cli_args_positional_and_flags(self):
        args = parse_cli_args(["42", "--build", "--dry-run", "--interactive", "--engine", "podman"])
        self.assertEqual(args.issue, 42)
        self.assertTrue(args.build)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.interactive)
        self.assertEqual(args.engine, "podman")

    def test_parse_cli_args_powershell_flags_end_to_end(self):
        args = parse_cli_args(["105", "-BuildSandbox", "-DryRun", "-ContainerEngine", "docker"])
        self.assertEqual(args.issue, 105)
        self.assertTrue(args.build)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.engine, "docker")

    def test_parse_cli_args_defaults(self):
        args = parse_cli_args([])
        self.assertEqual(args.issue, 0)
        self.assertEqual(args.session, "")
        self.assertFalse(args.build)
        self.assertFalse(args.interactive)
        self.assertFalse(args.dry_run)
        self.assertEqual(args.engine, "auto")

    def test_parse_cli_args_session_target(self):
        args = parse_cli_args(["refactor-auth", "--build"])
        self.assertEqual(args.issue, 0)
        self.assertEqual(args.session, "refactor-auth")
        self.assertTrue(args.build)

    def test_parse_cli_args_session_flag(self):
        args = parse_cli_args(["--session", "my-task", "--dry-run"])
        self.assertEqual(args.issue, 0)
        self.assertEqual(args.session, "my-task")
        self.assertTrue(args.dry_run)

    def test_parse_cli_args_hash_issue(self):
        args = parse_cli_args(["#99"])
        self.assertEqual(args.issue, 99)
        self.assertEqual(args.session, "")



if __name__ == "__main__":
    unittest.main()
