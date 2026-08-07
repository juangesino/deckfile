"""Project discovery: multi-file merging, SQL models, and backwards compatibility."""

from __future__ import annotations

import pytest

from deckfile.project import load_project


class TestSingleFile:
    """A pre-split deckfile must keep behaving exactly as it did."""

    def test_monolithic_project_still_loads(self, make_project):
        deckfile = make_project({
            "defaults": {"output_dir": "./out"},
            "sources": {"s": {"type": "file", "path": "data/x.csv"}},
            "charts": {"c": {"type": "bar", "source": "s", "columns": {"y": "v"}}},
        })
        project = load_project(deckfile)
        assert set(project.charts) == {"c"}
        assert project.sources["s"]["type"] == "file"
        assert project.defaults == {"output_dir": "./out"}

    def test_empty_project_is_not_an_error(self, make_project):
        project = load_project(make_project({}))
        assert project.charts == {}
        assert project.sources == {}

    def test_missing_conventional_dirs_are_fine(self, make_project):
        project = load_project(make_project({"charts": {"c": {"type": "bar"}}}))
        assert set(project.charts) == {"c"}

    def test_top_level_non_mapping_rejected(self, make_project):
        with pytest.raises(ValueError, match="expected a mapping"):
            load_project(make_project("- just\n- a list\n"))


class TestDiscovery:
    def test_charts_dir_is_discovered_automatically(self, make_project):
        deckfile = make_project(
            {"defaults": {}},
            {"charts/segments.yml": "charts:\n  seg_a:\n    type: bar\n"},
        )
        assert set(load_project(deckfile).charts) == {"seg_a"}

    def test_nested_directories_are_walked(self, make_project):
        deckfile = make_project(
            {},
            {
                "charts/a/b/deep.yml": "charts:\n  deep:\n    type: bar\n",
                "charts/top.yaml": "charts:\n  top:\n    type: line\n",
            },
        )
        assert set(load_project(deckfile).charts) == {"deep", "top"}

    def test_project_file_and_chart_files_share_a_namespace(self, make_project):
        deckfile = make_project(
            {"charts": {"in_project": {"type": "bar"}}},
            {"charts/more.yml": "charts:\n  in_file:\n    type: line\n"},
        )
        assert set(load_project(deckfile).charts) == {"in_project", "in_file"}

    def test_presets_can_live_in_chart_files(self, make_project):
        deckfile = make_project(
            {},
            {
                "charts/presets.yml": (
                    "presets:\n  monthly:\n    x_labels:\n      mode: auto_date\n"
                ),
                "charts/c.yml": "charts:\n  c:\n    preset: monthly\n    type: bar\n",
            },
        )
        project = load_project(deckfile)
        assert project.charts["c"]["x_labels"] == {"mode": "auto_date"}

    def test_explicit_paths_are_honoured(self, make_project):
        deckfile = make_project(
            {"chart_paths": ["viz"]},
            {"viz/a.yml": "charts:\n  a:\n    type: bar\n",
             "charts/ignored.yml": "charts:\n  ignored:\n    type: bar\n"},
        )
        assert set(load_project(deckfile).charts) == {"a"}

    def test_missing_configured_path_errors(self, make_project):
        deckfile = make_project({"chart_paths": ["nope"]})
        with pytest.raises(ValueError, match="Configured path 'nope' does not exist"):
            load_project(deckfile)

    def test_hidden_directories_skipped(self, make_project):
        deckfile = make_project(
            {},
            {"charts/.hidden/x.yml": "charts:\n  hidden:\n    type: bar\n",
             "charts/real.yml": "charts:\n  real:\n    type: bar\n"},
        )
        assert set(load_project(deckfile).charts) == {"real"}

    def test_unexpected_top_level_key_in_chart_file_errors(self, make_project):
        deckfile = make_project({}, {"charts/bad.yml": "defaults:\n  output_dir: ./x\n"})
        with pytest.raises(ValueError, match="unexpected top-level key"):
            load_project(deckfile)

    def test_chart_file_origin_is_tracked(self, make_project):
        deckfile = make_project({}, {"charts/seg.yml": "charts:\n  c:\n    type: bar\n"})
        project = load_project(deckfile)
        assert project.chart_files["c"].name == "seg.yml"


class TestDuplicates:
    def test_duplicate_chart_names_across_files_error(self, make_project):
        deckfile = make_project(
            {},
            {
                "charts/a.yml": "charts:\n  dup:\n    type: bar\n",
                "charts/b.yml": "charts:\n  dup:\n    type: line\n",
            },
        )
        with pytest.raises(ValueError) as excinfo:
            load_project(deckfile)
        message = str(excinfo.value)
        assert "Duplicate chart name 'dup'" in message
        # Both files must be named so the collision is actionable.
        assert "a.yml" in message and "b.yml" in message

    def test_duplicate_between_project_file_and_chart_file(self, make_project):
        deckfile = make_project(
            {"charts": {"dup": {"type": "bar"}}},
            {"charts/a.yml": "charts:\n  dup:\n    type: line\n"},
        )
        with pytest.raises(ValueError, match="Duplicate chart name 'dup'"):
            load_project(deckfile)

    def test_duplicate_model_stems_error(self, make_project):
        deckfile = make_project(
            {},
            {"models/a/live.sql": "select 1", "models/b/live.sql": "select 2"},
        )
        with pytest.raises(ValueError, match="Duplicate model name 'live'"):
            load_project(deckfile)

    def test_duplicate_preset_names_error(self, make_project):
        deckfile = make_project(
            {},
            {
                "charts/a.yml": "presets:\n  p:\n    type: bar\n",
                "charts/b.yml": "presets:\n  p:\n    type: line\n",
            },
        )
        with pytest.raises(ValueError, match="Duplicate preset name 'p'"):
            load_project(deckfile)


class TestSqlModels:
    def test_sql_file_becomes_a_source_named_after_the_file(self, make_project):
        deckfile = make_project({}, {"models/live.sql": "select * from t\n"})
        project = load_project(deckfile)
        assert project.sources["live"]["query"] == "select * from t\n"

    def test_query_with_ref_is_inferred_as_dep(self, make_project):
        deckfile = make_project(
            {},
            {"models/base.sql": "select 1 as x",
             "models/derived.sql": "select * from ref(base)"},
        )
        project = load_project(deckfile)
        assert project.sources["derived"]["type"] == "dep"

    def test_query_without_ref_uses_default_model_type(self, make_project):
        deckfile = make_project({}, {"models/raw.sql": "select 1"})
        assert load_project(deckfile).sources["raw"]["type"] == "snowflake"

    def test_default_model_type_is_configurable(self, make_project):
        deckfile = make_project(
            {"default_model_type": "url"}, {"models/raw.sql": "select 1"}
        )
        assert load_project(deckfile).sources["raw"]["type"] == "url"

    def test_matching_sources_entry_supplies_config(self, make_project):
        deckfile = make_project(
            {"sources": {"raw": {"warehouse": "BIG_WH", "role": "ANALYST"}}},
            {"models/raw.sql": "select 1"},
        )
        spec = load_project(deckfile).sources["raw"]
        assert spec["warehouse"] == "BIG_WH"
        assert spec["role"] == "ANALYST"
        assert spec["query"] == "select 1"

    def test_explicit_type_overrides_inference(self, make_project):
        deckfile = make_project(
            {"sources": {"raw": {"type": "dep"}}}, {"models/raw.sql": "select 1"}
        )
        assert load_project(deckfile).sources["raw"]["type"] == "dep"

    def test_query_defined_in_two_places_errors(self, make_project):
        deckfile = make_project(
            {"sources": {"raw": {"query": "select 2"}}}, {"models/raw.sql": "select 1"}
        )
        with pytest.raises(ValueError, match="has a query in two places"):
            load_project(deckfile)

    def test_nested_model_directories_are_walked(self, make_project):
        deckfile = make_project(
            {}, {"models/core/a.sql": "select 1", "models/segments/b.sql": "select 2"}
        )
        assert set(load_project(deckfile).sources) == {"a", "b"}

    def test_sources_carry_project_root_for_relative_paths(self, make_project):
        deckfile = make_project({"sources": {"s": {"type": "file", "path": "d.csv"}}})
        project = load_project(deckfile)
        assert project.sources["s"]["_root"] == str(project.root)


class TestVarsIntegration:
    def test_vars_interpolate_into_charts(self, make_project):
        deckfile = make_project({
            "vars": {"as_of": "Jun 2026"},
            "charts": {"c": {"type": "bar", "subtitle": "Live · {{ var('as_of') }}"}},
        })
        assert load_project(deckfile).charts["c"]["subtitle"] == "Live · Jun 2026"

    def test_vars_interpolate_into_sql_models(self, make_project):
        deckfile = make_project(
            {"vars": {"cutoff": "2026-01-01"}},
            {"models/m.sql": "select * from t where d >= '{{ var('cutoff') }}'"},
        )
        query = load_project(deckfile).sources["m"]["query"]
        assert query == "select * from t where d >= '2026-01-01'"

    def test_cli_vars_override_project_vars(self, make_project):
        deckfile = make_project({
            "vars": {"as_of": "Jun 2026"},
            "charts": {"c": {"subtitle": "{{ var('as_of') }}"}},
        })
        project = load_project(deckfile, cli_vars={"as_of": "Jul 2026"})
        assert project.charts["c"]["subtitle"] == "Jul 2026"

    def test_vars_apply_through_presets(self, make_project):
        deckfile = make_project({
            "vars": {"period": "Q1-Q4"},
            "presets": {"p": {"subtitle": "{{ var('period') }}"}},
            "charts": {"c": {"preset": "p", "type": "bar"}},
        })
        assert load_project(deckfile).charts["c"]["subtitle"] == "Q1-Q4"

    def test_undefined_var_names_the_chart(self, make_project):
        deckfile = make_project({"charts": {"my_chart": {"title": "{{ var('nope') }}"}}})
        with pytest.raises(ValueError, match="chart 'my_chart'"):
            load_project(deckfile)


class TestAsConfig:
    def test_flattens_to_single_file_shape(self, make_project):
        deckfile = make_project(
            {"defaults": {"output_dir": "./o"}, "vars": {"a": 1}},
            {
                "charts/c.yml": "charts:\n  c:\n    type: bar\n    source: m\n",
                "models/m.sql": "select 1",
            },
        )
        config = load_project(deckfile).as_config()
        assert set(config) == {"defaults", "vars", "sources", "charts"}
        assert config["charts"]["c"]["type"] == "bar"
        assert config["sources"]["m"]["query"] == "select 1"

    def test_abstract_charts_excluded_from_output(self, make_project):
        deckfile = make_project({
            "charts": {
                "_tpl": {"abstract": True, "type": "bar"},
                "real": {"extends": "_tpl"},
            }
        })
        assert set(load_project(deckfile).as_config()["charts"]) == {"real"}
