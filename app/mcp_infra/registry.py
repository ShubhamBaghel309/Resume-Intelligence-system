# app/mcp_infra/registry.py
"""
MCPRegistry - Universal server discovery & schema management.

Config-driven routing (mcp_config.json) + live schema discovery (tools/list).
Adding a new MCP server:
  1. Add entry to MCP/mcp_config.json  (script path + trigger keywords)
  2. Create the FastMCP server script  (tool signatures ARE the schema)
  That's it. No field lists or examples needed in config — the agent discovers them.
"""

import json
import os
from typing import Optional


class MCPRegistry:
    """
    Loads MCP/mcp_config.json and provides:
    - Intent matching (which server handles this query?)
    - Live tool schema discovery (connect to server → tools/list)
    - Derived field metadata (required fields, labels, examples — all from server)
    - Caching (schemas fetched once per server per session)

    Old approach: required_fields and field_examples lived in config.
    New approach: they come from the server's tool signatures automatically.
    """

    def __init__(self):
        # Config lives at project_root/MCP/mcp_config.json
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_path = os.path.join(project_root, "MCP", "mcp_config.json")

        with open(config_path, "r") as f:
            self._config = json.load(f)

        self._project_root = project_root
        # Cache: server_id → list of tool schema dicts from tools/list
        self._schema_cache: dict[str, list[dict]] = {}

    # ─── Intent Matching ─────────────────────────────────────────

    def match_intent(self, query: str) -> Optional[str]:
        """
        Check query against all registered server trigger keywords.
        Returns the matching server_id, or None if no server matches.
        """
        query_lower = query.lower()
        for server_id, config in self._config["servers"].items():
            for keyword in config.get("trigger_keywords", []):
                if keyword.lower() in query_lower:
                    return server_id
        return None

    # ─── Config Accessors ────────────────────────────────────────

    def get_server_config(self, server_id: str) -> dict:
        """Get full config dict for a server (from mcp_config.json)."""
        return self._config["servers"].get(server_id, {})

    def get_script_path(self, server_id: str) -> str:
        """Get the absolute path to the MCP server script."""
        config = self.get_server_config(server_id)
        relative_script = config.get("script", "")
        return os.path.join(self._project_root, relative_script)

    def list_servers(self) -> dict:
        """Return all registered servers."""
        return self._config["servers"]

    # ─── Live Schema Discovery ───────────────────────────────────

    def discover_tools(self, server_id: str) -> list[dict]:
        """
        Connect to the server and discover all its tools via tools/list.

        Returns list of tool schema dicts:
        [
          {
            "name": "send_interview_invite",
            "description": "Send personalized interview invitation...",
            "inputSchema": {
              "properties": {
                "resume_id": {"type": "string", "description": "..."},
                "job_role":  {"type": "string", "description": "..."},
                ...
              },
              "required": ["resume_id"]
            }
          }
        ]

        Results are cached per server_id — safe to call multiple times.
        """
        if server_id in self._schema_cache:
            return self._schema_cache[server_id]

        from .executor import MCPExecutor
        executor = MCPExecutor()
        script_path = self.get_script_path(server_id)

        tools = executor.list_tools(script_path)
        self._schema_cache[server_id] = tools

        if tools:
            tool_names = [t["name"] for t in tools]
            print(f"   🔍 Discovered {len(tools)} tool(s) from {server_id}: {tool_names}")
        else:
            print(f"   ⚠️  No tools discovered from {server_id}")

        return tools

    def get_tool_schema(self, server_id: str, tool_name: str = None) -> dict:
        """
        Get the schema for a specific tool on a server.

        If tool_name is None, returns the FIRST tool's schema
        (most servers expose just one tool).

        Returns:
            {"name": "...", "description": "...", "inputSchema": {...}}
            or {} if not found.
        """
        tools = self.discover_tools(server_id)
        if not tools:
            return {}
        if tool_name:
            return next((t for t in tools if t["name"] == tool_name), {})
        return tools[0]  # Default: first tool

    def get_tool_name(self, server_id: str) -> str:
        """
        Get the tool name from the live server (replaces config's 'tool_name').

        Falls back to config if discovery fails.
        """
        schema = self.get_tool_schema(server_id)
        if schema:
            return schema["name"]
        # Fallback to config (backward compatibility)
        return self.get_server_config(server_id).get("tool_name", "")

    # ─── Derived Field Metadata (from live schema) ───────────────

    def get_required_fields(self, server_id: str) -> list[str]:
        """
        Derive required fields from the server's tool inputSchema.

        Logic:
        1. Get all properties from inputSchema
        2. Exclude auto_fields (e.g., 'resume_id' — filled by the agent, not user)
        3. Exclude truly-optional fields (those with non-None defaults, e.g. tone="professional")
        4. Include fields with default=None — these are "server-validated required"
           (FastMCP uses `field: str | None = None` to allow server-side validation)
        5. Return the rest as "required from user"

        This replaces the hardcoded "required_fields" list in the old config.
        """
        schema = self.get_tool_schema(server_id)
        if not schema:
            return self.get_server_config(server_id).get("required_fields", [])

        input_schema = schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        # Fields the agent fills automatically (not asked from user)
        auto_fields = set(self.get_server_config(server_id).get("auto_fields", []))

        user_fields = []
        for field_name, field_schema in properties.items():
            if field_name in auto_fields:
                continue
            # If the field has a non-None default, it's truly optional (e.g. tone="professional")
            # But default=None means the server validates it — treat as required
            if "default" in field_schema and field_schema["default"] is not None:
                continue
            user_fields.append(field_name)

        return user_fields

    def get_field_examples(self, server_id: str) -> dict:
        """
        Derive field labels and examples from the server's tool inputSchema.

        parses each field's JSON Schema 'description' to extract label + example.
        E.g., description = "Position they're being interviewed for (e.g., 'Senior Python Developer')"
             → label = "Job Role" (from field name), example = "e.g., 'Senior Python Developer'"

        Returns:
            {field_name: {"label": "...", "example": "..."}}

        This replaces the hardcoded "field_examples" dict in the old config.
        """
        schema = self.get_tool_schema(server_id)
        if not schema:
            return self.get_server_config(server_id).get("field_examples", {})

        input_schema = schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required_fields = self.get_required_fields(server_id)

        field_meta = {}
        for field_name in required_fields:
            prop = properties.get(field_name, {})
            description = prop.get("description", "")

            # Derive label from field name: "interview_datetime" → "Interview Datetime"
            label = field_name.replace("_", " ").title()

            # Extract example from description if it contains (e.g., ...) or similar
            example = ""
            if description:
                # Look for example patterns in the description
                import re
                # Pattern: (e.g., "something") or (e.g., 'something')
                eg_match = re.search(r'\(e\.g\.\s*[,:]?\s*(.+?)\)$', description)
                if eg_match:
                    example = f"e.g., {eg_match.group(1).strip()}"
                else:
                    # Use the whole description as a hint
                    example = description

            field_meta[field_name] = {
                "label": label,
                "example": example,
            }

        return field_meta
