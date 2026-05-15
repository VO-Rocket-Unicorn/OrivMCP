import importlib


def register_all_tools():

    importlib.import_module("oriv_mcp.capabilities.tools")

    importlib.import_module("oriv_mcp.capabilities.prompts")

    importlib.import_module("oriv_mcp.capabilities.resources")
