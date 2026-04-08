"""
UN/EDIFACT IFTMIN segment group structure validator.

Validates three structural properties of a parsed EDIFACT message:

1. **Mandatory / max occurrences** — mandatory groups must appear at least
   once; no group may exceed its declared maximum occurrence count.

2. **Correct order** — top-level segment groups must appear in ascending
   schema order (derived from the SG number).  Once a higher-ordered group
   has started, a lower-ordered group must not appear again.

3. **Segment group hierarchy** — child group segments (e.g. DGS / SG32
   inside GID / SG18) must only appear after their parent group trigger has
   been seen at least once.

Default rules (can be overridden via *rules_dict*):

    SG11  NAD  mandatory  max 2      (top-level)
    SG18  GID  mandatory  max 999    (top-level)
    SG32  DGS  conditional           (child of SG18)

IFTMIN hierarchy is encoded in ``_IFTMIN_HIERARCHY``.  Pass an explicit
``"parent"`` key in a custom rule to override.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, Union

from edifact_parser import parse


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Segment = dict[str, Union[str, list]]
ValidationResult = dict[str, Union[str, list[str]]]


# ---------------------------------------------------------------------------
# Schema data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SegmentGroupRule:
    """Describes one segment group in an IFTMIN message structure."""
    name: str                 # e.g. "SG11"
    segment: str              # trigger segment tag, e.g. "NAD"
    mandatory: bool           # must appear at least once when True
    max_occur: Optional[int]  # None = unlimited
    parent: Optional[str]     # parent SG name; None = top-level
    order: int                # sort key (numeric part of SG name)


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

_SG_NUMBER_RE = re.compile(r"SG(\d+)", re.IGNORECASE)

# IFTMIN-specific hierarchy: maps child SG name → parent SG name.
# Extend this dict to model deeper nesting.
_IFTMIN_HIERARCHY: dict[str, str] = {
    "SG32": "SG18",   # DGS goods-item dangerous-goods is inside GID goods-item
}


def _sg_order(name: str) -> int:
    """Return the numeric part of an SG name (e.g. ``SG32`` → ``32``)."""
    m = _SG_NUMBER_RE.match(name)
    return int(m.group(1)) if m else 0


def build_rules(rules_dict: dict) -> list[SegmentGroupRule]:
    """
    Convert a user-supplied rules dictionary into a sorted list of
    :class:`SegmentGroupRule` objects.

    Accepted rule spec keys:

    * ``"segment"``    *(required)* — segment tag, e.g. ``"NAD"``
    * ``"mandatory"``  — ``True`` if the group must appear at least once
    * ``"conditional"``— ``True`` is treated as ``mandatory=False``
    * ``"max"``        — maximum occurrence count (``None`` = unlimited)
    * ``"parent"``     — parent SG name; defaults to :data:`_IFTMIN_HIERARCHY`
      lookup, or ``None`` if not found

    Example input::

        {
            "SG11": {"segment": "NAD", "mandatory": True, "max": 2},
            "SG18": {"segment": "GID", "mandatory": True, "max": 999},
            "SG32": {"segment": "DGS", "conditional": True},
        }

    Args:
        rules_dict: Mapping of SG name → rule spec dict.

    Returns:
        List of :class:`SegmentGroupRule`, sorted by SG number (ascending).
    """
    result: list[SegmentGroupRule] = []
    for name, spec in rules_dict.items():
        mandatory = spec.get("mandatory", not spec.get("conditional", False))
        parent = spec.get("parent", _IFTMIN_HIERARCHY.get(name))
        result.append(SegmentGroupRule(
            name=name,
            segment=spec["segment"],
            mandatory=mandatory,
            max_occur=spec.get("max"),
            parent=parent,
            order=_sg_order(name),
        ))
    return sorted(result, key=lambda r: r.order)


# ---------------------------------------------------------------------------
# Individual structure checks
# ---------------------------------------------------------------------------

def _check_mandatory_and_max(
    segments: list[Segment],
    rules: list[SegmentGroupRule],
    errors: list[str],
) -> None:
    """
    Rule: mandatory groups must appear ≥ 1 time; no group may exceed its max.

    Counts all segments whose tag matches the rule's trigger tag, regardless
    of position.
    """
    for rule in rules:
        count = sum(1 for s in segments if s["tag"] == rule.segment)
        if rule.mandatory and count == 0:
            errors.append(
                f"{rule.name} ({rule.segment}): mandatory segment group is missing."
            )
        if rule.max_occur is not None and count > rule.max_occur:
            errors.append(
                f"{rule.name} ({rule.segment}): found {count} occurrence(s) "
                f"but maximum allowed is {rule.max_occur}."
            )


def _check_order(
    segments: list[Segment],
    rules: list[SegmentGroupRule],
    errors: list[str],
) -> None:
    """
    Rule: top-level segment groups must appear in ascending schema order.

    For every pair of top-level groups A (lower order) and B (higher order),
    all occurrences of A must precede all occurrences of B.  Concretely:
    ``max_position(A) < min_position(B)`` must hold when both are present.

    Child groups (those with a ``parent``) are excluded from this check;
    their position relative to other top-level groups is governed only by
    :func:`_check_hierarchy`.
    """
    top_level = [r for r in rules if r.parent is None]

    # positions[rule.name] = sorted list of segment indices in the message
    positions: dict[str, list[int]] = {
        r.name: [i for i, s in enumerate(segments) if s["tag"] == r.segment]
        for r in top_level
    }

    for idx, rule_a in enumerate(top_level):
        for rule_b in top_level[idx + 1:]:
            pos_a = positions[rule_a.name]
            pos_b = positions[rule_b.name]
            if not pos_a or not pos_b:
                continue  # absence dealt with by mandatory check
            last_a = max(pos_a)
            first_b = min(pos_b)
            if last_a > first_b:
                errors.append(
                    f"Order violation: {rule_a.name} ({rule_a.segment}) segment "
                    f"at index {last_a} appears after "
                    f"{rule_b.name} ({rule_b.segment}) segment at index {first_b}. "
                    f"Expected all {rule_a.name} before any {rule_b.name}."
                )


def _check_hierarchy(
    segments: list[Segment],
    rules: list[SegmentGroupRule],
    errors: list[str],
) -> None:
    """
    Rule: child group segments must only appear after their parent trigger.

    For a child group C with parent P:

    * If C is present but P is entirely absent → hierarchy violation.
    * If any C segment appears at an index lower than the first P segment
      → hierarchy violation (C precedes its parent).

    A child group that is absent causes no error here (mandatory check covers
    that separately).
    """
    name_to_tag: dict[str, str] = {r.name: r.segment for r in rules}
    child_rules = [r for r in rules if r.parent is not None]

    for rule in child_rules:
        parent_tag = name_to_tag.get(rule.parent)
        if parent_tag is None:
            continue  # parent not in the schema — cannot validate

        parent_positions = [i for i, s in enumerate(segments) if s["tag"] == parent_tag]
        child_positions  = [i for i, s in enumerate(segments) if s["tag"] == rule.segment]

        if not child_positions:
            continue  # no child segments — nothing to validate

        if not parent_positions:
            errors.append(
                f"Hierarchy violation: {rule.name} ({rule.segment}) is present but "
                f"parent group {rule.parent} ({parent_tag}) is missing entirely."
            )
            continue

        first_parent = min(parent_positions)
        early = [i for i in child_positions if i < first_parent]
        if early:
            errors.append(
                f"Hierarchy violation: {rule.name} ({rule.segment}) at "
                f"index {early[0]} appears before its parent "
                f"{rule.parent} ({parent_tag}) at index {first_parent}."
            )


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

DEFAULT_RULES: dict = {
    "SG11": {"segment": "NAD", "mandatory": True,  "max": 2},
    "SG18": {"segment": "GID", "mandatory": True,  "max": 999},
    "SG32": {"segment": "DGS", "conditional": True},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_structure(
    segments: list[Segment],
    rules_dict: dict | None = None,
) -> ValidationResult:
    """
    Validate segment group structure of a pre-parsed EDIFACT message.

    Runs three checks in order:

    1. Mandatory presence and max occurrence count
    2. Correct top-level group order
    3. Child group hierarchy

    Args:
        segments:   Output of :func:`edifact_parser.parse`.
        rules_dict: Rules dictionary (defaults to :data:`DEFAULT_RULES`).

    Returns:
        ``{"status": "PASS" | "FAIL", "errors": [str, ...]}``
    """
    rules = build_rules(rules_dict if rules_dict is not None else DEFAULT_RULES)
    errors: list[str] = []

    _check_mandatory_and_max(segments, rules, errors)
    _check_order(segments, rules, errors)
    _check_hierarchy(segments, rules, errors)

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def validate_structure_raw(
    edi_string: str,
    rules_dict: dict | None = None,
) -> ValidationResult:
    """
    Parse *edi_string* and validate its segment group structure.

    Args:
        edi_string: Raw UN/EDIFACT message string.
        rules_dict: Rules dictionary (defaults to :data:`DEFAULT_RULES`).

    Returns:
        ``{"status": "PASS" | "FAIL", "errors": [str, ...]}``
    """
    return validate_structure(parse(edi_string), rules_dict)


def validate_structure_to_json(
    edi_string: str,
    rules_dict: dict | None = None,
    indent: int = 2,
) -> str:
    """
    Parse, validate structure, and return the result as a JSON string.

    Args:
        edi_string: Raw UN/EDIFACT message string.
        rules_dict: Rules dictionary (defaults to :data:`DEFAULT_RULES`).
        indent:     JSON indentation spaces (default ``2``).

    Returns:
        JSON-encoded structural validation result.
    """
    return json.dumps(validate_structure_raw(edi_string, rules_dict), indent=indent)


# ---------------------------------------------------------------------------
# CLI / quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    VALID = (
        "UNB+UNOA:3+S+R+200401:1000+42'"
        "UNH+1+IFTMIN:D:04A:UN:BIG14'"
        "BGM+610+ORD001+9'"
        "NAD+CZ+9SENDER:::91'"
        "NAD+CN+9CONSIGNEE:::91'"
        "GID+1+10:BX'"
        "DGS+ADR+3:I+UN1090'"
        "UNT+7+1'"
        "UNZ+1+42'"
    )

    print("--- Valid structure ---")
    print(validate_structure_to_json(VALID))

    INVALID = (
        "UNB+UNOA:3+S+R+200401:1000+42'"
        "UNH+1+IFTMIN:D:04A:UN:BIG14'"
        "BGM+610+ORD001+9'"
        "DGS+ADR+3:I+UN1090'"   # DGS before any GID — hierarchy violation
        "GID+1+10:BX'"
        "NAD+CZ+9SENDER:::91'"  # NAD after GID — order violation
        "NAD+CN+9CONSIGNEE:::91'"
        "NAD+FP+9PAYER:::91'"   # 3rd NAD — exceeds max 2
        "UNT+8+1'"
        "UNZ+1+42'"
    )

    print("\n--- Invalid structure (order + hierarchy + max) ---")
    print(validate_structure_to_json(INVALID))
