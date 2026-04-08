"""
UN/EDIFACT message parser.

Converts a raw EDI string into a structured list of segment dictionaries.

Delimiters (EDIFACT defaults):
    Segment terminator : '
    Element separator  : +
    Component separator: :
    Escape / release   : ?

Output structure per segment:
    {
        "tag": str,
        "elements": list[str | list[str]]
    }

Each element is a plain string when it contains one component, or a list of
strings when it contains multiple colon-separated components.  Example:
    DTM+137:20260408:102'
    → {"tag": "DTM", "elements": [["137", "20260408", "102"]]}

Parsing strategy
----------------
Escape sequences are processed **once**, at the lowest (component) level.
All higher-level splits (segment → element → component) preserve escape
sequences verbatim so that a ``??`` sequence is never consumed early and
re-interpreted as a new escape at the next level.
"""

import json
from typing import Union


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _split_raw(
    text: str,
    delimiter: str,
    escape_char: str = "?",
) -> list[str]:
    """
    Split *text* by *delimiter*, honouring EDIFACT escape sequences.

    Unlike a naive split, an escaped delimiter (e.g. ``?+``) is **not** used
    as a split point.  Escape sequences are kept verbatim in the output so
    that callers can apply :func:`_unescape` exactly once at the final level.

    Args:
        text:        The string to split.
        delimiter:   The single character used as a field boundary.
        escape_char: The release / escape character (default ``?``).

    Returns:
        A list of raw sub-strings between occurrences of *delimiter*.
    """
    parts: list[str] = []
    current: list[str] = []
    i = 0

    while i < len(text):
        ch = text[i]
        if ch == escape_char and i + 1 < len(text):
            # Keep the escape sequence verbatim — do NOT decode here.
            current.append(ch)
            current.append(text[i + 1])
            i += 2
        elif ch == delimiter:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1

    parts.append("".join(current))
    return parts


def _unescape(text: str, escape_char: str = "?") -> str:
    """
    Decode EDIFACT escape sequences in *text*.

    Each occurrence of *escape_char* followed by any character is replaced
    by that character alone.  Call this **only** on a final component string,
    after all delimiter-based splitting has been completed.

    Args:
        text:        Raw component string that may contain escape sequences.
        escape_char: The release / escape character (default ``?``).

    Returns:
        The decoded string with escape sequences resolved.
    """
    result: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == escape_char and i + 1 < len(text):
            result.append(text[i + 1])
            i += 2
        else:
            result.append(ch)
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Element / segment parsers
# ---------------------------------------------------------------------------

def _parse_element(raw: str) -> Union[str, list[str]]:
    """
    Parse a single element string, applying component-level splitting.

    Returns a plain string when the element has exactly one component;
    returns a list of strings when it has two or more colon-separated
    components.  Escape sequences are decoded at this stage via
    :func:`_unescape`.

    Args:
        raw: Raw element string, e.g. ``"137:20260408:102"`` or ``"380"``.

    Returns:
        ``str`` for a single component, ``list[str]`` for composite elements.
    """
    raw_components = _split_raw(raw, ":")
    components = [_unescape(c) for c in raw_components]
    return components[0] if len(components) == 1 else components


def _parse_segment(raw_segment: str) -> dict:
    """
    Parse one raw segment string into a structured dictionary.

    The first ``+``-delimited token is the three-letter segment tag; all
    subsequent tokens are parsed as elements (with component splitting
    applied via :func:`_parse_element`).

    Args:
        raw_segment: A single segment string without the trailing ``'``,
                     e.g. ``"DTM+137:20260408:102"``.

    Returns:
        ``{"tag": str, "elements": list[str | list[str]]}``
    """
    parts = _split_raw(raw_segment.strip(), "+")
    tag = parts[0]
    elements = [_parse_element(p) for p in parts[1:]]
    return {"tag": tag, "elements": elements}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(edi_string: str) -> list[dict]:
    """
    Parse a raw UN/EDIFACT string into a list of segment dictionaries.

    Segments are split on the ``'`` terminator; each segment is then split
    on ``+`` for elements and ``:`` for components.  The ``?`` escape
    character is honoured at every level.

    Args:
        edi_string: Raw EDI message, e.g.::

            "BGM+380+INV001+9'DTM+137:20260408:102'UNZ+1+42'"

    Returns:
        A list of segment dicts ordered as they appear in the message:

        .. code-block:: json

            [
              {"tag": "BGM", "elements": ["380", "INV001", "9"]},
              {"tag": "DTM", "elements": [["137", "20260408", "102"]]},
              {"tag": "UNZ", "elements": ["1", "42"]}
            ]
    """
    raw_segments = _split_raw(edi_string.strip(), "'")
    result: list[dict] = []

    for raw in raw_segments:
        raw = raw.strip()
        if raw:
            result.append(_parse_segment(raw))

    return result


def parse_to_json(edi_string: str, indent: int = 2) -> str:
    """
    Parse a raw UN/EDIFACT string and return a formatted JSON string.

    Args:
        edi_string: Raw EDI message string.
        indent:     JSON indentation spaces (default ``2``).

    Returns:
        JSON-encoded representation of the parsed segments.
    """
    return json.dumps(parse(edi_string), indent=indent)


def check_escape(text: str) -> str | None:
    """
    Check whether *text* contains an unescaped apostrophe.

    In UN/EDIFACT the apostrophe (``'``) is the segment terminator.  Any
    literal apostrophe inside a data value must be escaped as ``?'``.  A
    bare ``'`` that is not preceded by the escape character ``?`` is a
    structural error that will cause the parser to split the segment
    prematurely.

    Args:
        text: A raw element or component value string to inspect.

    Returns:
        An error message string if an unescaped apostrophe is found,
        or ``None`` if the text is clean.

    Examples::

        >>> check_escape("O'Brien")
        "Unescaped apostrophe found. Use ?'"
        >>> check_escape("O?'Brien")   # correctly escaped
        >>> check_escape("no issues")
    """
    if "'" in text and "?" not in text:
        return "Unescaped apostrophe found. Use ?'"
    return None


# ---------------------------------------------------------------------------
# CLI / quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SAMPLE = (
        "UNB+UNOA:3+SENDER+RECEIVER+200401:1000+42'"
        "UNH+1+INVOIC:D:96A:UN'"
        "BGM+380+INV001+9'"
        "DTM+137:20260408:102'"
        "NAD+BY+9BUYER:::91'"
        "LIN+1++WIDGET:IB'"
        "MOA+79:1500.00:EUR'"
        "UNT+7+1'"
        "UNZ+1+42'"
    )

    print(parse_to_json(SAMPLE))
