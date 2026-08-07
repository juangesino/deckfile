"""Composition semantics: deep merge, presets, extends, and vars."""

from __future__ import annotations

import pytest

from deckfile.resolve import (
    deep_merge,
    interpolate,
    interpolate_string,
    parse_cli_vars,
    resolve_chart,
    resolve_charts,
    resolve_preset,
)


# ═══════════════════════════════════════════════════════════════════════════════
# deep_merge
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeepMerge:
    def test_nested_dicts_merge_rather_than_replace(self):
        base = {"y_format": {"style": "$K", "step": 200}}
        override = {"y_format": {"step": 500}}
        assert deep_merge(base, override) == {"y_format": {"style": "$K", "step": 500}}

    def test_lists_replace_wholesale(self):
        base = {"palette": ["a", "b", "c"]}
        override = {"palette": ["x"]}
        assert deep_merge(base, override) == {"palette": ["x"]}

    def test_explicit_null_deletes_inherited_key(self):
        base = {"y_lim": {"top": 100}, "title": "kept"}
        assert deep_merge(base, {"y_lim": None}) == {"title": "kept"}

    def test_null_on_absent_key_is_harmless(self):
        assert deep_merge({"a": 1}, {"b": None}) == {"a": 1}

    def test_tags_union_instead_of_replacing(self):
        base = {"tags": ["segments"]}
        override = {"tags": ["quarterly"]}
        assert deep_merge(base, override) == {"tags": ["segments", "quarterly"]}

    def test_tags_union_deduplicates(self):
        base = {"tags": ["a", "b"]}
        assert deep_merge(base, {"tags": ["b", "c"]}) == {"tags": ["a", "b", "c"]}

    def test_does_not_mutate_inputs(self):
        base = {"nested": {"a": 1}}
        override = {"nested": {"b": 2}}
        deep_merge(base, override)
        assert base == {"nested": {"a": 1}}
        assert override == {"nested": {"b": 2}}

    def test_scalar_overwrites_dict(self):
        assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


# ═══════════════════════════════════════════════════════════════════════════════
# Presets
# ═══════════════════════════════════════════════════════════════════════════════

class TestPresets:
    def test_applies_preset_block(self):
        presets = {"monthly": {"x_labels": {"mode": "auto_date"}}}
        charts = {"c": {"preset": "monthly", "type": "bar"}}
        resolved = resolve_chart("c", charts, presets)
        assert resolved == {"x_labels": {"mode": "auto_date"}, "type": "bar"}

    def test_chart_keys_win_over_preset(self):
        presets = {"p": {"y_format": {"style": "number", "step": 10}}}
        charts = {"c": {"preset": "p", "y_format": {"style": "$K"}}}
        resolved = resolve_chart("c", charts, presets)
        assert resolved["y_format"] == {"style": "$K", "step": 10}

    def test_later_preset_wins_over_earlier(self):
        presets = {"a": {"legend": {"loc": "top"}}, "b": {"legend": {"loc": "bottom"}}}
        charts = {"c": {"preset": ["a", "b"]}}
        assert resolve_chart("c", charts, presets)["legend"] == {"loc": "bottom"}

    def test_preset_can_extend_another_preset(self):
        presets = {
            "base": {"separators": {"auto": True}, "transform": {"sort": True}},
            "quarterly": {"extends": "base", "separators": {"trigger": "Q1"}},
        }
        resolved = resolve_preset("quarterly", presets)
        assert resolved == {
            "separators": {"auto": True, "trigger": "Q1"},
            "transform": {"sort": True},
        }

    def test_unknown_preset_names_available_ones(self):
        charts = {"c": {"preset": "nope"}}
        with pytest.raises(ValueError, match="Unknown preset: 'nope'"):
            resolve_chart("c", charts, {"real": {}})

    def test_circular_preset_inheritance_detected(self):
        presets = {"a": {"extends": "b"}, "b": {"extends": "a"}}
        with pytest.raises(ValueError, match="Circular preset inheritance"):
            resolve_preset("a", presets)

    def test_malformed_preset_field_names_the_chart(self):
        charts = {"my_chart": {"preset": {"not": "a name"}}}
        with pytest.raises(ValueError, match="Chart 'my_chart': 'preset' must be"):
            resolve_chart("my_chart", charts, {})

    def test_malformed_extends_field_names_the_chart(self):
        charts = {"my_chart": {"extends": 42}}
        with pytest.raises(ValueError, match="Chart 'my_chart': 'extends' must be"):
            resolve_chart("my_chart", charts, {})

    def test_control_keys_are_stripped(self):
        presets = {"p": {"type": "bar"}}
        charts = {"c": {"preset": "p", "extends": None, "title": "t"}}
        resolved = resolve_chart("c", charts, presets)
        assert "preset" not in resolved and "extends" not in resolved


# ═══════════════════════════════════════════════════════════════════════════════
# Extends
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtends:
    def test_inherits_parent_keys(self):
        charts = {
            "base": {"type": "bar", "y_format": {"style": "$K", "step": 200}},
            "child": {"extends": "base", "title": "Child"},
        }
        resolved = resolve_chart("child", charts, {})
        assert resolved == {
            "type": "bar",
            "y_format": {"style": "$K", "step": 200},
            "title": "Child",
        }

    def test_child_overrides_parent(self):
        charts = {
            "base": {"y_format": {"style": "$K", "step": 200}},
            "child": {"extends": "base", "y_format": {"style": "pct"}},
        }
        resolved = resolve_chart("child", charts, {})
        assert resolved["y_format"] == {"style": "pct", "step": 200}

    def test_multi_level_chain(self):
        charts = {
            "a": {"type": "bar", "figsize": [16, 8]},
            "b": {"extends": "a", "source": "s"},
            "c": {"extends": "b", "title": "T"},
        }
        resolved = resolve_chart("c", charts, {})
        assert resolved == {
            "type": "bar",
            "figsize": [16, 8],
            "source": "s",
            "title": "T",
        }

    def test_child_can_delete_inherited_key(self):
        charts = {
            "base": {"type": "bar", "y_lim": {"top": 100}},
            "child": {"extends": "base", "y_lim": None},
        }
        assert "y_lim" not in resolve_chart("child", charts, {})

    def test_own_preset_wins_over_inherited_base(self):
        # A chart's own preset is a deliberate act, so it beats what the
        # parent happened to set.
        presets = {"pct": {"y_format": {"style": "pct"}}}
        charts = {
            "base": {"y_format": {"style": "$K"}},
            "child": {"extends": "base", "preset": "pct"},
        }
        assert resolve_chart("child", charts, presets)["y_format"]["style"] == "pct"

    def test_own_keys_win_over_own_preset(self):
        presets = {"pct": {"y_format": {"style": "pct"}}}
        charts = {"c": {"preset": "pct", "y_format": {"style": "number"}}}
        assert resolve_chart("c", charts, presets)["y_format"]["style"] == "number"

    def test_circular_inheritance_detected(self):
        charts = {"a": {"extends": "b"}, "b": {"extends": "a"}}
        with pytest.raises(ValueError, match="Circular chart inheritance"):
            resolve_chart("a", charts, {})

    def test_self_reference_detected(self):
        with pytest.raises(ValueError, match="Circular chart inheritance"):
            resolve_chart("a", {"a": {"extends": "a"}}, {})

    def test_unknown_parent_errors(self):
        with pytest.raises(ValueError, match="Unknown chart: 'ghost'"):
            resolve_chart("c", {"c": {"extends": "ghost"}}, {})

    def test_abstract_charts_excluded_but_still_extendable(self):
        charts = {
            "_base": {"abstract": True, "type": "bar"},
            "real": {"extends": "_base", "title": "T"},
        }
        resolved = resolve_charts(charts, {})
        assert set(resolved) == {"real"}
        assert resolved["real"]["type"] == "bar"
        assert "abstract" not in resolved["real"]

    def test_tags_accumulate_down_a_chain(self):
        charts = {
            "base": {"tags": ["segments"]},
            "child": {"extends": "base", "tags": ["quarterly"]},
        }
        assert resolve_chart("child", charts, {})["tags"] == ["segments", "quarterly"]

    def test_diamond_resolves_without_error(self):
        charts = {
            "root": {"type": "bar"},
            "left": {"extends": "root", "title": "L"},
            "right": {"extends": "root", "subtitle": "R"},
            "join": {"extends": ["left", "right"]},
        }
        resolved = resolve_chart("join", charts, {})
        assert resolved == {"type": "bar", "title": "L", "subtitle": "R"}


# ═══════════════════════════════════════════════════════════════════════════════
# Vars
# ═══════════════════════════════════════════════════════════════════════════════

class TestVars:
    def test_substitutes_inside_a_larger_string(self):
        out = interpolate_string("Live accounts · {{ var('as_of') }}", {"as_of": "Jun 2026"})
        assert out == "Live accounts · Jun 2026"

    def test_whole_string_reference_keeps_native_type(self):
        assert interpolate_string("{{ var('cap') }}", {"cap": 1000}) == 1000
        assert interpolate_string("{{ var('flag') }}", {"flag": True}) is True

    def test_partial_reference_stringifies(self):
        assert interpolate_string("top={{ var('cap') }}", {"cap": 1000}) == "top=1000"

    def test_double_quotes_accepted(self):
        assert interpolate_string('{{ var("x") }}', {"x": "y"}) == "y"

    def test_default_used_when_var_absent(self):
        assert interpolate_string("{{ var('x', 'fallback') }}", {}) == "fallback"
        assert interpolate_string("{{ var('n', 42) }}", {}) == 42

    def test_defined_var_beats_default(self):
        assert interpolate_string("{{ var('x', 'fallback') }}", {"x": "real"}) == "real"

    def test_undefined_var_errors_with_guidance(self):
        with pytest.raises(ValueError, match="Undefined var 'missing'"):
            interpolate_string("{{ var('missing') }}", {"other": 1}, where="chart 'c'")

    def test_python_format_strings_pass_through(self):
        # Single braces are chart label formats and must survive untouched.
        assert interpolate_string("${value:,.0f}K", {}) == "${value:,.0f}K"

    def test_multiple_references_in_one_string(self):
        out = interpolate_string("{{ var('a') }} - {{ var('b') }}", {"a": "Q1", "b": "Q4"})
        assert out == "Q1 - Q4"

    def test_recurses_through_structures(self):
        spec = {
            "subtitle": "As of {{ var('as_of') }}",
            "y_lim": {"top": "{{ var('cap') }}"},
            "tags": ["{{ var('env') }}"],
        }
        out = interpolate(spec, {"as_of": "Jun", "cap": 500, "env": "prod"})
        assert out == {
            "subtitle": "As of Jun",
            "y_lim": {"top": 500},
            "tags": ["prod"],
        }

    def test_non_strings_untouched(self):
        assert interpolate({"a": 1, "b": None, "c": True}, {}) == {"a": 1, "b": None, "c": True}


class TestParseCliVars:
    def test_parses_typed_values(self):
        assert parse_cli_vars(["cap=1000", "name=hello", "flag=true"]) == {
            "cap": 1000,
            "name": "hello",
            "flag": True,
        }

    def test_value_may_contain_equals(self):
        assert parse_cli_vars(["q=a=b"]) == {"q": "a=b"}

    def test_missing_equals_errors(self):
        with pytest.raises(ValueError, match="Expected the form name=value"):
            parse_cli_vars(["bare"])

    def test_empty_name_errors(self):
        with pytest.raises(ValueError, match="Missing variable name"):
            parse_cli_vars(["=value"])
