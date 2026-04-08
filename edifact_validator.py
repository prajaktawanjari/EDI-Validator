"""
UN/EDIFACT message validator for IFTMIN messages.

Runs a fixed rule-set over a parsed EDIFACT message and returns a
structured validation result.

Rules applied
-------------
Core rules
~~~~~~~~~~
1. UNH must exist and its message-type composite must be
   ``IFTMIN:D:04A:UN:BIG14``.
2. UNT segment count (element 0) must equal the actual number of segments
   in the message (UNH … UNT inclusive).
3. UNZ (interchange trailer) must exist with at least two elements: message
   count and interchange control reference.
4. BGM document-code (element 0) must be one of ``610``, ``335``, ``730``.
5. DTM+137 (document date) must exist.

Bring-specific rules
~~~~~~~~~~~~~~~~~~~~
6. NAD+CZ (sender party) must exist.
7. NAD+CN (consignee / receiver party) must exist.
8. If any TOD segment contains qualifier ``TP``, a NAD+FP (freight payer)
   segment must also be present.
9. If any GDS segment declares cargo type ``11`` (hazardous goods), at
   least one DGS segment must exist.
10. Every DGS segment must contain a valid UN number in element 2 — the
    value must match ``UN`` followed by exactly four digits (e.g.
    ``UN1234``).

Conditional (IF/THEN) rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~
The three IF/THEN rules are:

* **IF** GDS cargo type = ``11`` (hazardous) **THEN** DGS must exist
  *(rule 9 above)*.
* **IF** any TOD carries qualifier ``TP`` **THEN** NAD+FP must exist
  *(rule 8 above)*.
* **IF** any DGS segment is present **THEN** at least one MEA segment
  (measurement — weight or volume) must also be present *(rule 11)*.

Usage
-----
    from edifact_validator import validate, validate_raw

    # From already-parsed segments:
    result = validate(segments)

    # From a raw EDI string:
    result = validate_raw(edi_string)

    # result is always:
    # {"status": "PASS" | "FAIL", "errors": [{"segment": str, "error": str, "suggestion": str}, ...]}
"""

import json
import os
import re
from typing import Union

from edifact_parser import parse


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

Segment = dict[str, Union[str, list]]
ValidationResult = dict[str, Union[str, list[dict]]]


# ---------------------------------------------------------------------------
# Error builder
# ---------------------------------------------------------------------------

def _error(segment: str, message: str, suggestion: str) -> dict:
    """Return a structured validation error dict."""
    return {"segment": segment, "error": message, "suggestion": suggestion}


# ---------------------------------------------------------------------------
# Rules config loader
# ---------------------------------------------------------------------------

RulesConfig = dict[str, Union[list[str], bool]]

_RULES_SCHEMA: dict[str, type] = {
    "mandatory_segments": list,
    "nad_required": list,
    "dgs_required_if_gds": bool,
}


def load_rules(path: str) -> RulesConfig:
    """
    Load a Bring-rules JSON file and return the validated config dict.

    Expected JSON keys (all optional — defaults apply if absent):

    * ``mandatory_segments`` *(list[str])*: segment tags that must be present.
    * ``nad_required``       *(list[str])*: NAD party qualifiers that must exist.
    * ``dgs_required_if_gds``*(bool)*:     enforce GDS↝DGS rule when True.

    Args:
        path: Filesystem path to the JSON rules file.

    Returns:
        Parsed and type-checked rules dict.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError:        If the JSON is malformed or contains wrong types.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Rules file not found: {path}")

    with open(path, encoding="utf-8") as fh:
        try:
            data: dict = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Rules file is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Rules file must contain a JSON object at the top level.")

    for key, expected_type in _RULES_SCHEMA.items():
        if key in data and not isinstance(data[key], expected_type):
            raise ValueError(
                f"Rules key '{key}' must be {expected_type.__name__}, "
                f"got {type(data[key]).__name__}."
            )

    return data

# ---------------------------------------------------------------------------
# Individual rule checkers
# ---------------------------------------------------------------------------

_EXPECTED_MSG_TYPE = ["IFTMIN", "D", "04A", "UN", "BIG14"]
_VALID_BGM_CODES = {"610", "335", "730"}
_UN_NUMBER_RE = re.compile(r"^UN\d{4}$")


def _check_unh(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 1 — UNH must exist and carry the correct message-type composite.

    UNH element layout:
        UNH + <ref> + <type>:<version>:<release>:<agency>:<association>

    Expected composite: IFTMIN:D:04A:UN:BIG14
    """
    unh_segs = [s for s in segments if s["tag"] == "UNH"]

    if not unh_segs:
        errors.append(_error(
            "UNH",
            "UNH segment is missing.",
            "Add UNH segment with message type IFTMIN:D:04A:UN:BIG14.",
        ))
        return

    unh = unh_segs[0]
    elements = unh["elements"]

    # Element index 1 holds the message-type composite
    if len(elements) < 2:
        errors.append(_error(
            "UNH",
            "UNH segment is missing the message-type element.",
            "Add message type composite IFTMIN:D:04A:UN:BIG14 as the second element of UNH.",
        ))
        return

    msg_type = elements[1]

    # Normalise: the parser returns a list for composites, str for single values
    if isinstance(msg_type, str):
        msg_type = [msg_type]

    if msg_type != _EXPECTED_MSG_TYPE:
        actual = ":".join(msg_type)
        expected = ":".join(_EXPECTED_MSG_TYPE)
        errors.append(_error(
            "UNH",
            f"UNH message type is '{actual}'; expected '{expected}'.",
            f"Change UNH message type composite to {expected}.",
        ))


def _check_unt_count(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 2 — UNT segment count must match the actual number of segments
    between UNH and UNT inclusive.

    UNT element layout:
        UNT + <segment-count> + <ref>

    EDIFACT counts every segment from UNH through to and including UNT.
    """
    # Locate UNH and UNT by index so we can count the slice they enclose.
    unh_idx = next((i for i, s in enumerate(segments) if s["tag"] == "UNH"), None)
    unt_idx = next((i for i, s in enumerate(segments) if s["tag"] == "UNT"), None)

    if unt_idx is None:
        errors.append(_error(
            "UNT",
            "UNT segment is missing.",
            "Add UNT segment with correct segment count and message reference.",
        ))
        return

    unt = segments[unt_idx]
    elements = unt["elements"]

    if not elements:
        errors.append(_error(
            "UNT",
            "UNT segment is missing the segment-count element.",
            "Add the segment count as the first element of UNT, e.g. UNT+5+1.",
        ))
        return

    try:
        declared_count = int(elements[0])
    except (ValueError, TypeError):
        errors.append(_error(
            "UNT",
            f"UNT segment count '{elements[0]}' is not a valid integer.",
            "Provide a numeric segment count, e.g. UNT+5+1.",
        ))
        return

    # Count from UNH (or the start if UNH is absent) up to and including UNT.
    start = unh_idx if unh_idx is not None else 0
    actual_count = unt_idx - start + 1  # inclusive of UNT itself

    if declared_count != actual_count:
        errors.append(_error(
            "UNT",
            f"UNT segment count is {declared_count} but "
            f"{actual_count} segment(s) were found (UNH\u2013UNT inclusive).",
            f"Update UNT count to {actual_count}.",
        ))


def _check_unz(segments: list[Segment], errors: list[dict]) -> None:
    """
    Rule 11 — UNZ (interchange trailer) must exist if UNB (interchange header) is present.

    UNZ element layout:
        UNZ + <interchange-control-count> + <interchange-control-reference>

    The UNZ segment marks the end of the interchange. If a UNB (interchange
    header) exists, then UNZ must also be present with at least two elements.
    """
    has_unb = any(s["tag"] == "UNB" for s in segments)
    
    # Only check for UNZ if UNB is present
    if not has_unb:
        return
    
    unz_segs = [s for s in segments if s["tag"] == "UNZ"]

    if not unz_segs:
        errors.append(_error(
            "UNZ",
            "Missing UNZ (interchange trailer) — UNB is present but UNZ is missing.",
            "Add UNZ segment at the end of the interchange, e.g. UNZ+1+REF123.",
        ))
        return

    unz = unz_segs[0]
    elements = unz["elements"]

    if len(elements) < 2:
        errors.append(_error(
            "UNZ",
            "UNZ is missing required elements (message count and interchange reference).",
            "Add UNZ with message count and reference, e.g. UNZ+1+REF123.",
        ))


def _check_bgm_code(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 3 — BGM document-code (element 0) must be 610, 335, or 730.

    BGM element layout:
        BGM + <document-code> + <document-number> + <message-function>
    """
    bgm_segs = [s for s in segments if s["tag"] == "BGM"]

    if not bgm_segs:
        errors.append(_error(
            "BGM",
            "BGM segment is missing.",
            "Add BGM segment with a valid document code (610, 335, or 730).",
        ))
        return

    bgm = bgm_segs[0]
    elements = bgm["elements"]

    if not elements:
        errors.append(_error(
            "BGM",
            "BGM segment is missing the document-code element.",
            "Add document code (610, 335, or 730) as the first element of BGM.",
        ))
        return

    code = elements[0]
    # Code may be a composite — take the first component only.
    if isinstance(code, list):
        code = code[0]

    if code not in _VALID_BGM_CODES:
        errors.append(_error(
            "BGM",
            f"BGM document code '{code}' is invalid; "
            f"must be one of {sorted(_VALID_BGM_CODES)}.",
            "Change BGM document code to 610, 335, or 730.",
        ))


def _check_dtm_137(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 4 — A DTM segment with qualifier 137 (document date) must exist.

    DTM element layout:
        DTM + <qualifier>:<value>:<format>
    """
    for seg in segments:
        if seg["tag"] != "DTM":
            continue
        elements = seg["elements"]
        if not elements:
            continue
        qualifier = elements[0]
        # Composite element → list; plain element → str
        if isinstance(qualifier, list):
            qualifier = qualifier[0]
        if qualifier == "137":
            return

    errors.append(_error(
        "DTM",
        "DTM+137 (document date) segment is missing.",
        "Add DTM+137 segment with the document date, e.g. DTM+137:20260408:102.",
    ))


# ---------------------------------------------------------------------------
# Bring-specific rule helpers
# ---------------------------------------------------------------------------

def _get_nad_by_qualifier(segments: list[Segment], qualifier: str) -> list[Segment]:
    """
    Return every NAD segment whose party-qualifier (element 0) equals *qualifier*.

    Handles both plain-string and composite-list representations of element 0.
    """
    result = []
    for seg in segments:
        if seg["tag"] != "NAD":
            continue
        els = seg["elements"]
        if not els:
            continue
        q = els[0]
        if isinstance(q, list):
            q = q[0]
        if q == qualifier:
            result.append(seg)
    return result


def _segment_contains_value(seg: Segment, value: str) -> bool:
    """Return True if *value* appears in any element (or component) of *seg*."""
    for el in seg["elements"]:
        values = el if isinstance(el, list) else [el]
        if value in values:
            return True
    return False


# ---------------------------------------------------------------------------
# Bring-specific rule checkers
# ---------------------------------------------------------------------------

def _check_nad_cz(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 5 — NAD+CZ (sender / consignor) must exist.

    NAD element layout:
        NAD + <party-qualifier> + <party-id-composite> + ...
    """
    if not _get_nad_by_qualifier(segments, "CZ"):
        errors.append(_error(
            "NAD",
            "NAD+CZ (sender) segment is missing.",
            "Add NAD+CZ segment identifying the message sender.",
        ))


def _check_nad_cn(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 6 — NAD+CN (consignee / receiver) must exist.
    """
    if not _get_nad_by_qualifier(segments, "CN"):
        errors.append(_error(
            "NAD",
            "NAD+CN (consignee/receiver) segment is missing.",
            "Add NAD+CN segment identifying the consignee/receiver.",
        ))


def _check_tod_fp(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 7 — If any TOD segment carries qualifier ``TP`` (freight prepaid /
    third-party payment), a NAD+FP (freight payer) segment must exist.

    TOD element layout:
        TOD + <terms-of-delivery-function-code> + <payment-conditions-code>
              + <terms-of-delivery-composite>
    """
    tod_has_tp = any(
        _segment_contains_value(seg, "TP")
        for seg in segments
        if seg["tag"] == "TOD"
    )

    if tod_has_tp and not _get_nad_by_qualifier(segments, "FP"):
        errors.append(_error(
            "NAD",
            "TOD contains qualifier 'TP' but NAD+FP (freight payer) segment is missing.",
            "Add NAD+FP segment identifying the freight payer.",
        ))


def _check_mandatory_segments(
    segments: list[Segment],
    tags: list[str],
    errors: list[dict],
) -> None:
    """
    Generic presence check — emit an error for every tag in *tags* that is
    not represented by at least one segment in *segments*.
    """
    present = {s["tag"] for s in segments}
    for tag in tags:
        if tag not in present:
            errors.append(_error(
                tag,
                f"{tag} segment is mandatory but missing.",
                f"Add a {tag} segment to the message.",
            ))


def _check_gds_dgs(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 8 — If any GDS segment declares cargo-type code ``11`` (hazardous
    goods), at least one DGS (dangerous goods) segment must be present.

    GDS element layout:
        GDS + <nature-of-cargo-composite>   →   component 0 = cargo-type code
    """
    gds_11 = False
    for seg in segments:
        if seg["tag"] != "GDS":
            continue
        els = seg["elements"]
        if not els:
            continue
        code = els[0]
        if isinstance(code, list):
            code = code[0]
        if code == "11":
            gds_11 = True
            break

    if gds_11 and not any(s["tag"] == "DGS" for s in segments):
        errors.append(_error(
            "DGS",
            "Dangerous goods indicated (GDS+11) but DGS segment missing.",
            "Add DGS segment with UN number and class.",
        ))


def _check_dgs_un_number(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 9 — Every DGS segment must contain a valid UN number at element 2.

    Valid format: ``UN`` followed by exactly four digits, e.g. ``UN1234``.

    DGS element layout:
        DGS + <dangerous-goods-regulations-code>
             + <hazard-code-composite>
             + <undg-number>
             + ...
    """
    for seg in segments:
        if seg["tag"] != "DGS":
            continue
        els = seg["elements"]
        if len(els) < 3:
            errors.append(_error(
                "DGS",
                "DGS segment is missing the UN number (expected at element index 2).",
                "Add UN number as the third element of DGS, e.g. DGS+ADR+3:I+UN1090.",
            ))
            continue
        un_num = els[2]
        if isinstance(un_num, list):
            un_num = un_num[0]
        if not _UN_NUMBER_RE.match(un_num):
            errors.append(_error(
                "DGS",
                f"DGS UN number '{un_num}' is invalid; "
                "expected 'UN' followed by 4 digits (e.g. 'UN1234').",
                "Use UN followed by exactly 4 digits, e.g. UN1090.",
            ))


def _check_dgs_mea(segments: list[Segment], errors: list[str]) -> None:
    """
    Rule 11 — IF any DGS segment is present THEN at least one MEA segment
    (measurement — weight or volume) must also exist.

    Rationale: IFTMIN dangerous-goods shipments require a declared
    measurement (e.g. gross weight or volume) so carriers can apply the
    correct handling.  A DGS without a matching MEA is structurally
    incomplete.

    MEA element layout:
        MEA + <measurement-application-qualifier>
             + <measurement-dimension-composite>
             + <measurement-value-composite>
    """
    has_dgs = any(s["tag"] == "DGS" for s in segments)
    has_mea = any(s["tag"] == "MEA" for s in segments)

    if has_dgs and not has_mea:
        errors.append(_error(
            "MEA",
            "DGS (dangerous goods) segment is present but MEA (measurement) "
            "segment is missing \u2014 weight or volume must be declared.",
            "Add MEA segment with weight or volume, e.g. MEA+WT++KGM:500.",
        ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(
    segments: list[Segment],
    rules: RulesConfig | None = None,
) -> ValidationResult:
    """
    Run all validation rules against a pre-parsed list of segments.

    When *rules* is provided (e.g. loaded via :func:`load_rules`) the
    Bring-specific checks are driven by the config rather than the
    hardcoded defaults:

    * ``mandatory_segments`` — each listed tag must be present.
    * ``nad_required``       — each listed NAD qualifier must be present.
    * ``dgs_required_if_gds``— GDS↝DGS rule is enforced only when ``True``.

    The core mechanical checks (UNH message type, UNT count, UNZ presence,
    BGM code, DTM+137, DGS UN-number format, TOD↝FP, DGS↝MEA) always run
    regardless of the rules config.

    Args:
        segments: Output of :func:`edifact_parser.parse`.
        rules:    Optional config dict from :func:`load_rules`.

    Returns:
        ``{"status": "PASS" | "FAIL", "errors": [{"segment": str, "error": str, "suggestion": str}, ...]}``
    """
    errors: list[dict] = []

    # Core rules — always enforced
    _check_unh(segments, errors)
    _check_unt_count(segments, errors)
    _check_unz(segments, errors)
    _check_bgm_code(segments, errors)
    _check_dtm_137(segments, errors)
    _check_tod_fp(segments, errors)
    _check_dgs_un_number(segments, errors)
    _check_dgs_mea(segments, errors)

    if rules is not None:
        # Config-driven Bring rules
        mandatory = rules.get("mandatory_segments", [])
        if mandatory:
            _check_mandatory_segments(segments, list(mandatory), errors)

        for qualifier in rules.get("nad_required", []):
            if not _get_nad_by_qualifier(segments, str(qualifier)):
                errors.append(_error(
                    "NAD",
                    f"NAD+{qualifier} segment is mandatory but missing.",
                    f"Add NAD+{qualifier} segment as required by the rules configuration.",
                ))

        if rules.get("dgs_required_if_gds", False):
            _check_gds_dgs(segments, errors)
    else:
        # Hardcoded Bring defaults (no rules file)
        _check_nad_cz(segments, errors)
        _check_nad_cn(segments, errors)
        _check_gds_dgs(segments, errors)

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def validate_raw(
    edi_string: str,
    rules: RulesConfig | None = None,
) -> ValidationResult:
    """
    Parse *edi_string* and run all validation rules.

    Args:
        edi_string: Raw UN/EDIFACT message string.
        rules:      Optional config dict from :func:`load_rules`.

    Returns:
        ``{"status": "PASS" | "FAIL", "errors": [{"segment": str, ...}, ...]}``
    """
    return validate(parse(edi_string), rules)


def validate_to_json(
    edi_string: str,
    rules: RulesConfig | None = None,
    indent: int = 2,
) -> str:
    """
    Parse and validate *edi_string*, returning the result as a JSON string.

    Args:
        edi_string: Raw UN/EDIFACT message string.
        rules:      Optional config dict from :func:`load_rules`.
        indent:     JSON indentation spaces (default ``2``).

    Returns:
        JSON-encoded validation result.
    """
    return json.dumps(validate_raw(edi_string, rules), indent=indent)


# ---------------------------------------------------------------------------
# CLI / quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    VALID_MSG = (
        "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
        "UNH+1+IFTMIN:D:04A:UN:BIG14'"
        "BGM+610+SHIPORDER001+9'"
        "DTM+137:20260408:102'"
        "NAD+CZ+9SENDER:::91'"
        "NAD+CN+9CONSIGNEE:::91'"
        "UNT+6+1'"
        "UNZ+1+42'"
    )

    print("--- Valid message ---")
    print(validate_to_json(VALID_MSG))

    HAZMAT_MSG = (
        "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
        "UNH+1+IFTMIN:D:04A:UN:BIG14'"
        "BGM+610+SHIPORDER001+9'"
        "DTM+137:20260408:102'"
        "NAD+CZ+9SENDER:::91'"
        "NAD+CN+9CONSIGNEE:::91'"
        "TOD+6+TP'"
        "NAD+FP+9FREIGHTPAYER:::91'"
        "GDS+11'"
        "DGS+ADR+3:I+UN1090'"
        "UNT+10+1'"
        "UNZ+1+42'"
    )

    print("\n--- Hazmat message (valid) ---")
    print(validate_to_json(HAZMAT_MSG))

    INVALID_MSG = (
        "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
        "UNH+1+IFTMIN:D:04A:UN:BIG14'"
        "BGM+999+BADORDER+9'"
        "GDS+11'"
        "TOD+6+TP'"
        "UNT+5+1'"
        "UNZ+1+42'"
    )

    print("\n--- Invalid message ---")
    print(validate_to_json(INVALID_MSG))
