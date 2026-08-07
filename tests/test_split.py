"""Migration: splitting a monolithic deckfile into a multi-file project."""

from __future__ import annotations

import pytest
import yaml

from deckfile.project import load_project
from deckfile.split import group_charts, split_project


class TestGrouping:
    def test_groups_by_first_name_token(self):
        charts = dict.fromkeys(
            ["monthly_a", "monthly_b", "quarterly_a", "quarterly_b"], {}
        )
        assert group_charts(charts) == {
            "monthly": ["monthly_a", "monthly_b"],
            "quarterly": ["quarterly_a", "quarterly_b"],
        }

    def test_singleton_groups_collect_into_misc(self):
        charts = dict.fromkeys(["alone", "solo_chart", "pair_a", "pair_b"], {})
        groups = group_charts(charts)
        assert set(groups["misc"]) == {"alone", "solo_chart"}
        assert groups["pair"] == ["pair_a", "pair_b"]

    def test_large_group_subdivides_by_second_token(self):
        # Twenty segment charts would be one unwieldy file, so they split by
        # the dimension in their name.
        charts = dict.fromkeys(
            [f"segment_country_{i}" for i in range(10)]
            + [f"segment_plan_{i}" for i in range(10)],
            {},
        )
        groups = group_charts(charts)
        assert len(groups["segment/country"]) == 10
        assert len(groups["segment/plan"]) == 10

    def test_every_chart_lands_in_exactly_one_group(self):
        names = [f"segment_{d}_{m}" for d in "abcdef" for m in "xyz"] + ["lonely"]
        groups = group_charts(dict.fromkeys(names, {}))
        placed = [n for names_ in groups.values() for n in names_]
        assert sorted(placed) == sorted(names)
        assert len(placed) == len(set(placed))


class TestSplit:
    @pytest.fixture
    def monolith(self, make_project):
        return make_project({
            "defaults": {"output_dir": "./output"},
            "vars": {"as_of": "Jun 2026"},
            "sources": {
                "raw": {"type": "snowflake", "query": "select 1 as x\n"},
                "derived": {"type": "dep", "query": "select * from ref(raw)\n"},
                "big_wh": {
                    "type": "snowflake",
                    "query": "select 2",
                    "warehouse": "BIG",
                },
                "seed": {"type": "file", "path": "data/seed.csv"},
            },
            "charts": {
                "monthly_a": {"type": "bar", "source": "raw"},
                "monthly_b": {"type": "bar", "source": "derived"},
                "solo": {"type": "line", "source": "seed"},
            },
        })

    def test_writes_sql_models(self, monolith):
        split_project(monolith)
        root = monolith.parent
        assert (root / "models" / "raw.sql").read_text() == "select 1 as x\n"
        assert (root / "models" / "derived.sql").read_text() == "select * from ref(raw)\n"

    def test_location_sources_stay_in_yaml(self, monolith):
        split_project(monolith)
        assert not (monolith.parent / "models" / "seed.sql").exists()
        project_config = yaml.safe_load(monolith.read_text())
        assert project_config["sources"]["seed"]["path"] == "data/seed.csv"

    def test_inferable_types_are_not_restated(self, monolith):
        split_project(monolith)
        project_config = yaml.safe_load(monolith.read_text())
        # raw and derived carry no config beyond their query, so they need no
        # YAML entry at all.
        assert "raw" not in project_config.get("sources", {})
        assert "derived" not in project_config.get("sources", {})

    def test_extra_source_config_is_preserved(self, monolith):
        split_project(monolith)
        project_config = yaml.safe_load(monolith.read_text())
        assert project_config["sources"]["big_wh"] == {"warehouse": "BIG"}

    def test_charts_are_grouped_into_files(self, monolith):
        split_project(monolith)
        charts_dir = monolith.parent / "charts"
        monthly = yaml.safe_load((charts_dir / "monthly.yml").read_text())
        assert set(monthly["charts"]) == {"monthly_a", "monthly_b"}
        misc = yaml.safe_load((charts_dir / "misc.yml").read_text())
        assert set(misc["charts"]) == {"solo"}

    def test_project_settings_are_kept(self, monolith):
        split_project(monolith)
        project_config = yaml.safe_load(monolith.read_text())
        assert project_config["defaults"] == {"output_dir": "./output"}
        assert project_config["vars"] == {"as_of": "Jun 2026"}
        assert "charts" not in project_config

    def test_original_is_backed_up(self, monolith):
        original = monolith.read_text()
        split_project(monolith)
        assert (monolith.parent / "deckfile.yaml.bak").read_text() == original

    def test_round_trip_preserves_the_resolved_project(self, monolith):
        before = load_project(monolith).as_config()
        split_project(monolith)
        after = load_project(monolith).as_config()

        assert set(before["charts"]) == set(after["charts"])
        assert before["charts"] == after["charts"]
        assert set(before["sources"]) == set(after["sources"])
        for name, spec in before["sources"].items():
            assert after["sources"][name]["type"] == spec["type"], name
            # SQL files are written with a trailing newline, which is the only
            # way a query is allowed to differ.
            before_query = (spec.get("query") or "").rstrip("\n")
            after_query = (after["sources"][name].get("query") or "").rstrip("\n")
            assert after_query == before_query, name

    def test_refuses_to_overwrite_without_force(self, monolith):
        split_project(monolith)
        with pytest.raises(ValueError, match="Refusing to overwrite"):
            split_project(monolith)

    def test_force_overwrites(self, monolith):
        split_project(monolith)
        split_project(monolith, force=True)
        assert (monolith.parent / "models" / "raw.sql").exists()

    def test_can_write_to_a_separate_directory(self, monolith, tmp_path):
        target = tmp_path / "split_out"
        target.mkdir()
        split_project(monolith, target=target)
        assert (target / "models" / "raw.sql").exists()
        assert (target / "deckfile.yaml").exists()
        # The source project is left alone apart from its backup.
        assert not (monolith.parent / "models").exists()

    def test_empty_deckfile_errors(self, make_project):
        with pytest.raises(ValueError, match="nothing to split"):
            split_project(make_project({"defaults": {}}))
