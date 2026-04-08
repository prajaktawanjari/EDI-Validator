"""
Unit tests for edifact_validator.py.

Run with:
    python -m pytest test_edifact_validator.py -v
"""

import json
import pytest

from edifact_parser import parse
from edifact_validator import (
    validate,
    validate_raw,
    validate_to_json,
    load_rules,
    _check_unh,
    _check_unt_count,
    _check_unz,
    _check_bgm_code,
    _check_dtm_137,
    _check_nad_cz,
    _check_nad_cn,
    _check_tod_fp,
    _check_gds_dgs,
    _check_dgs_un_number,
    _check_dgs_mea,
    _check_mandatory_segments,
    _get_nad_by_qualifier,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_message(
    unh="UNH+1+IFTMIN:D:04A:UN:BIG14'",
    bgm="BGM+610+ORD001+9'",
    dtm="DTM+137:20260408:102'",
    nad_cz="NAD+CZ+9SENDER:::91'",
    nad_cn="NAD+CN+9CONSIGNEE:::91'",
    extra="",
    unt_override: str | None = None,
) -> str:
    """
    Build a minimal but structurally valid IFTMIN message.

    Segment count for UNT is calculated automatically unless *unt_override*
    is supplied.
    """
    body_segments = []
    if unh:
        body_segments.append(unh)
    if bgm:
        body_segments.append(bgm)
    if dtm:
        body_segments.append(dtm)
    if nad_cz:
        body_segments.append(nad_cz)
    if nad_cn:
        body_segments.append(nad_cn)
    if extra:
        body_segments.append(extra)

    # Count the actual number of segments across all body pieces (handles
    # multi-segment extras where a single string contains multiple ' terminators).
    body_text = "".join(body_segments)
    actual_seg_count = len([s for s in body_text.split("'") if s.strip()])
    auto_count = actual_seg_count + 1  # +1 for UNT itself
    unt_count = unt_override if unt_override is not None else str(auto_count)
    unt = f"UNT+{unt_count}+1'"

    return (
        "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
        + "".join(body_segments)
        + unt
        + "UNZ+1+42'"
    )


# ---------------------------------------------------------------------------
# Full message happy path
# ---------------------------------------------------------------------------

class TestValidateHappyPath:
    def test_valid_message_returns_pass(self):
        result = validate_raw(_make_message())
        assert result["status"] == "PASS"
        assert result["errors"] == []

    def test_bgm_code_335_is_valid(self):
        result = validate_raw(_make_message(bgm="BGM+335+ORD001+9'"))
        assert result["status"] == "PASS"

    def test_bgm_code_730_is_valid(self):
        result = validate_raw(_make_message(bgm="BGM+730+ORD001+9'"))
        assert result["status"] == "PASS"

    def test_validate_to_json_returns_valid_json(self):
        output = validate_to_json(_make_message())
        data = json.loads(output)
        assert data["status"] == "PASS"
        assert data["errors"] == []

    def test_validate_accepts_pre_parsed_segments(self):
        segments = parse(_make_message())
        result = validate(segments)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 1 — UNH checks
# ---------------------------------------------------------------------------

class TestCheckUnh:
    def test_missing_unh_adds_error(self):
        errors: list[dict] = []
        _check_unh([], errors)
        assert any("UNH segment is missing" in e["error"] for e in errors)

    def test_unh_without_message_type_element(self):
        segs = [{"tag": "UNH", "elements": ["1"]}]
        errors: list[dict] = []
        _check_unh(segs, errors)
        assert any("missing the message-type element" in e["error"] for e in errors)

    def test_wrong_message_type_composite(self):
        segs = [{"tag": "UNH", "elements": ["1", ["INVOIC", "D", "96A", "UN"]]}]
        errors: list[dict] = []
        _check_unh(segs, errors)
        assert any("INVOIC" in e["error"] for e in errors)

    def test_correct_message_type_no_error(self):
        segs = [{"tag": "UNH", "elements": ["1", ["IFTMIN", "D", "04A", "UN", "BIG14"]]}]
        errors: list[dict] = []
        _check_unh(segs, errors)
        assert errors == []

    def test_scalar_message_type_treated_as_list(self):
        # Parser returns a plain string for a single-component element
        segs = [{"tag": "UNH", "elements": ["1", "IFTMIN"]}]
        errors: list[dict] = []
        _check_unh(segs, errors)
        # "IFTMIN" alone ≠ full composite → error
        assert errors != []

    def test_full_message_wrong_unh_fails(self):
        msg = _make_message(unh="UNH+1+INVOIC:D:96A:UN'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("UNH" in e["error"] for e in result["errors"])

    def test_full_message_missing_unh_fails(self):
        msg = _make_message(unh="")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("UNH" in e["error"] for e in result["errors"])


# ---------------------------------------------------------------------------
# Rule 2 — UNT segment count
# ---------------------------------------------------------------------------

class TestCheckUntCount:
    def test_missing_unt_adds_error(self):
        errors: list[dict] = []
        _check_unt_count([], errors)
        assert any("UNT segment is missing" in e["error"] for e in errors)

    def test_unt_missing_count_element(self):
        segs = [{"tag": "UNT", "elements": []}]
        errors: list[dict] = []
        _check_unt_count(segs, errors)
        assert any("missing the segment-count" in e["error"] for e in errors)

    def test_unt_non_integer_count(self):
        segs = [{"tag": "UNT", "elements": ["FOUR"]}]
        errors: list[dict] = []
        _check_unt_count(segs, errors)
        assert any("not a valid integer" in e["error"] for e in errors)

    def test_correct_count_no_error(self):
        # UNH + UNT = 2 segments; UNT declares 2
        segs = [
            {"tag": "UNH", "elements": ["1", ["IFTMIN", "D", "04A", "UN", "BIG14"]]},
            {"tag": "UNT", "elements": ["2", "1"]},
        ]
        errors: list[dict] = []
        _check_unt_count(segs, errors)
        assert errors == []

    def test_wrong_count_adds_error(self):
        segs = [
            {"tag": "UNH", "elements": ["1", ["IFTMIN", "D", "04A", "UN", "BIG14"]]},
            {"tag": "BGM", "elements": ["610", "ORD", "9"]},
            {"tag": "UNT", "elements": ["9", "1"]},   # wrong: should be 3
        ]
        errors: list[dict] = []
        _check_unt_count(segs, errors)
        assert any("segment count" in e["error"] for e in errors)

    def test_full_message_wrong_unt_count_fails(self):
        msg = _make_message(unt_override="99")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("UNT" in e["error"] for e in result["errors"])

    def test_full_message_correct_unt_count_passes(self):
        result = validate_raw(_make_message())
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 11 — UNZ interchange trailer
# ---------------------------------------------------------------------------

class TestCheckUnz:
    def test_missing_unz_no_unb_no_error(self):
        # If no UNB, UNZ is not required
        errors: list[dict] = []
        _check_unz([], errors)
        assert errors == []

    def test_missing_unz_with_unb_adds_error(self):
        segs = [{"tag": "UNB", "elements": ["UNOA:3", "SENDER", "RECEIVER"]}]
        errors: list[dict] = []
        _check_unz(segs, errors)
        assert any("Missing UNZ" in e["error"] for e in errors)
        assert any("UNB is present but UNZ is missing" in e["error"] for e in errors)

    def test_unz_with_no_elements_adds_error(self):
        segs = [
            {"tag": "UNB", "elements": ["UNOA:3", "SENDER", "RECEIVER"]},
            {"tag": "UNZ", "elements": []}
        ]
        errors: list[dict] = []
        _check_unz(segs, errors)
        assert any("missing required elements" in e["error"] for e in errors)

    def test_unz_with_one_element_adds_error(self):
        segs = [
            {"tag": "UNB", "elements": ["UNOA:3", "SENDER", "RECEIVER"]},
            {"tag": "UNZ", "elements": ["1"]}
        ]
        errors: list[dict] = []
        _check_unz(segs, errors)
        assert any("missing required elements" in e["error"] for e in errors)

    def test_unz_with_two_elements_no_error(self):
        segs = [
            {"tag": "UNB", "elements": ["UNOA:3", "SENDER", "RECEIVER"]},
            {"tag": "UNZ", "elements": ["1", "REF123"]}
        ]
        errors: list[dict] = []
        _check_unz(segs, errors)
        assert errors == []

    def test_no_unb_no_unz_no_error(self):
        # Message without UNB doesn't need UNZ
        segs = [
            {"tag": "UNH", "elements": ["1", ["IFTMIN", "D", "04A", "UN", "BIG14"]]},
            {"tag": "BGM", "elements": ["610", "ORD001", "9"]},
            {"tag": "UNT", "elements": ["3", "1"]}
        ]
        errors: list[dict] = []
        _check_unz(segs, errors)
        assert errors == []

    def test_full_message_without_unz_fails(self):
        # Build message with UNB but without UNZ
        msg = (
            "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
            "UNH+1+IFTMIN:D:04A:UN:BIG14'"
            "BGM+610+ORD001+9'"
            "DTM+137:20260408:102'"
            "NAD+CZ+9SENDER:::91'"
            "NAD+CN+9CONSIGNEE:::91'"
            "UNT+6+1'"
        )
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("UNZ" in e["error"] for e in result["errors"])

    def test_full_message_with_valid_unz_passes(self):
        result = validate_raw(_make_message())
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 3 — BGM document code
# ---------------------------------------------------------------------------

class TestCheckBgmCode:
    def test_missing_bgm_adds_error(self):
        errors: list[dict] = []
        _check_bgm_code([], errors)
        assert any("BGM segment is missing" in e["error"] for e in errors)

    def test_bgm_without_elements_adds_error(self):
        segs = [{"tag": "BGM", "elements": []}]
        errors: list[dict] = []
        _check_bgm_code(segs, errors)
        assert any("missing the document-code" in e["error"] for e in errors)

    def test_invalid_code_adds_error(self):
        segs = [{"tag": "BGM", "elements": ["999"]}]
        errors: list[dict] = []
        _check_bgm_code(segs, errors)
        assert any("999" in e["error"] for e in errors)

    @pytest.mark.parametrize("code", ["610", "335", "730"])
    def test_valid_codes_no_error(self, code):
        segs = [{"tag": "BGM", "elements": [code, "ORD001", "9"]}]
        errors: list[dict] = []
        _check_bgm_code(segs, errors)
        assert errors == []

    def test_composite_code_first_component_used(self):
        # Parser may return code as composite list
        segs = [{"tag": "BGM", "elements": [["610", "2"], "ORD001"]}]
        errors: list[dict] = []
        _check_bgm_code(segs, errors)
        assert errors == []

    def test_full_message_invalid_bgm_fails(self):
        msg = _make_message(bgm="BGM+999+ORD001+9'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("BGM" in e["error"] for e in result["errors"])


# ---------------------------------------------------------------------------
# Rule 4 — DTM+137
# ---------------------------------------------------------------------------

class TestCheckDtm137:
    def test_no_dtm_at_all_adds_error(self):
        errors: list[dict] = []
        _check_dtm_137([], errors)
        assert any("DTM+137" in e["error"] for e in errors)

    def test_dtm_with_different_qualifier_adds_error(self):
        segs = [{"tag": "DTM", "elements": [["63", "20260408", "102"]]}]
        errors: list[dict] = []
        _check_dtm_137(segs, errors)
        assert any("DTM+137" in e["error"] for e in errors)

    def test_dtm_137_composite_no_error(self):
        segs = [{"tag": "DTM", "elements": [["137", "20260408", "102"]]}]
        errors: list[dict] = []
        _check_dtm_137(segs, errors)
        assert errors == []

    def test_dtm_137_plain_string_no_error(self):
        segs = [{"tag": "DTM", "elements": ["137"]}]
        errors: list[dict] = []
        _check_dtm_137(segs, errors)
        assert errors == []

    def test_multiple_dtm_one_is_137(self):
        segs = [
            {"tag": "DTM", "elements": [["63", "20260408", "102"]]},
            {"tag": "DTM", "elements": [["137", "20260408", "102"]]},
        ]
        errors: list[dict] = []
        _check_dtm_137(segs, errors)
        assert errors == []

    def test_full_message_missing_dtm_fails(self):
        msg = _make_message(dtm="")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("DTM+137" in e["error"] for e in result["errors"])


# ---------------------------------------------------------------------------
# Multiple simultaneous errors
# ---------------------------------------------------------------------------

class TestMultipleErrors:
    def test_core_rules_can_fail_simultaneously(self):
        # UNH wrong type, BGM wrong code, no DTM, UNT wrong count,
        # plus no NAD+CZ / NAD+CN → 6 errors
        msg = (
            "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
            "UNH+1+INVOIC:D:96A:UN'"
            "BGM+999+ORD001+9'"
            "UNT+99+1'"
            "UNZ+1+42'"
        )
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert len(result["errors"]) == 6  # UNH + UNT + BGM + DTM + NAD+CZ + NAD+CN

    def test_result_always_has_status_and_errors_keys(self):
        result = validate_raw("")
        assert "status" in result
        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_empty_message_fails_all_rules(self):
        result = validate_raw("")
        assert result["status"] == "FAIL"
        assert len(result["errors"]) >= 6


# ---------------------------------------------------------------------------
# Rule 5 — NAD+CZ (sender mandatory)
# ---------------------------------------------------------------------------

class TestCheckNadCz:
    def test_missing_nad_cz_adds_error(self):
        errors: list[dict] = []
        _check_nad_cz([], errors)
        assert any("NAD+CZ" in e["error"] for e in errors)

    def test_nad_with_wrong_qualifier_adds_error(self):
        segs = [{"tag": "NAD", "elements": ["CN", "9FOO:::91"]}]
        errors: list[dict] = []
        _check_nad_cz(segs, errors)
        assert any("NAD+CZ" in e["error"] for e in errors)

    def test_nad_cz_present_no_error(self):
        segs = [{"tag": "NAD", "elements": ["CZ", "9SENDER:::91"]}]
        errors: list[dict] = []
        _check_nad_cz(segs, errors)
        assert errors == []

    def test_composite_qualifier_resolved(self):
        segs = [{"tag": "NAD", "elements": [["CZ"], "9SENDER:::91"]}]
        errors: list[dict] = []
        _check_nad_cz(segs, errors)
        assert errors == []

    def test_full_message_missing_nad_cz_fails(self):
        msg = _make_message(nad_cz="")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("NAD+CZ" in e["error"] for e in result["errors"])

    def test_full_message_with_nad_cz_passes(self):
        result = validate_raw(_make_message())
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 6 — NAD+CN (receiver mandatory)
# ---------------------------------------------------------------------------

class TestCheckNadCn:
    def test_missing_nad_cn_adds_error(self):
        errors: list[dict] = []
        _check_nad_cn([], errors)
        assert any("NAD+CN" in e["error"] for e in errors)

    def test_nad_with_wrong_qualifier_adds_error(self):
        segs = [{"tag": "NAD", "elements": ["CZ", "9FOO:::91"]}]
        errors: list[dict] = []
        _check_nad_cn(segs, errors)
        assert any("NAD+CN" in e["error"] for e in errors)

    def test_nad_cn_present_no_error(self):
        segs = [{"tag": "NAD", "elements": ["CN", "9CONSIGNEE:::91"]}]
        errors: list[dict] = []
        _check_nad_cn(segs, errors)
        assert errors == []

    def test_full_message_missing_nad_cn_fails(self):
        msg = _make_message(nad_cn="")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("NAD+CN" in e["error"] for e in result["errors"])

    def test_get_nad_by_qualifier_returns_correct_segments(self):
        segs = [
            {"tag": "NAD", "elements": ["CZ", "9A"]},
            {"tag": "NAD", "elements": ["CN", "9B"]},
            {"tag": "NAD", "elements": ["CN", "9C"]},
        ]
        assert len(_get_nad_by_qualifier(segs, "CN")) == 2
        assert len(_get_nad_by_qualifier(segs, "CZ")) == 1
        assert len(_get_nad_by_qualifier(segs, "FP")) == 0


# ---------------------------------------------------------------------------
# Rule 7 — TOD with TP requires NAD+FP
# ---------------------------------------------------------------------------

class TestCheckTodFp:
    def test_no_tod_no_error(self):
        errors: list[dict] = []
        _check_tod_fp([], errors)
        assert errors == []

    def test_tod_without_tp_no_error(self):
        segs = [{"tag": "TOD", "elements": ["6", "CFR"]}]
        errors: list[dict] = []
        _check_tod_fp(segs, errors)
        assert errors == []

    def test_tod_with_tp_missing_nad_fp_adds_error(self):
        segs = [{"tag": "TOD", "elements": ["6", "TP"]}]
        errors: list[dict] = []
        _check_tod_fp(segs, errors)
        assert any("NAD+FP" in e["error"] for e in errors)

    def test_tod_with_tp_and_nad_fp_no_error(self):
        segs = [
            {"tag": "TOD", "elements": ["6", "TP"]},
            {"tag": "NAD", "elements": ["FP", "9PAYER:::91"]},
        ]
        errors: list[dict] = []
        _check_tod_fp(segs, errors)
        assert errors == []

    def test_tp_in_composite_element_detected(self):
        segs = [{"tag": "TOD", "elements": [["6", "TP"]]}]
        errors: list[dict] = []
        _check_tod_fp(segs, errors)
        assert any("NAD+FP" in e["error"] for e in errors)

    def test_full_message_tod_tp_without_fp_fails(self):
        msg = _make_message(extra="TOD+6+TP'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("NAD+FP" in e["error"] for e in result["errors"])

    def test_full_message_tod_tp_with_fp_passes(self):
        msg = _make_message(extra="TOD+6+TP'NAD+FP+9PAYER:::91'")
        result = validate_raw(msg)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 8 — GDS=11 requires DGS
# ---------------------------------------------------------------------------

class TestCheckGdsDgs:
    def test_no_gds_no_error(self):
        errors: list[dict] = []
        _check_gds_dgs([], errors)
        assert errors == []

    def test_gds_non_11_no_error(self):
        segs = [{"tag": "GDS", "elements": ["7"]}]
        errors: list[dict] = []
        _check_gds_dgs(segs, errors)
        assert errors == []

    def test_gds_11_without_dgs_adds_error(self):
        segs = [{"tag": "GDS", "elements": ["11"]}]
        errors: list[dict] = []
        _check_gds_dgs(segs, errors)
        assert any("DGS" in e["error"] for e in errors)

    def test_gds_dgs_error_has_correct_structure(self):
        segs = [{"tag": "GDS", "elements": ["11"]}]
        errors: list[dict] = []
        _check_gds_dgs(segs, errors)
        assert len(errors) == 1
        err = errors[0]
        assert err["segment"] == "DGS"
        assert err["error"] == "Dangerous goods indicated (GDS+11) but DGS segment missing."
        assert err["suggestion"] == "Add DGS segment with UN number and class."

    def test_gds_11_with_dgs_no_error(self):
        segs = [
            {"tag": "GDS", "elements": ["11"]},
            {"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN1090"]},
        ]
        errors: list[dict] = []
        _check_gds_dgs(segs, errors)
        assert errors == []

    def test_gds_11_as_composite_detected(self):
        segs = [{"tag": "GDS", "elements": [["11", "HG"]]}]
        errors: list[dict] = []
        _check_gds_dgs(segs, errors)
        assert any("DGS" in e["error"] for e in errors)

    def test_full_message_gds_11_no_dgs_fails(self):
        msg = _make_message(extra="GDS+11'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any(e["segment"] == "DGS" for e in result["errors"])

    def test_full_message_gds_11_with_dgs_passes(self):
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'MEA+WT++KGM:500'")
        result = validate_raw(msg)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 9 — DGS UN number format
# ---------------------------------------------------------------------------

class TestCheckDgsUnNumber:
    def test_no_dgs_no_error(self):
        errors: list[dict] = []
        _check_dgs_un_number([], errors)
        assert errors == []

    def test_valid_un_number_no_error(self):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN1090"]}]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert errors == []

    def test_valid_un_number_0001_no_error(self):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN0001"]}]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert errors == []

    def test_missing_un_element_adds_error(self):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"]]}]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert any("missing" in e["error"] for e in errors)

    @pytest.mark.parametrize("bad", [
        "1090",        # missing UN prefix
        "UN109",       # only 3 digits
        "UN10900",     # 5 digits
        "un1090",      # lowercase
        "UN 1090",     # space
        "UNABC1",      # letters instead of digits
        "",            # empty string
    ])
    def test_invalid_un_number_formats_add_error(self, bad):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"], bad]}]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert any(bad in e["error"] or "invalid" in e["error"] for e in errors)

    def test_un_number_as_composite_first_component_used(self):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"], ["UN1090", "extra"]]}]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert errors == []

    def test_multiple_dgs_first_invalid_second_valid_both_reported(self):
        segs = [
            {"tag": "DGS", "elements": ["ADR", ["3", "I"], "BADFMT"]},
            {"tag": "DGS", "elements": ["ADR", ["6", "II"], "UN3077"]},
        ]
        errors: list[dict] = []
        _check_dgs_un_number(segs, errors)
        assert len(errors) == 1  # only the first DGS is invalid

    def test_full_message_invalid_un_number_fails(self):
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+1090'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("UN number" in e["error"] for e in result["errors"])

    def test_full_message_valid_un_number_passes(self):
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'MEA+WT++KGM:500'")
        result = validate_raw(msg)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Rule 10 — DGS → MEA required
# ---------------------------------------------------------------------------

class TestCheckDgsMea:
    def test_no_dgs_no_error(self):
        errors: list[dict] = []
        _check_dgs_mea([], errors)
        assert errors == []

    def test_dgs_with_mea_no_error(self):
        segs = [
            {"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN1090"]},
            {"tag": "MEA", "elements": ["WT", "", ["KGM", "500"]]},
        ]
        errors: list[dict] = []
        _check_dgs_mea(segs, errors)
        assert errors == []

    def test_dgs_without_mea_adds_error(self):
        segs = [{"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN1090"]}]
        errors: list[dict] = []
        _check_dgs_mea(segs, errors)
        assert any("MEA" in e["error"] for e in errors)

    def test_multiple_dgs_one_mea_is_sufficient(self):
        segs = [
            {"tag": "DGS", "elements": ["ADR", ["3", "I"], "UN1090"]},
            {"tag": "DGS", "elements": ["ADR", ["6", "II"], "UN3077"]},
            {"tag": "MEA", "elements": ["WT", "", ["KGM", "500"]]},
        ]
        errors: list[dict] = []
        _check_dgs_mea(segs, errors)
        assert errors == []

    def test_mea_without_dgs_no_error(self):
        # MEA for non-hazmat shipment is allowed without DGS
        segs = [{"tag": "MEA", "elements": ["WT", "", ["KGM", "1000"]]}]
        errors: list[dict] = []
        _check_dgs_mea(segs, errors)
        assert errors == []

    def test_full_message_dgs_without_mea_fails(self):
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("MEA" in e["error"] for e in result["errors"])

    def test_full_message_dgs_with_mea_passes(self):
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'MEA+WT++KGM:500'")
        result = validate_raw(msg)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# All three IF/THEN conditional rules together
# ---------------------------------------------------------------------------

class TestConditionalRulesIntegration:
    """Verify the three IF/THEN rules fire (or don't) as a group."""

    def test_all_three_conditions_met_correctly(self):
        # GDS+11 → DGS present; TOD+TP → NAD+FP present; DGS → MEA present
        msg = _make_message(
            extra="GDS+11'TOD+6+TP'NAD+FP+9PAYER:::91'DGS+ADR+3:I+UN1090'MEA+WT++KGM:500'"
        )
        result = validate_raw(msg)
        assert result["status"] == "PASS"
        assert result["errors"] == []

    def test_all_three_conditions_violated(self):
        # GDS+11 but no DGS; TOD+TP but no NAD+FP; (DGS absent so MEA rule silent)
        msg = _make_message(extra="GDS+11'TOD+6+TP'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        failing = result["errors"]
        assert any("DGS" in e["error"] and "missing" in e["error"] for e in failing)
        assert any("NAD+FP" in e["error"] for e in failing)

    def test_dgs_present_but_mea_missing_fails(self):
        # DGS without MEA specifically — GDS→DGS rule must NOT fire (DGS is there)
        msg = _make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'")
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("MEA" in e["error"] for e in result["errors"])
        # The GDS→DGS error says "requires a DGS segment"; that must NOT appear
        assert not any("requires a DGS" in e["error"] for e in result["errors"])

    def test_tod_tp_without_fp_and_dgs_without_mea_both_fail(self):
        msg = _make_message(
            extra="GDS+11'TOD+6+TP'DGS+ADR+3:I+UN1090'"
        )
        result = validate_raw(msg)
        assert result["status"] == "FAIL"
        assert any("NAD+FP" in e["error"] for e in result["errors"])
        assert any("MEA" in e["error"] for e in result["errors"])

    def test_no_hazmat_segments_no_conditional_errors(self):
        # Plain shipment: no GDS/11, no TOD+TP, no DGS — no conditional errors
        result = validate_raw(_make_message())
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Tests for _check_mandatory_segments
# ---------------------------------------------------------------------------

class TestCheckMandatorySegments:
    def test_all_present_no_error(self):
        segs = [
            {"tag": "UNH", "elements": []},
            {"tag": "BGM", "elements": []},
            {"tag": "DTM", "elements": []},
        ]
        errors: list[dict] = []
        _check_mandatory_segments(segs, ["UNH", "BGM", "DTM"], errors)
        assert errors == []

    def test_one_missing_adds_error(self):
        segs = [{"tag": "UNH", "elements": []}, {"tag": "BGM", "elements": []}]
        errors: list[dict] = []
        _check_mandatory_segments(segs, ["UNH", "BGM", "CNT"], errors)
        assert len(errors) == 1
        assert errors[0]["segment"] == "CNT"
        assert "CNT" in errors[0]["error"]

    def test_multiple_missing_adds_multiple_errors(self):
        errors: list[dict] = []
        _check_mandatory_segments([], ["UNH", "BGM", "DTM"], errors)
        assert len(errors) == 3

    def test_empty_tag_list_no_error(self):
        segs = [{"tag": "UNH", "elements": []}]
        errors: list[dict] = []
        _check_mandatory_segments(segs, [], errors)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests for load_rules
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_loads_valid_json(self, tmp_path):
        rules_file = tmp_path / "bring_rules.json"
        rules_file.write_text(
            '{"mandatory_segments": ["UNH", "CNT"], "nad_required": ["CZ"], "dgs_required_if_gds": true}',
            encoding="utf-8",
        )
        rules = load_rules(str(rules_file))
        assert rules["mandatory_segments"] == ["UNH", "CNT"]
        assert rules["nad_required"] == ["CZ"]
        assert rules["dgs_required_if_gds"] is True

    def test_missing_file_raises_file_not_found(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_rules(str(tmp_path / "nonexistent.json"))

    def test_malformed_json_raises_value_error(self, tmp_path):
        rules_file = tmp_path / "bad.json"
        rules_file.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            load_rules(str(rules_file))

    def test_non_object_root_raises_value_error(self, tmp_path):
        rules_file = tmp_path / "bad.json"
        rules_file.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            load_rules(str(rules_file))

    def test_wrong_type_for_key_raises_value_error(self, tmp_path):
        rules_file = tmp_path / "bad.json"
        rules_file.write_text('{"mandatory_segments": "UNH"}', encoding="utf-8")
        with pytest.raises(ValueError, match="mandatory_segments"):
            load_rules(str(rules_file))

    def test_partial_config_is_accepted(self, tmp_path):
        rules_file = tmp_path / "partial.json"
        rules_file.write_text('{"nad_required": ["CN"]}', encoding="utf-8")
        rules = load_rules(str(rules_file))
        assert rules["nad_required"] == ["CN"]
        assert "mandatory_segments" not in rules


# ---------------------------------------------------------------------------
# Tests for config-driven validate()
# ---------------------------------------------------------------------------

class TestValidateWithRules:
    """Verify that passing a rules dict changes which checks are applied."""

    def _base_segs(self, extra_tags: list[str] | None = None):
        """Return minimal valid segments; optionally inject extra bare tags."""
        segs = _make_message(
            extra="".join(f"{t}+1'" for t in (extra_tags or []))
        )
        return parse(segs)

    # --- mandatory_segments -------------------------------------------------

    def test_mandatory_segment_missing_adds_error(self):
        rules = {"mandatory_segments": ["CNT"], "nad_required": [], "dgs_required_if_gds": False}
        segs = parse(_make_message())
        result = validate(segs, rules)
        assert any("CNT" in e["error"] for e in result["errors"])

    def test_mandatory_segment_present_no_error(self):
        rules = {"mandatory_segments": ["BGM"], "nad_required": [], "dgs_required_if_gds": False}
        segs = parse(_make_message())
        result = validate(segs, rules)
        assert not any("BGM" in e["error"] and "mandatory but missing" in e["error"] for e in result["errors"])

    # --- nad_required -------------------------------------------------------

    def test_nad_required_qualifier_missing_adds_error(self):
        rules = {"mandatory_segments": [], "nad_required": ["SH"], "dgs_required_if_gds": False}
        segs = parse(_make_message())
        result = validate(segs, rules)
        assert any("NAD+SH" in e["error"] for e in result["errors"])

    def test_nad_required_qualifier_present_no_error(self):
        rules = {"mandatory_segments": [], "nad_required": ["CZ"], "dgs_required_if_gds": False}
        segs = parse(_make_message())
        result = validate(segs, rules)
        assert not any("NAD+CZ" in e["error"] and "mandatory" in e["error"] for e in result["errors"])

    def test_nad_required_multiple_one_missing(self):
        rules = {"mandatory_segments": [], "nad_required": ["CZ", "FP"], "dgs_required_if_gds": False}
        segs = parse(_make_message())
        result = validate(segs, rules)
        # CZ present → no error; FP absent → error
        assert any("NAD+FP" in e["error"] for e in result["errors"])
        assert not any("NAD+CZ" in e["error"] and "mandatory" in e["error"] for e in result["errors"])

    # --- dgs_required_if_gds ------------------------------------------------

    def test_gds_rule_disabled_no_dgs_error(self):
        rules = {"mandatory_segments": [], "nad_required": [], "dgs_required_if_gds": False}
        segs = parse(_make_message(extra="GDS+11'"))
        result = validate(segs, rules)
        # GDS→DGS rule is off; no DGS error
        assert not any(
            "Dangerous goods" in e["error"] for e in result["errors"]
        )

    def test_gds_rule_enabled_no_dgs_segment_adds_error(self):
        rules = {"mandatory_segments": [], "nad_required": [], "dgs_required_if_gds": True}
        segs = parse(_make_message(extra="GDS+11'"))
        result = validate(segs, rules)
        assert any("Dangerous goods" in e["error"] for e in result["errors"])

    def test_gds_rule_enabled_dgs_present_no_error(self):
        rules = {"mandatory_segments": [], "nad_required": [], "dgs_required_if_gds": True}
        segs = parse(_make_message(extra="GDS+11'DGS+ADR+3:I+UN1090'MEA+WT++KGM:500'"))
        result = validate(segs, rules)
        assert not any("Dangerous goods" in e["error"] for e in result["errors"])

    # --- bring_rules.json round-trip ----------------------------------------

    def test_bring_rules_json_file_drives_validate(self, tmp_path):
        """Loading the actual bring_rules.json produces the expected errors."""
        import json as _json
        rules_file = tmp_path / "bring_rules.json"
        rules_file.write_text(
            _json.dumps({
                "mandatory_segments": ["UNH", "BGM", "DTM", "CNT"],
                "nad_required": ["CZ", "CN"],
                "dgs_required_if_gds": True,
            }),
            encoding="utf-8",
        )
        rules = load_rules(str(rules_file))
        # Message without CNT → CNT error expected
        segs = parse(_make_message())
        result = validate(segs, rules)
        assert any("CNT" in e["error"] for e in result["errors"])
