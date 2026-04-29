# aeromcp/core/bootstrap.py

import importlib
import pkgutil


def _import_submodules(package_name: str) -> None:
    package = importlib.import_module(package_name)

    for _, module_name, _ in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        importlib.import_module(module_name)


def register_all() -> None:
    """
    Automatically import all capability modules so decorators execute.
    """

    _import_submodules("aeromcp.capabilities.tools")
    _import_submodules("aeromcp.capabilities.resources")
    _import_submodules("aeromcp.capabilities.prompts")
