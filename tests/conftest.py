"""Shared fixtures for the deckfile test suite."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def write(path: Path, content: str) -> Path:
    """Write *content* to *path*, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def write_yaml(path: Path, data: dict) -> Path:
    return write(path, yaml.safe_dump(data, sort_keys=False))


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """An empty project directory."""
    return tmp_path


@pytest.fixture
def make_project(project_dir: Path):
    """Build a project on disk and return the path to its deckfile."""

    def _make(project: dict | str, files: dict[str, str] | None = None) -> Path:
        deckfile = project_dir / "deckfile.yaml"
        if isinstance(project, str):
            write(deckfile, project)
        else:
            write_yaml(deckfile, project)
        for relative, content in (files or {}).items():
            write(project_dir / relative, content)
        return deckfile

    return _make
