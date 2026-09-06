"""Tests for MCP server."""

import pytest
from fathom.mcp_server import FathomMCPServer


class TestMCPServer:
    """Test MCP tool registration."""

    def test_mcp_server_initialization(self):
        server = FathomMCPServer()
        assert server.client is not None
        assert server.active_profiles == {}

    def test_mcp_tool_registration(self):
        server = FathomMCPServer()
        tools = server.get_tools()

        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]

        assert "create_profile" in tool_names
        assert "add_fact" in tool_names
        assert "diagnose" in tool_names
        assert "export_report" in tool_names
        assert "get_skills" in tool_names

    def test_mcp_tool_schemas(self):
        server = FathomMCPServer()
        tools = server.get_tools()

        # Verify create_profile schema
        create_profile_tool = next(t for t in tools if t["name"] == "create_profile")
        assert "inputSchema" in create_profile_tool
        schema = create_profile_tool["inputSchema"]
        assert schema["properties"]["system_id"]["type"] == "string"

        # Verify diagnose schema
        diagnose_tool = next(t for t in tools if t["name"] == "diagnose")
        schema = diagnose_tool["inputSchema"]
        assert "system_id" in schema["properties"]
        assert "executor_behavior" in schema["properties"]
