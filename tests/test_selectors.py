"""Chart selection: names, globs, tags, paths, and the model graph."""

from __future__ import annotations

import pytest

from deckfile.project import load_project
from deckfile.selectors import descendants, select_charts


@pytest.fixture
def project(make_project):
    """A project with tags, several files, and a three-level model DAG."""
    deckfile = make_project(
        {
            "sources": {
                "seed": {"type": "file", "path": "seed.csv"},
                "unrelated": {"type": "file", "path": "other.csv"},
            },
            "charts": {
                "top_level": {"type": "bar", "source": "unrelated"},
            },
        },
        {
            "models/live.sql": "select * from ref(seed)",
            "models/monthly.sql": "select * from ref(live)",
            "charts/segments/country.yml": (
                "charts:\n"
                "  segment_country_logos:\n"
                "    type: bar\n"
                "    source: monthly\n"
                "    tags: [segments, country]\n"
                "  segment_country_revenue:\n"
                "    type: bar\n"
                "    source: live\n"
                "    tags: [segments]\n"
            ),
            "charts/quarterly.yml": (
                "charts:\n"
                "  quarterly_growth:\n"
                "    type: line\n"
                "    source: seed\n"
                "    tags: [quarterly]\n"
            ),
        },
    )
    return load_project(deckfile)


class TestNameSelectors:
    def test_exact_name(self, project):
        assert select_charts(["quarterly_growth"], project) == ["quarterly_growth"]

    def test_glob_matches_a_family(self, project):
        assert select_charts(["segment_country_*"], project) == [
            "segment_country_logos",
            "segment_country_revenue",
        ]

    def test_glob_with_question_mark(self, project):
        assert select_charts(["quarterly_growt?"], project) == ["quarterly_growth"]

    def test_unknown_name_suggests_near_matches(self, project):
        with pytest.raises(ValueError) as excinfo:
            select_charts(["quarterly_growt"], project)
        message = str(excinfo.value)
        assert "matched no charts" in message
        assert "Did you mean: quarterly_growth" in message

    def test_unknown_name_does_not_dump_every_chart(self, project):
        # A project with hundreds of charts must not print all of them.
        with pytest.raises(ValueError) as excinfo:
            select_charts(["totally_unrelated_xyz"], project)
        message = str(excinfo.value)
        assert "run 'deck list'" in message
        assert "segment_country_logos" not in message

    def test_glob_matching_nothing_errors(self, project):
        with pytest.raises(ValueError, match="matched no charts"):
            select_charts(["zzz_*"], project)


class TestTagSelectors:
    def test_selects_by_tag(self, project):
        assert select_charts(["tag:segments"], project) == [
            "segment_country_logos",
            "segment_country_revenue",
        ]

    def test_second_tag_narrows(self, project):
        assert select_charts(["tag:country"], project) == ["segment_country_logos"]

    def test_unknown_tag_lists_known_tags(self, project):
        with pytest.raises(ValueError) as excinfo:
            select_charts(["tag:ghost"], project)
        assert "Known tags:" in str(excinfo.value)
        assert "segments" in str(excinfo.value)


class TestPathSelectors:
    def test_selects_by_directory(self, project):
        assert select_charts(["path:charts/segments"], project) == [
            "segment_country_logos",
            "segment_country_revenue",
        ]

    def test_selects_by_exact_file(self, project):
        assert select_charts(["path:charts/quarterly.yml"], project) == [
            "quarterly_growth"
        ]

    def test_parent_directory_selects_everything_below(self, project):
        selected = select_charts(["path:charts"], project)
        assert set(selected) == {
            "segment_country_logos",
            "segment_country_revenue",
            "quarterly_growth",
        }

    def test_file_may_be_named_without_its_extension(self, project):
        # Whether a group is a directory or a single .yml is an organizational
        # detail the selector should not depend on.
        assert select_charts(["path:charts/quarterly"], project) == ["quarterly_growth"]

    def test_nonexistent_path_says_what_it_looked_for(self, project):
        with pytest.raises(ValueError) as excinfo:
            select_charts(["path:charts/nonexistent"], project)
        message = str(excinfo.value)
        assert "does not match any file or directory" in message
        assert "charts/nonexistent.yml" in message

    def test_existing_path_with_no_charts_errors(self, project, tmp_path):
        (project.root / "charts" / "empty").mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="matched no charts"):
            select_charts(["path:charts/empty"], project)


class TestGraphSelectors:
    def test_descendants_walks_the_ref_chain(self, project):
        assert descendants("seed", project.sources) == {"seed", "live", "monthly"}

    def test_descendants_of_a_leaf_is_itself(self, project):
        assert descendants("monthly", project.sources) == {"monthly"}

    def test_unrelated_models_excluded(self, project):
        assert "unrelated" not in descendants("seed", project.sources)

    def test_selects_charts_downstream_of_a_model(self, project):
        # seed feeds live feeds monthly, so every chart on that chain is caught.
        # Order follows definition order, not graph order.
        assert select_charts(["seed+"], project) == [
            "quarterly_growth",
            "segment_country_logos",
            "segment_country_revenue",
        ]

    def test_narrower_model_selects_fewer_charts(self, project):
        assert select_charts(["live+"], project) == [
            "segment_country_logos",
            "segment_country_revenue",
        ]

    def test_leaf_model_selects_only_its_own_chart(self, project):
        assert select_charts(["monthly+"], project) == ["segment_country_logos"]

    def test_unknown_model_errors(self, project):
        with pytest.raises(ValueError, match="Unknown model 'ghost'"):
            select_charts(["ghost+"], project)


class TestCombining:
    def test_selectors_union(self, project):
        selected = select_charts(["tag:quarterly", "segment_country_logos"], project)
        assert set(selected) == {"quarterly_growth", "segment_country_logos"}

    def test_overlapping_selectors_do_not_duplicate(self, project):
        selected = select_charts(["tag:segments", "segment_country_*"], project)
        assert selected == ["segment_country_logos", "segment_country_revenue"]

    def test_results_follow_definition_order(self, project):
        # Selector order must not change build order. The project file's own
        # charts come first, then chart files in sorted path order.
        forwards = select_charts(["quarterly_growth", "top_level"], project)
        backwards = select_charts(["top_level", "quarterly_growth"], project)
        assert forwards == backwards == ["top_level", "quarterly_growth"]


class TestAbstractCharts:
    def test_selecting_a_template_explains_why_it_matched_nothing(self, make_project):
        deckfile = make_project({
            "charts": {
                "_base": {"abstract": True, "type": "bar"},
                "real": {"extends": "_base"},
            }
        })
        project = load_project(deckfile)
        with pytest.raises(ValueError, match="abstract template"):
            select_charts(["_base"], project)
