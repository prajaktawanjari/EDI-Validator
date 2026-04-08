"""
Unit tests for edifact_structure_validator.py.

Run with:
    python -m pytest test_edifact_structure_validator.py -v
"""

import json
import pytest

from edifact_parser import parse
from edifact_structure_validator import (
    SegmentGroupRule,
    build_rules,
    validate_structure,
    validate_structure_raw,
    validate_structure_to_json,
    DEFAULT_RULES,
    _IFTMIN_HIERARCHY,
    _check_mandatory_and_max,
    _check_order,
    _check_hierarchy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(tag: str, *elements) -> dict:
    """Build a minimal parsed segment dict."""
    return {"tag": tag, "elements": list(elements)}


def _segs(*tags: str) -> list[dict]:
    """Build a list of bare segments from a sequence of tags."""
    return [_seg(t) for t in tags]


def _msg(*segment_strings: str) -> list[dict]:
    """Parse a sequence of raw segment strings (without terminators)."""
    return parse("'".join(segment_strings) + "'")


# ---------------------------------------------------------------------------
# build_rules
# ---------------------------------------------------------------------------

class TestBuildRules:
    def test_returns_list_of_segment_group_rules(self):
        rules = build_rules(DEFAULT_RULES)
        assert all(isinstance(r, SegmentGroupRule) for r in rules)

    def test_sorted_by_sg_number(self):
        rules = build_rules(DEFAULT_RULES)
        orders = [r.order for r in rules]
        assert orders == sorted(orders)

    def test_sg11_is_first(self):
        rules = build_rules(DEFAULT_RULES)
        assert rules[0].name == "SG11"
        assert rules[0].segment == "NAD"

    def test_mandatory_flag_set_correctly(self):
        rules = build_rules(DEFAULT_RULES)
        by_name = {r.name: r for r in rules}
        assert by_name["SG11"].mandatory is True
        assert by_name["SG18"].mandatory is True
        assert by_name["SG32"].mandatory is False  # conditional

    def test_max_occur_set(self):
        rules = build_rules(DEFAULT_RULES)
        by_name = {r.name: r for r in rules}
        assert by_name["SG11"].max_occur == 2
        assert by_name["SG18"].max_occur == 999
        assert by_name["SG32"].max_occur is None  # not specified

    def test_sg32_parent_resolved_from_iftmin_hierarchy(self):
        rules = build_rules(DEFAULT_RULES)
        by_name = {r.name: r for r in rules}
        assert by_name["SG32"].parent == "SG18"

    def test_sg11_and_sg18_have_no_parent(self):
        rules = build_rules(DEFAULT_RULES)
        by_name = {r.name: r for r in rules}
        assert by_name["SG11"].parent is None
        assert by_name["SG18"].parent is None

    def test_explicit_parent_overrides_hierarchy(self):
        custom = {"SG32": {"segment": "DGS", "conditional": True, "parent": "SG99"}}
        rules = build_rules(custom)
        assert rules[0].parent == "SG99"

    def test_conditional_true_sets_mandatory_false(self):
        custom = {"SG99": {"segment": "TST", "conditional": True}}
        rules = build_rules(custom)
        assert rules[0].mandatory is False

    def test_order_derived_from_sg_number(self):
        custom = {
            "SG5":  {"segment": "LOC"},
            "SG22": {"segment": "DIM"},
        }
        rules = build_rules(custom)
        assert rules[0].order == 5
        assert rules[1].order == 22

    def test_custom_rules_dict_accepted(self):
        custom = {
            "SG11": {"segment": "NAD", "mandatory": True, "max": 5},
            "SG18": {"segment": "GID", "mandatory": True, "max": 10},
        }
        rules = build_rules(custom)
        assert len(rules) == 2
        assert rules[0].max_occur == 5


# ---------------------------------------------------------------------------
# _check_mandatory_and_max
# ---------------------------------------------------------------------------

class TestCheckMandatoryAndMax:
    def test_mandatory_present_no_error(self):
        segs = [_seg("NAD"), _seg("GID")]
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert errors == []

    def test_mandatory_missing_adds_error(self):
        # GID absent
        segs = [_seg("NAD")]
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert any("SG18" in e and "mandatory" in e for e in errors)

    def test_both_mandatory_missing_adds_two_errors(self):
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max([], rules, errors)
        mandatory_errors = [e for e in errors if "mandatory" in e]
        assert len(mandatory_errors) == 2  # NAD and GID

    def test_conditional_absent_no_error(self):
        # DGS absent — that's fine for a conditional group
        segs = [_seg("NAD"), _seg("GID")]
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert not any("DGS" in e for e in errors)

    def test_max_not_exceeded_no_error(self):
        segs = [_seg("NAD"), _seg("NAD")]  # exactly 2, max is 2
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert not any("maximum" in e for e in errors)

    def test_max_exceeded_adds_error(self):
        segs = [_seg("NAD"), _seg("NAD"), _seg("NAD")]  # 3 > max 2
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert any("SG11" in e and "maximum" in e for e in errors)

    def test_max_none_means_unlimited(self):
        # DGS has max_occur=None — 100 occurrences should be fine
        segs = [_seg("GID")] + [_seg("DGS")] * 100 + [_seg("NAD")]
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert not any("DGS" in e and "maximum" in e for e in errors)

    def test_max_999_not_exceeded(self):
        segs = [_seg("NAD")] + [_seg("GID")] * 999
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert not any("SG18" in e and "maximum" in e for e in errors)

    def test_max_999_exceeded(self):
        segs = [_seg("NAD")] + [_seg("GID")] * 1000
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_mandatory_and_max(segs, rules, errors)
        assert any("SG18" in e and "maximum" in e for e in errors)


# ---------------------------------------------------------------------------
# _check_order
# ---------------------------------------------------------------------------

class TestCheckOrder:
    def test_correct_order_no_error(self):
        # NAD … GID — correct
        segs = _segs("UNB", "UNH", "BGM", "NAD", "NAD", "GID", "UNT")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert errors == []

    def test_nad_after_gid_is_order_violation(self):
        segs = _segs("UNH", "BGM", "GID", "NAD", "UNT")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert any("Order violation" in e and "SG11" in e for e in errors)

    def test_mixed_nad_gid_interleaved_reports_violation(self):
        # NAD, GID, NAD — the last NAD is after first GID
        segs = _segs("NAD", "GID", "NAD")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert any("Order violation" in e for e in errors)

    def test_only_one_group_present_no_order_error(self):
        # Only NAD — no GID to compare, absence caught elsewhere
        segs = _segs("NAD", "NAD")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert errors == []

    def test_child_group_position_not_checked_as_top_level(self):
        # DGS before NAD — should NOT flag an order violation here
        # (hierarchy check handles DGS/GID; order check ignores child groups)
        segs = _segs("DGS", "NAD", "GID")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert errors == []

    def test_multiple_violations_reported(self):
        # Three top-level groups defined; put them all out of order
        custom = {
            "SG5":  {"segment": "A", "mandatory": True},
            "SG10": {"segment": "B", "mandatory": True},
            "SG15": {"segment": "C", "mandatory": True},
        }
        # Order: C, B, A — violates SG5<SG10, SG5<SG15, and SG10<SG15
        segs = _segs("C", "B", "A")
        rules = build_rules(custom)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert len(errors) >= 2

    def test_correct_order_with_multiple_groups_each(self):
        segs = _segs("NAD", "NAD", "GID", "GID", "GID")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_order(segs, rules, errors)
        assert errors == []


# ---------------------------------------------------------------------------
# _check_hierarchy
# ---------------------------------------------------------------------------

class TestCheckHierarchy:
    def test_dgs_after_gid_no_error(self):
        segs = _segs("NAD", "GID", "DGS")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert errors == []

    def test_dgs_before_gid_is_hierarchy_violation(self):
        segs = _segs("NAD", "DGS", "GID")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert any("Hierarchy violation" in e and "SG32" in e for e in errors)

    def test_dgs_present_no_gid_is_hierarchy_violation(self):
        segs = _segs("NAD", "DGS")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert any("Hierarchy violation" in e and "SG18" in e for e in errors)

    def test_no_dgs_no_hierarchy_error(self):
        segs = _segs("NAD", "GID")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert errors == []

    def test_multiple_dgs_all_after_gid_no_error(self):
        segs = _segs("NAD", "GID", "DGS", "DGS", "DGS")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert errors == []

    def test_one_dgs_before_gid_triggers_error(self):
        # DGS, GID, DGS — first DGS is before GID
        segs = _segs("DGS", "GID", "DGS")
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert any("Hierarchy violation" in e for e in errors)

    def test_parent_not_in_schema_skips_check(self):
        # SG32 with parent "SG99", but SG99 is not in the schema
        custom = {"SG32": {"segment": "DGS", "conditional": True, "parent": "SG99"}}
        segs = _segs("DGS")
        rules = build_rules(custom)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        # SG99 not in rules, so no hierarchy check performed
        assert errors == []

    def test_hierarchy_error_reports_correct_indices(self):
        segs = _segs("DGS", "GID", "DGS")   # index 0: DGS, index 1: GID
        rules = build_rules(DEFAULT_RULES)
        errors: list[str] = []
        _check_hierarchy(segs, rules, errors)
        assert any("index 0" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_structure  (integration)
# ---------------------------------------------------------------------------

class TestValidateStructure:
    def test_valid_message_passes(self):
        segs = _segs("UNH", "BGM", "NAD", "NAD", "GID", "DGS", "UNT")
        result = validate_structure(segs)
        assert result["status"] == "PASS"
        assert result["errors"] == []

    def test_valid_without_optional_dgs(self):
        segs = _segs("UNH", "BGM", "NAD", "GID", "UNT")
        result = validate_structure(segs)
        assert result["status"] == "PASS"

    def test_missing_mandatory_nad_fails(self):
        segs = _segs("UNH", "BGM", "GID", "UNT")
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert any("SG11" in e for e in result["errors"])

    def test_missing_mandatory_gid_fails(self):
        segs = _segs("UNH", "BGM", "NAD", "UNT")
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert any("SG18" in e for e in result["errors"])

    def test_nad_count_exceeds_max_fails(self):
        segs = _segs("NAD", "NAD", "NAD", "GID")  # 3 NAD > max 2
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert any("maximum" in e and "SG11" in e for e in result["errors"])

    def test_nad_after_gid_fails(self):
        segs = _segs("UNH", "GID", "NAD", "UNT")
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert any("Order violation" in e for e in result["errors"])

    def test_dgs_before_gid_fails(self):
        segs = _segs("NAD", "DGS", "GID")
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert any("Hierarchy violation" in e for e in result["errors"])

    def test_all_three_violations_simultaneously(self):
        # Too many NADs (3 > max 2), wrong order (NAD at idx 2-4 after GID at idx 1),
        # hierarchy violation (DGS at idx 0 before GID at idx 1)
        segs = _segs("DGS", "GID", "NAD", "NAD", "NAD")
        result = validate_structure(segs)
        assert result["status"] == "FAIL"
        assert len(result["errors"]) >= 3

    def test_custom_rules_override_defaults(self):
        custom = {
            "SG11": {"segment": "NAD", "mandatory": True, "max": 5},
            "SG18": {"segment": "GID", "mandatory": True, "max": 2},
        }
        # 3 NAD (≤ 5 is fine), 3 GID (> 2 should fail)
        segs = _segs("NAD", "NAD", "NAD", "GID", "GID", "GID")
        result = validate_structure(segs, custom)
        assert result["status"] == "FAIL"
        assert any("SG18" in e and "maximum" in e for e in result["errors"])
        assert not any("SG11" in e and "maximum" in e for e in result["errors"])

    def test_result_always_has_required_keys(self):
        result = validate_structure([])
        assert "status" in result
        assert "errors" in result
        assert isinstance(result["errors"], list)


# ---------------------------------------------------------------------------
# validate_structure_raw  (raw EDI string entry point)
# ---------------------------------------------------------------------------

class TestValidateStructureRaw:
    def test_valid_raw_message_passes(self):
        edi = (
            "UNB+UNOA:3+S+R+200401:1000+1'"
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "BGM+610+ORD001+9'"
            "NAD+CZ+9SENDER:::91'"
            "NAD+CN+9CONSIGNEE:::91'"
            "GID+1+10:BX'"
            "UNT+6+1'"
            "UNZ+1+1'"
        )
        result = validate_structure_raw(edi)
        assert result["status"] == "PASS"

    def test_raw_message_with_dgs_passes(self):
        edi = (
            "UNB+UNOA:3+S+R+200401:1000+1'"
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "BGM+610+ORD001+9'"
            "NAD+CZ+9SENDER:::91'"
            "NAD+CN+9CONSIGNEE:::91'"
            "GID+1+10:BX'"
            "DGS+ADR+3:I+UN1090'"
            "UNT+7+1'"
            "UNZ+1+1'"
        )
        result = validate_structure_raw(edi)
        assert result["status"] == "PASS"

    def test_raw_missing_gid_fails(self):
        edi = (
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "BGM+610+ORD001+9'"
            "NAD+CZ+9SENDER:::91'"
            "UNT+3+1'"
        )
        result = validate_structure_raw(edi)
        assert result["status"] == "FAIL"
        assert any("SG18" in e for e in result["errors"])

    def test_raw_nad_after_gid_fails(self):
        edi = (
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "GID+1+10:BX'"
            "NAD+CZ+9SENDER:::91'"
            "UNT+3+1'"
        )
        result = validate_structure_raw(edi)
        assert result["status"] == "FAIL"
        assert any("Order violation" in e for e in result["errors"])

    def test_raw_dgs_before_gid_fails(self):
        edi = (
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "NAD+CZ+9SENDER:::91'"
            "DGS+ADR+3:I+UN1090'"
            "GID+1+10:BX'"
            "UNT+4+1'"
        )
        result = validate_structure_raw(edi)
        assert result["status"] == "FAIL"
        assert any("Hierarchy violation" in e for e in result["errors"])

    def test_empty_edi_string_fails(self):
        result = validate_structure_raw("")
        assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# validate_structure_to_json
# ---------------------------------------------------------------------------

class TestValidateStructureToJson:
    def test_returns_valid_json(self):
        segs = _segs("NAD", "GID")
        output = validate_structure_to_json("NAD+CZ'GID+1'")
        data = json.loads(output)
        assert "status" in data
        assert "errors" in data

    def test_json_matches_validate_structure(self):
        segs = _segs("NAD", "GID")
        edi = "NAD+X'GID+1'"
        assert json.loads(validate_structure_to_json(edi)) == validate_structure_raw(edi)

    def test_custom_indent(self):
        output = validate_structure_to_json("NAD+X'GID+1'", indent=4)
        assert '    "' in output

    def test_custom_rules_passed_through(self):
        custom = {"SG18": {"segment": "GID", "mandatory": True, "max": 1}}
        edi = "GID+1'GID+2'"   # 2 GID > max 1
        result = json.loads(validate_structure_to_json(edi, custom))
        assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# DEFAULT_RULES and _IFTMIN_HIERARCHY
# ---------------------------------------------------------------------------

class TestConstants:
    def test_default_rules_has_three_groups(self):
        assert len(DEFAULT_RULES) == 3

    def test_default_rules_contains_expected_keys(self):
        assert set(DEFAULT_RULES.keys()) == {"SG11", "SG18", "SG32"}

    def test_iftmin_hierarchy_maps_sg32_to_sg18(self):
        assert _IFTMIN_HIERARCHY["SG32"] == "SG18"
