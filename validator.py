"""
CLI entry point for the UN/EDIFACT IFTMIN validator.

Usage
-----
    python validator.py <file.edi>

Output lines
------------
    ❌ ERROR: <message>         — a hard validation failure
    ⚠️  WARNING: <message>      — an optional/advisory notice
    ✅ Valid structure: PASS    — structure check passed
    ❌ Invalid structure: FAIL  — structure check failed

Exit codes
----------
    0  — no errors (warnings are allowed)
    1  — one or more errors found
    2  — usage / file-read problem
"""

import os
import sys

from edifact_parser import parse
from edifact_validator import validate, load_rules, RulesConfig
from edifact_structure_validator import validate_structure

_RULES_FILENAME = "bring_rules.json"

# Optional segments: present = good, absent = advisory warning only.
_OPTIONAL_SEGMENTS = [
    ("FTX", "FTX (free text)"),
    ("RFF", "RFF (reference number)"),
]


def _print_error(message: str) -> None:
    print(f"\u274c ERROR: {message}")


def _print_warning(message: str) -> None:
    print(f"\u26a0\ufe0f  WARNING: {message}")


def _find_rules(edi_path: str) -> RulesConfig | None:
    """
    Look for bring_rules.json next to the EDI file, then next to this script.
    Returns the loaded config dict, or None if no rules file is found.
    """
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(edi_path)), _RULES_FILENAME),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), _RULES_FILENAME),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return load_rules(candidate)
    return None


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print("Usage: python validator.py <file.edi>", file=sys.stderr)
        return 2

    path = args[0]
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Cannot read file: {exc}", file=sys.stderr)
        return 2

    has_errors = False

    # --- load rules (optional) ----------------------------------------------
    rules = _find_rules(path)

    # --- content validation -------------------------------------------------
    segments = parse(raw)
    content_result = validate(segments, rules)
    for err in content_result["errors"]:
        _print_error(err["error"])
        has_errors = True

    # --- optional-segment checks (warnings only) ----------------------------
    present_tags = {seg["tag"] for seg in segments}
    for tag, label in _OPTIONAL_SEGMENTS:
        if tag not in present_tags:
            _print_warning(f"Missing optional {label}")

    # --- structure validation -----------------------------------------------
    structure_result = validate_structure(segments)
    for err in structure_result["errors"]:
        _print_error(f"[Structure] {err}")
        has_errors = True

    # --- summary line -------------------------------------------------------
    if structure_result["status"] == "PASS":
        print("\u2705 Valid structure: PASS")
    else:
        print("\u274c Invalid structure: FAIL")
        has_errors = True

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
