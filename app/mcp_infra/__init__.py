# app/mcp_infra/__init__.py
# Modular MCP infrastructure layer
# Add new MCP servers by updating MCP/mcp_config.json only - no agent code changes needed.

from .registry import MCPRegistry
from .executor import MCPExecutor

__all__ = ["MCPRegistry", "MCPExecutor"]
