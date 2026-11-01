"""Tests for sandbox terminal visibility, formatting, and stream event display."""

import io
import sys
import unittest
from unittest.mock import patch

from agy_automation.sandbox import format_stream_event_for_display, print_stream_line


class TestSandboxVisibility(unittest.TestCase):
    def test_format_tool_call_run_command(self):
        event = {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "ACTIVE",
                "tool_name": "run_command",
                "tool_info": {
                    "parameters": {"CommandLine": "ls -la /workspace"}
                },
            },
        }
        disp = format_stream_event_for_display(event)
        self.assertIsNotNone(disp)
        self.assertIn("[TOOL CALL]", disp)
        self.assertIn("run_command: ls -la /workspace", disp)

    def test_format_tool_call_file_operations(self):
        for tool in ("read_file", "view_file", "edit_file", "replace_file_content", "write_file", "write_to_file"):
            event = {
                "event": "step_update",
                "step_update": {
                    "step_type": "tool",
                    "state": "ACTIVE",
                    "tool_name": tool,
                    "tool_info": {
                        "parameters": {"Path": "/workspace/src/app.py"}
                    },
                },
            }
            disp = format_stream_event_for_display(event)
            self.assertIsNotNone(disp)
            self.assertIn("[TOOL CALL]", disp)
            self.assertIn(f"{tool}: /workspace/src/app.py", disp)

    def test_format_tool_call_manage_task(self):
        event_with_id = {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "ACTIVE",
                "tool_name": "manage_task",
                "tool_info": {
                    "parameters": {"Action": "status", "TaskId": "task-6"}
                },
            },
        }
        disp = format_stream_event_for_display(event_with_id)
        self.assertIn("manage_task: status task-6", disp)

        event_without_id = {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "ACTIVE",
                "tool_name": "manage_task",
                "tool_info": {
                    "parameters": {"Action": "list"}
                },
            },
        }
        disp2 = format_stream_event_for_display(event_without_id)
        self.assertIn("manage_task: list", disp2)

    def test_format_tool_call_search_web(self):
        event = {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "ACTIVE",
                "tool_name": "search_web",
                "tool_info": {
                    "parameters": {"query": "python subprocess devnull"}
                },
            },
        }
        disp = format_stream_event_for_display(event)
        self.assertIn("search_web: python subprocess devnull", disp)

    def test_format_tool_done_with_output(self):
        event = {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "DONE",
                "duration_seconds": 0.26,
                "tool_info": {
                    "output": "Command exited with code 0.\nExtra info..."
                },
            },
        }
        disp = format_stream_event_for_display(event)
        self.assertIn("[TOOL OUTPUT]", disp)
        self.assertIn("Command exited with code 0.", disp)
        self.assertIn("(0.26s)", disp)

    def test_format_agent_response_usage(self):
        event = {
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "duration_seconds": 3.37,
                "usage": {
                    "input_tokens": 11057,
                    "output_tokens": 64,
                    "total_tokens": 11121,
                },
            },
        }
        disp = format_stream_event_for_display(event)
        self.assertIn("[STEP USAGE]", disp)
        self.assertIn("11,121 tokens", disp)
        self.assertIn("in: 11,057, out: 64", disp)
        self.assertIn("in 3.37s", disp)

    def test_format_result(self):
        event = {
            "event": "result",
            "result": {
                "duration_seconds": 45.2,
                "num_turns": 8,
                "usage": {
                    "total_tokens": 54200,
                },
            },
        }
        disp = format_stream_event_for_display(event)
        self.assertIn("[AGENT RESULT]", disp)
        self.assertIn("45.2s", disp)
        self.assertIn("8 turns", disp)
        self.assertIn("54,200 total tokens", disp)

    def test_print_stream_line_carriage_return(self):
        captured = io.StringIO()
        with patch.object(sys, "stdout", captured):
            print_stream_line("Test Line")
        val = captured.getvalue()
        self.assertTrue(val.startswith("\r"))
        self.assertTrue(val.endswith("\n"))
        self.assertIn("Test Line", val)


if __name__ == "__main__":
    unittest.main()
