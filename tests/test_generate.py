"""Build-time behaviour that the composition layer changed."""

from __future__ import annotations

from pathlib import Path

from deckfile.generate import _needed_sources, _resolve_source_path


class TestNeededSources:
    """Selecting one chart must not execute every model in the project."""

    SOURCES = {
        "seed": {"type": "file", "path": "s.csv"},
        "live": {"type": "dep", "query": "select * from ref(seed)"},
        "monthly": {"type": "dep", "query": "select * from ref(live)"},
        "other_seed": {"type": "file", "path": "o.csv"},
        "unrelated": {"type": "dep", "query": "select * from ref(other_seed)"},
    }

    def test_walks_the_ref_chain_upstream(self):
        charts = {"c": {"source": "monthly"}}
        assert _needed_sources(charts, self.SOURCES) == {"monthly", "live", "seed"}

    def test_excludes_unrelated_branches(self):
        charts = {"c": {"source": "monthly"}}
        needed = _needed_sources(charts, self.SOURCES)
        assert "unrelated" not in needed and "other_seed" not in needed

    def test_unions_across_charts(self):
        charts = {"a": {"source": "live"}, "b": {"source": "unrelated"}}
        assert _needed_sources(charts, self.SOURCES) == {
            "live", "seed", "unrelated", "other_seed",
        }

    def test_multiple_refs_in_one_query(self):
        sources = {
            "a": {"type": "file", "path": "a.csv"},
            "b": {"type": "file", "path": "b.csv"},
            "joined": {"type": "dep", "query": "select * from ref(a) join ref(b)"},
        }
        assert _needed_sources({"c": {"source": "joined"}}, sources) == {"joined", "a", "b"}

    def test_inline_sources_are_skipped(self):
        charts = {"c": {"source": {"type": "file", "path": "inline.csv"}}}
        assert _needed_sources(charts, self.SOURCES) == set()

    def test_no_charts_needs_nothing(self):
        assert _needed_sources({}, self.SOURCES) == set()

    def test_unknown_source_name_does_not_crash(self):
        # Validation happens later with a better message; this must not raise.
        assert _needed_sources({"c": {"source": "ghost"}}, self.SOURCES) == set()


class TestResolveSourcePath:
    """Relative file sources resolve against the project, not the cwd."""

    def test_relative_path_resolves_against_project_root(self, tmp_path: Path):
        data = tmp_path / "data.csv"
        data.write_text("a,b\n1,2\n")
        source = {"path": "data.csv", "_root": str(tmp_path)}
        assert _resolve_source_path(source) == str(data)

    def test_nested_relative_path(self, tmp_path: Path):
        nested = tmp_path / "data" / "seed.csv"
        nested.parent.mkdir()
        nested.write_text("a\n1\n")
        source = {"path": "data/seed.csv", "_root": str(tmp_path)}
        assert _resolve_source_path(source) == str(nested)

    def test_falls_back_to_the_path_as_given(self, tmp_path: Path):
        # A path that does not exist under the root is left alone, so projects
        # that relied on cwd-relative paths keep working.
        source = {"path": "elsewhere.csv", "_root": str(tmp_path)}
        assert _resolve_source_path(source) == "elsewhere.csv"

    def test_absolute_paths_untouched(self, tmp_path: Path):
        source = {"path": "/abs/data.csv", "_root": str(tmp_path)}
        assert _resolve_source_path(source) == "/abs/data.csv"

    def test_no_root_leaves_path_alone(self):
        assert _resolve_source_path({"path": "data.csv"}) == "data.csv"
