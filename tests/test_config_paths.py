"""
Tests for fundfactory_core.config.paths path resolution.
"""
from fundfactory_core.config import paths


def test_project_root_is_dir(tmp_path):
    """PROJECT_ROOT must be a valid directory."""
    assert paths.PROJECT_ROOT.is_dir()


def test_resolve_path_relative_to_project_root(tmp_path, monkeypatch):
    """
    Passing a project-root-aware module's resolve_path with a relative path
    resolves it under PROJECT_ROOT, not under the current working directory.
    """
    # Create a subdir under the resolved PROJECT_ROOT to serve as db target
    db_subdir = paths.PROJECT_ROOT / "tmp_test_db_root"
    db_subdir.mkdir(exist_ok=True)

    relative = "test.db"
    resolved = paths.resolve_path(relative)

    # Path must be inside PROJECT_ROOT
    assert str(paths.PROJECT_ROOT) in str(resolved)
    assert resolved.name == "test.db"


def test_resolve_path_absolute(tmp_path):
    """Absolute paths are returned unchanged (resolved)."""
    abs_path = tmp_path / "abs_test.db"
    resolved = paths.resolve_path(str(abs_path))
    assert resolved == abs_path.resolve()


def test_resolve_path_str(tmp_path):
    """resolve_path_str returns a string form of the resolved path."""
    result = paths.resolve_path_str("data/test.db")
    assert isinstance(result, str)
    assert "test.db" in result
