"""CLI entry point for deckfile.

Usage:
    deck build                       # Build all charts from deckfile.yaml
    deck build myconfig.yaml         # Build from a specific file
    deck build -s monthly_calls      # Build only selected chart(s)
    deck build -s tag:segments       # Build every chart carrying a tag
    deck build -s live+              # Build everything downstream of a model
    deck list                        # List all charts in deckfile.yaml
    deck compile                     # Print the fully-resolved config
    deck split                       # Migrate a single file into models/ + charts/
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
    """Resolve the project file path.

    Without an explicit path, the current directory and its parents are
    searched, so ``deck build`` works from anywhere inside a project rather
    than only from its root.
    """
    if explicit:
        p = Path(explicit)
        if not p.exists():
            print(f"Error: config file not found: {explicit}")
            sys.exit(1)
        if p.is_dir():
            candidate = p / DEFAULT_CONFIG
            if not candidate.exists():
                print(f"Error: no {DEFAULT_CONFIG} in directory: {explicit}")
                sys.exit(1)
            return str(candidate)
        return str(p)

    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        candidate = directory / DEFAULT_CONFIG
        if candidate.exists():
            return str(candidate)

    print(f"Error: no {DEFAULT_CONFIG} found in {current} or any parent directory.")
    print("Specify a path: deck build <path>")
    sys.exit(1)


def _cli_vars(args: argparse.Namespace) -> dict:
    """Parse repeated ``--var name=value`` flags."""
    from .resolve import parse_cli_vars

    return parse_cli_vars(getattr(args, "var", None) or [])


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


def _selectors(args: argparse.Namespace) -> list[str] | None:
    groups = getattr(args, "select", None)
    return [c for group in groups for c in group] if groups else None


def cmd_build(args: argparse.Namespace) -> None:
    from dotenv import load_dotenv

    from .generate import build_all

    config_path = find_config(args.config)
    load_dotenv(Path(config_path).resolve().parent / ".env")
    build_all(config_path, select=_selectors(args), cli_vars=_cli_vars(args))


def cmd_list(args: argparse.Namespace) -> None:
    from .generate import list_charts

    config_path = find_config(args.config)
    list_charts(config_path, select=_selectors(args), cli_vars=_cli_vars(args))


def cmd_compile(args: argparse.Namespace) -> None:
    from dotenv import load_dotenv

    from .generate import compile_project

    config_path = find_config(args.config)
    load_dotenv(Path(config_path).resolve().parent / ".env")
    compile_project(config_path, output=args.output, cli_vars=_cli_vars(args))


def cmd_split(args: argparse.Namespace) -> None:
    from .split import split_project

    config_path = find_config(args.config)
    split_project(
        config_path,
        target=Path(args.output) if args.output else None,
        force=args.force,
    )


def main(argv: list[str] | None = None) -> None:
    from importlib.metadata import version

    parser = argparse.ArgumentParser(
        prog="deck",
        description="Generate investor-quality charts from YAML definitions.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"deck {version('deckfile')}",
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

    def add_common(p, *, selectable: bool = True):
        p.add_argument(
            "config",
            nargs="?",
            default=None,
            help=f"Path to the project file (default: nearest {DEFAULT_CONFIG})",
        )
        if selectable:
            p.add_argument(
                "-s", "--select",
                nargs="+",
                action="append",
                metavar="SELECTOR",
                help=(
                    "Limit to matching charts. A selector is a chart name, a glob "
                    "(segment_country_*), tag:NAME, path:DIR_OR_FILE, or MODEL+ "
                    "for every chart downstream of a model. Repeatable; matches union."
                ),
            )
        p.add_argument(
            "--var",
            action="append",
            metavar="NAME=VALUE",
            help="Override a project var. Repeatable.",
        )
        p.add_argument(
            "--debug",
            action="store_true",
            help="Show full traceback on errors",
        )
        return p

    # deck build
    add_common(subparsers.add_parser("build", help="Build charts from a deckfile"))

    # deck list (alias: ls)
    add_common(
        subparsers.add_parser(
            "list", aliases=["ls"], help="List charts defined in a deckfile"
        )
    )

    # deck compile
    compile_parser = add_common(
        subparsers.add_parser(
            "compile",
            help="Print the fully-resolved config (presets, extends, and vars applied)",
        ),
        selectable=False,
    )
    compile_parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PATH",
        help="Write to a file instead of stdout",
    )

    # deck split
    split_parser = subparsers.add_parser(
        "split",
        help="Migrate a single-file deckfile into models/ and charts/ files",
    )
    split_parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help=f"Path to the deckfile to split (default: nearest {DEFAULT_CONFIG})",
    )
    split_parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="DIR",
        help="Write the split project here (default: alongside the deckfile)",
    )
    split_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing models/ and charts/ files",
    )
    split_parser.add_argument(
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
        elif args.command == "compile":
            cmd_compile(args)
        elif args.command == "split":
            cmd_split(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        if debug:
            traceback.print_exc()
        else:
            print(f"Error: {e}")
        sys.exit(1)
