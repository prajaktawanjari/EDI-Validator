valid = (
    "UNH+1+IFTMIN:D:04A:UN:BIG14'"
    "BGM+610+ORD001+9'"
    "DTM+137:20260408:102'"
    "NAD+CZ+9SENDER:::91'"
    "NAD+CN+9CONSIGNEE:::91'"
    "UNT+6+1'"
)
invalid = (
    "UNH+1+IFTMIN:D:04A:UN:BIG14'"
    "BGM+610+ORD001+9'"
    "NAD+CZ+9SENDER:::91'"
    "UNT+4+1'"
)
open("input_valid.edi", "w", encoding="utf-8").write(valid)
open("input_invalid.edi", "w", encoding="utf-8").write(invalid)
print("files written")
