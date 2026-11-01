# Deprecated Scripts

These host-level shell and PowerShell wrapper scripts have been deprecated.
All host-side orchestration is performed directly by the Python package `agy_automation` (via `start_issue.py` or the `agy-automation` CLI command).

Active scripts retained in `scripts/`:
- `container-agent-runner.sh`: Active in-container entrypoint mounted to `/runner/container-agent-runner.sh` inside Docker/Podman sandbox.
- `sandbox-mcp-config.json`: Active isolated MCP configuration mounted into the sandbox container.
