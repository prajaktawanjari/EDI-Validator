"""
Unit tests for the UN/EDIFACT parser (edifact_parser.py).

Run with:
    python -m pytest test_edifact_parser.py -v
"""

import json
import pytest

from edifact_parser import (
    _split_raw,
    _unescape,
    _parse_element,
    _parse_segment,
    parse,
    parse_to_json,
    check_escape,
)


# ---------------------------------------------------------------------------
# _split_raw
# ---------------------------------------------------------------------------

class TestSplitRaw:
    """_split_raw splits by delimiter but PRESERVES escape sequences verbatim."""

    def test_simple_split_by_plus(self):
        assert _split_raw("A+B+C", "+") == ["A", "B", "C"]

    def test_simple_split_by_colon(self):
        assert _split_raw("1:2:3", ":") == ["1", "2", "3"]

    def test_escaped_delimiter_kept_verbatim(self):
        # ?+ is NOT a split point; the escape sequence is preserved in the token
        assert _split_raw("A?+B+C", "+") == ["A?+B", "C"]

    def test_escaped_colon_kept_verbatim(self):
        assert _split_raw("AB?:CD:EF", ":") == ["AB?:CD", "EF"]

    def test_double_escape_kept_verbatim(self):
        # ??  is preserved as-is in the token; decoding happens elsewhere
        assert _split_raw("A??B+C", "+") == ["A??B", "C"]

    def test_escaped_segment_terminator_kept_verbatim(self):
        assert _split_raw("A?'B'C", "'") == ["A?'B", "C"]

    def test_no_delimiter_present(self):
        assert _split_raw("ABCDEF", "+") == ["ABCDEF"]

    def test_empty_string(self):
        assert _split_raw("", "+") == [""]

    def test_delimiter_at_start(self):
        assert _split_raw("+A+B", "+") == ["", "A", "B"]

    def test_delimiter_at_end(self):
        assert _split_raw("A+B+", "+") == ["A", "B", ""]

    def test_consecutive_delimiters(self):
        assert _split_raw("A++B", "+") == ["A", "", "B"]


# ---------------------------------------------------------------------------
# _unescape
# ---------------------------------------------------------------------------

class TestUnescape:
    """_unescape decodes EDIFACT escape sequences in a single string."""

    def test_no_escapes(self):
        assert _unescape("HELLO") == "HELLO"

    def test_escaped_plus(self):
        assert _unescape("A?+B") == "A+B"

    def test_escaped_colon(self):
        assert _unescape("A?:B") == "A:B"

    def test_escaped_apostrophe(self):
        assert _unescape("A?'B") == "A'B"

    def test_double_escape_gives_literal_question_mark(self):
        assert _unescape("A??B") == "A?B"

    def test_escape_at_end_of_string_ignored(self):
        # A trailing lone escape char is treated as a literal (no next char).
        assert _unescape("AB?") == "AB?"

    def test_empty_string(self):
        assert _unescape("") == ""

    def test_multiple_escapes(self):
        assert _unescape("?+?:??"  ) == "+:?"


# ---------------------------------------------------------------------------
# _parse_element
# ---------------------------------------------------------------------------

class TestParseElement:
    def test_single_component_returns_string(self):
        assert _parse_element("380") == "380"

    def test_multiple_components_returns_list(self):
        assert _parse_element("137:20260408:102") == ["137", "20260408", "102"]

    def test_two_components(self):
        assert _parse_element("EUR:2") == ["EUR", "2"]

    def test_escaped_colon_not_split(self):
        # "AB?:C:D" → component 1 is "AB:C", component 2 is "D"
        assert _parse_element("AB?:C:D") == ["AB:C", "D"]

    def test_empty_component_preserved(self):
        # Leading colon → first component is empty string
        assert _parse_element(":FOO") == ["", "FOO"]

    def test_all_empty_components(self):
        assert _parse_element("::") == ["", "", ""]


# ---------------------------------------------------------------------------
# _parse_segment
# ---------------------------------------------------------------------------

class TestParseSegment:
    def test_dtm_composite_element(self):
        result = _parse_segment("DTM+137:20260408:102")
        assert result == {
            "tag": "DTM",
            "elements": [["137", "20260408", "102"]],
        }

    def test_bgm_simple_elements(self):
        result = _parse_segment("BGM+380+INV001+9")
        assert result == {
            "tag": "BGM",
            "elements": ["380", "INV001", "9"],
        }

    def test_unb_mixed_elements(self):
        result = _parse_segment("UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42")
        assert result == {
            "tag": "UNB",
            "elements": [
                ["UNOA", "3"],
                "SENDER",
                "RECEIVER",
                ["200401", "1000"],
                "42",
            ],
        }

    def test_segment_with_no_elements(self):
        result = _parse_segment("UNZ")
        assert result == {"tag": "UNZ", "elements": []}

    def test_leading_trailing_whitespace_stripped(self):
        result = _parse_segment("  BGM+380  ")
        assert result["tag"] == "BGM"

    def test_escaped_plus_in_element_value(self):
        # "LIN+1+PART?+A:IB" → element 2 is "PART+A:IB" split into ["PART+A","IB"]
        result = _parse_segment("LIN+1+PART?+A:IB")
        assert result["elements"][1] == ["PART+A", "IB"]


# ---------------------------------------------------------------------------
# parse  (full message)
# ---------------------------------------------------------------------------

class TestParse:
    def test_single_segment_with_terminator(self):
        result = parse("DTM+137:20260408:102'")
        assert result == [
            {"tag": "DTM", "elements": [["137", "20260408", "102"]]}
        ]

    def test_multiple_segments(self):
        edi = "BGM+380+INV001+9'DTM+137:20260408:102'"
        result = parse(edi)
        assert len(result) == 2
        assert result[0]["tag"] == "BGM"
        assert result[1]["tag"] == "DTM"

    def test_segment_order_preserved(self):
        edi = "UNB+X'UNH+1'BGM+380'DTM+137:20260408:102'UNZ+1+1'"
        tags = [seg["tag"] for seg in parse(edi)]
        assert tags == ["UNB", "UNH", "BGM", "DTM", "UNZ"]

    def test_escaped_segment_terminator_not_split(self):
        # ?' inside a value must NOT split the segment
        edi = "FTX+AAI++50?'s discount applies'UNZ+1+42'"
        result = parse(edi)
        assert len(result) == 2
        assert result[0]["tag"] == "FTX"
        assert result[1]["tag"] == "UNZ"
        # The apostrophe is embedded in the element value
        assert "50's discount applies" in result[0]["elements"][2]

    def test_empty_string_returns_empty_list(self):
        assert parse("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert parse("   ") == []

    def test_no_trailing_terminator(self):
        # Segment terminator is optional on the last segment
        result = parse("BGM+380+INV001")
        assert result == [{"tag": "BGM", "elements": ["380", "INV001"]}]

    def test_full_invoice_message(self):
        edi = (
            "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
            "UNH+1+INVOIC:D:96A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20260408:102'"
            "UNT+4+1'"
            "UNZ+1+42'"
        )
        result = parse(edi)
        assert len(result) == 6

        unb = result[0]
        assert unb["tag"] == "UNB"
        assert unb["elements"][0] == ["UNOA", "3"]
        assert unb["elements"][4] == "42"

        unh = result[1]
        assert unh["elements"][1] == ["INVOIC", "D", "96A", "UN"]

        dtm = result[3]
        assert dtm["elements"][0] == ["137", "20260408", "102"]

    def test_double_escape_in_element(self):
        # ?? → literal ? in the value
        edi = "FTX+AAI++100?? discount'"
        result = parse(edi)
        assert result[0]["elements"][2] == "100? discount"


# ---------------------------------------------------------------------------
# parse_to_json
# ---------------------------------------------------------------------------

class TestParseToJson:
    def test_returns_valid_json(self):
        output = parse_to_json("DTM+137:20260408:102'")
        data = json.loads(output)
        assert isinstance(data, list)
        assert data[0]["tag"] == "DTM"

    def test_json_structure_matches_parse(self):
        edi = "BGM+380+INV001'DTM+137:20260408:102'"
        assert json.loads(parse_to_json(edi)) == parse(edi)

    def test_default_indent_is_two_spaces(self):
        output = parse_to_json("BGM+380'")
        assert '  "' in output          # 2-space indent

    def test_custom_indent(self):
        output = parse_to_json("BGM+380'", indent=4)
        assert '    "' in output         # 4-space indent

    def test_empty_input_returns_empty_array(self):
        assert parse_to_json("") == "[]"


# ---------------------------------------------------------------------------
# check_escape
# ---------------------------------------------------------------------------

class TestCheckEscape:
    def test_unescaped_apostrophe_returns_error_message(self):
        result = check_escape("O'Brien")
        assert result == "Unescaped apostrophe found. Use ?'"

    def test_correctly_escaped_apostrophe_returns_none(self):
        assert check_escape("O?'Brien") is None

    def test_no_apostrophe_returns_none(self):
        assert check_escape("NoProblem") is None

    def test_empty_string_returns_none(self):
        assert check_escape("") is None

    def test_apostrophe_only_returns_error_message(self):
        assert check_escape("'") == "Unescaped apostrophe found. Use ?'"

    def test_escape_char_without_apostrophe_returns_none(self):
        # '?' present but no apostrophe — no problem
        assert check_escape("50? discount") is None

    def test_multiple_unescaped_apostrophes_returns_error_message(self):
        assert check_escape("it's a can't") == "Unescaped apostrophe found. Use ?'"

    def test_question_mark_present_with_apostrophe_returns_none(self):
        # The function considers the presence of '?' as indicative of
        # intentional escaping and does not report an error.
        assert check_escape("it?'s fine") is None
