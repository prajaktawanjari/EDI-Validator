# EDI Validator Demo

## Enhanced UI Features

### 1. Error Segment Highlighting
- Error segments now have a **red border** with glowing effect
- Background is highlighted with semi-transparent red
- Makes it easy to spot which segments have errors

### 2. Improved Suggestion Display
- Suggestions now shown in a styled box with left border
- Better visual separation from error messages
- 💡 Icon prefix for easy identification

### 3. Real-time Visual Feedback
- Segments with errors are highlighted as you validate
- Clear button removes all error highlighting
- Smooth visual transitions

## Test It Out

### Test Case 1: Missing UNB/UNZ
Paste this into the validator:
```
UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'
```

**Expected Result:**
- UNB and UNZ segments will show with red borders in the editor
- Error messages will show suggestions in styled boxes below

### Test Case 2: Invalid BGM Code
Paste this:
```
UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+999+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF123'
```

**Expected Result:**
- BGM segment will have red border highlighting
- Error will show: "BGM code '999' is invalid; must be one of [335, 610, 730]"
- Suggestion box will show: "Change to 610, 335, or 730."

### Test Case 3: Reference Mismatch
Paste this:
```
UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF999'
```

**Expected Result:**
- UNZ segment highlighted with red border
- Error: "UNB and UNZ reference mismatch: UNB=REF123, UNZ=REF999"
- Suggestion: "Ensure UNB element 5 and UNZ element 2 have the same control reference"

## Visual Indicators

| Element | Style |
|---------|-------|
| Error Segment Tag | Red border (2px), glowing red shadow, semi-transparent red background |
| Suggestion Box | Gray background, left border, padded, rounded corners |
| Error Message | Bold segment tag, clear error text |
| Success | Green header, no segment highlighting |
| Failure | Red header, error count displayed |

## API Server

Make sure the API server is running:
```bash
python -m uvicorn api:app --reload --port 8000
```

Visit: http://127.0.0.1:8000/docs for interactive API documentation
