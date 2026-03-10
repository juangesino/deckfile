"""Scaffold a new deckfile project."""

from __future__ import annotations

import shutil
from pathlib import Path


SCAFFOLD_DIR = Path(__file__).parent / "scaffold"


def init_project(target: Path) -> None:
    """Copy the scaffold template into *target*, creating directories as needed."""
    if (target / "deckfile.yaml").exists():
        raise FileExistsError(
            f"deckfile.yaml already exists in {target}. "
            "Remove it first or choose a different directory."
        )

    for src_path in sorted(SCAFFOLD_DIR.rglob("*")):
        rel = src_path.relative_to(SCAFFOLD_DIR)
        dest = target / rel

        if src_path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)

    # Ensure output dir exists
    (target / "output").mkdir(exist_ok=True)
    (target / "assets").mkdir(exist_ok=True)

    print(f"Initialized new deckfile project in {target.resolve()}")
    print()
    print("  Get started:")
    print(f"    cd {target}" if target != Path(".") else "")
    print("    deck build          # build all charts")
    print("    deck list           # list defined charts")
    print()
    print("  Edit deckfile.yaml to define your own charts.")
