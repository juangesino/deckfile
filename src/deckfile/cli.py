"""CLI entry point for deckfile.

Usage:
    deck build                       # Build all charts from deckfile.yaml
    deck build myconfig.yaml         # Build from a specific file
    deck build -s monthly_calls      # Build only selected chart(s)
    deck list                        # List all charts in deckfile.yaml
    deck docs                        # Print the README documentation
"""

from __future__ import annotations

import argparse
import importlib.resources
import sys
import traceback
from pathlib import Path

DEFAULT_CONFIG = "deckfile.yaml"


def find_config(explicit: str | None = None) -> str:
    """Resolve the config file path."""
    if explicit:
        p = Path(explicit)
        if not p.exists():
            print(f"Error: config file not found: {explicit}")
            sys.exit(1)
        return str(p)

    if Path(DEFAULT_CONFIG).exists():
        return DEFAULT_CONFIG

    print(f"Error: no {DEFAULT_CONFIG} found in current directory.")
    print("Specify a path: deck build <path>")
    sys.exit(1)


def cmd_docs(args: argparse.Namespace) -> None:
    # In editable installs the force-included README may not exist inside the
    # package directory, so fall back to the repo root.
    pkg_readme = importlib.resources.files("deckfile").joinpath("README.md")
    try:
        text = pkg_readme.read_text(encoding="utf-8")
    except FileNotFoundError:
        repo_readme = Path(__file__).resolve().parents[2] / "README.md"
        if not repo_readme.exists():
            print("README.md not found.")
            sys.exit(1)
        text = repo_readme.read_text(encoding="utf-8")
    print(text)


def cmd_init(args: argparse.Namespace) -> None:
    from .init import init_project

    target = Path(args.directory)
    init_project(target)


def cmd_build(args: argparse.Namespace) -> None:
    from .generate import build_all

    config_path = find_config(args.config)
    select = args.select or None
    build_all(config_path, select=select)


def cmd_list(args: argparse.Namespace) -> None:
    from .generate import list_charts

    config_path = find_config(args.config)
    list_charts(config_path)


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="deck",
        description="Generate investor-quality charts from YAML definitions.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # deck init
    init_parser = subparsers.add_parser("init", help="Scaffold a new deckfile project")
    init_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to initialize (default: current directory)",
    )

    # deck docs
    subparsers.add_parser("docs", help="Print the README documentation")

    # deck build
    build_parser = subparsers.add_parser("build", help="Build charts from a deckfile")
    build_parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help=f"Path to YAML config (default: {DEFAULT_CONFIG})",
    )
    build_parser.add_argument(
        "-s", "--select",
        nargs="+",
        metavar="CHART",
        help="Build only the specified chart(s)",
    )
    build_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full traceback on errors",
    )

    # deck list (alias: ls)
    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List charts defined in a deckfile")
    list_parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help=f"Path to YAML config (default: {DEFAULT_CONFIG})",
    )
    list_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full traceback on errors",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    debug = getattr(args, "debug", False)

    try:
        if args.command == "docs":
            cmd_docs(args)
        elif args.command == "init":
            cmd_init(args)
        elif args.command == "build":
            cmd_build(args)
        elif args.command in ("list", "ls"):
            cmd_list(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        if debug:
            traceback.print_exc()
        else:
            print(f"Error: {e}")
        sys.exit(1)
