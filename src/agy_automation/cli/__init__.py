"""CLI package for agy-automation.

Provides subcommands, terminal formatting, user prompts, and argument parsing.
"""

from .formatters import Colors, format_stream_event_for_display, print_stream_line
from .main import main
from .parser import create_parser, normalize_args, parse_cli_args
from .prompts import prompt_issue_number, prompt_session_or_issue

__all__ = [
    "Colors",
    "create_parser",
    "format_stream_event_for_display",
    "main",
    "normalize_args",
    "parse_cli_args",
    "print_stream_line",
    "prompt_issue_number",
    "prompt_session_or_issue",
]
