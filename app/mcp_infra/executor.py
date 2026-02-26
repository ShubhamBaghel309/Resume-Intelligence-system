# app/mcp_infra/executor.py
"""
MCPExecutor - Universal MCP client.

Connects to any MCP server and:
  1. Discovers tools + schemas via `tools/list`  (list_tools)
  2. Executes tool calls                         (execute)

Completely server-agnostic: just needs a script_path.
Handles asyncio correctly whether called from sync or async context (Streamlit-safe).
"""

import asyncio
import json
import os
import shutil
from typing import Any


class MCPExecutor:
    """
    Universal MCP client — connects to any FastMCP server via stdio transport.

    Usage:
        executor = MCPExecutor()

        # Discover tools (like Claude Desktop does)
        tools = executor.list_tools("/abs/path/to/server.py")
        # → [{"name": "send_interview_invite",
        #      "description": "...",
        #      "inputSchema": {"properties": {...}, "required": [...]}}]

        # Execute a tool
        response = executor.execute(
            script_path="/abs/path/to/server.py",
            tool_name="send_interview_invite",
            params={"job_role": "ML Intern", ...}
        )
    """

    def __init__(self):
        # Locate project root (this file → mcp_infra → app → project_root)
        self._project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    # ─── helpers ─────────────────────────────────────────────────
    def _run_async(self, coro):
        """Run an async coroutine safely from sync context (Streamlit-safe)."""
        try:
            asyncio.get_running_loop()
            # Running inside Streamlit / Jupyter — spawn a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        except RuntimeError:
            return asyncio.run(coro)

    def _get_server_params(self, script_path: str):
        """Build StdioServerParameters for the given FastMCP script."""
        from mcp import StdioServerParameters

        fastmcp_cmd = shutil.which("fastmcp")
        if not fastmcp_cmd:
            venv_fastmcp = os.path.join(self._project_root, "myenv311", "Scripts", "fastmcp.exe")
            if os.path.exists(venv_fastmcp):
                fastmcp_cmd = venv_fastmcp
            else:
                raise FileNotFoundError("fastmcp not found. Run: pip install fastmcp")

        return StdioServerParameters(
            command=fastmcp_cmd,
            args=["run", script_path],
            env=None,
        )

    # ─── list_tools (universal discovery) ────────────────────────
    def list_tools(self, script_path: str) -> list[dict]:
        """
        Discover all tools exposed by an MCP server — the universal way.

        Connects to the server, calls `tools/list`, and returns a list of
        tool schema dicts, each with:
          - name: str
          - description: str
          - inputSchema: dict  (JSON Schema with properties, required, etc.)

        This is the same protocol Claude Desktop uses.  Adding a new tool to
        a server requires ZERO config changes — the agent discovers it at
        runtime.

        Returns:
            List of tool schema dicts, or [] on error.
        """
        try:
            return self._run_async(self._list_tools_async(script_path))
        except Exception as e:
            print(f"   ⚠️  list_tools error: {e}")
            return []

    async def _list_tools_async(self, script_path: str) -> list[dict]:
        """Async helper: connect to server and call tools/list."""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        server_params = self._get_server_params(script_path)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()

                tools = []
                for tool in response.tools:
                    tools.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    })
                return tools

    # ─── execute (tool call) ─────────────────────────────────────
    def execute(self, script_path: str, tool_name: str, params: dict) -> dict:
        """
        Execute a tool call on the specified MCP server script.

        Args:
            script_path: Absolute path to the FastMCP server .py file
            tool_name: Name of the tool to call (as registered with @mcp.tool())
            params: Dict of parameters to pass. None values are stripped.

        Returns:
            Standardized response dict with at least a 'status' key:
            - {"status": "success", "message": "...", ...}
            - {"status": "missing_fields", "missing_fields": [...], "message": "..."}
            - {"status": "error", "message": "..."}
        """
        try:
            return self._run_async(self._call_tool(script_path, tool_name, params))
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _call_tool(self, script_path: str, tool_name: str, params: dict) -> dict:
        """Async helper: opens stdio connection to MCP server and calls the tool."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client
        except ImportError:
            return {"status": "error", "message": "MCP library not installed. Run: pip install mcp"}

        server_params = self._get_server_params(script_path)

        # Strip None values before sending to server
        clean_params = {k: v for k, v in params.items() if v is not None}

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, arguments=clean_params)

                    if result.content:
                        raw_text = result.content[0].text
                        try:
                            return json.loads(raw_text)
                        except json.JSONDecodeError:
                            # Server returned plain text - treat as success message
                            return {"status": "success", "message": raw_text}

                    return {"status": "error", "message": "No result returned from MCP server"}

        except Exception as e:
            return {"status": "error", "message": f"MCP communication error: {str(e)}"}
