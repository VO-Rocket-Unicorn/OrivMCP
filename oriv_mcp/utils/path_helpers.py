import toml
from pathlib import Path
from typing import Optional


def ensure_path_exists(path: Path, is_file: bool = False) -> Path:
    """
    Ensure that the given path exists. If `is_file=True`, it ensures that
    all parent directories exist and creates an empty file if needed.

    Args:
        path (Path): The directory or file path to check/create.
        is_file (bool): Whether the path represents a file.

    Returns:
        Path: The resolved absolute path.
    """
    path = Path(path).expanduser().resolve()

    if is_file:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()
    else:
        path.mkdir(parents=True, exist_ok=True)

    return path


def get_repo_root() -> Path:
    """
    Walk up from this file's location to find the main repository root
    containing pyproject.toml. Ignores pyproject.toml files in subtrees like lib_oriv_tools.
    """
    repo_root = Path(__file__).resolve()
    while repo_root != repo_root.parent:
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            # Optional: ignore known subtrees
            if "lib_oriv_tools" not in str(repo_root):
                return repo_root
        repo_root = repo_root.parent
    raise RuntimeError("Cannot find main pyproject.toml in any parent directory.")


def get_package_name(source_root: Optional[str] = None) -> str:
    """
    Detect the main Python package name in a project.

    It first tries to read the project name from pyproject.toml,
    then verifies that a corresponding package folder exists with an __init__.py.
    If no pyproject.toml name is found, it falls back to scanning the source directory
    for a single package folder containing an __init__.py.

    Args:
        source_root (Optional[str]): Relative path from project root to the source directory
                                     (e.g., "src"). Defaults to None.

    Returns:
        str: The name of the Python package (underscores instead of dashes).

    Raises:
        RuntimeError: If no valid package folder is found or multiple candidates exist.
    """
    current_dir = Path(__file__).parent
    project_root = current_dir.parent

    project_root = get_repo_root()

    # Determine the root directory to scan for packages
    root = project_root
    if source_root:
        root = project_root / source_root
        if not root.exists():
            root = project_root

    # Attempt to read project name from pyproject.toml
    pyproject_path = project_root / "pyproject.toml"
    project_name: str = ""
    if pyproject_path.exists():
        pyproject_data = toml.load(pyproject_path)

        if "project" in pyproject_data and "name" in pyproject_data["project"]:
            project_name = pyproject_data["project"]["name"]
        elif "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
            project_name = pyproject_data["tool"]["poetry"].get("name", "")

    # If project name found, normalize and verify folder exists
    if project_name:
        normalized_pkg_name = project_name.replace("-", "_")
        candidate = root / normalized_pkg_name
        if candidate.is_dir() and (candidate / "__init__.py").exists():
            return normalized_pkg_name

    # Fallback: scan for folders with __init__.py
    candidates = [
        p.name for p in root.iterdir() if p.is_dir() and (p / "__init__.py").exists()
    ]

    if not candidates:
        raise RuntimeError(f"No package folder with __init__.py found in {root}")

    if len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        f"Multiple package folders found in {root}: {candidates}. "
        "Please specify source_root explicitly or set project name correctly."
    )
