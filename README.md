# EDIFACT Validator

A comprehensive UN/EDIFACT message parser and validator for IFTMIN messages implementing Bring-specific business rules.

## Features

- ✅ **Python CLI Validator** - Command-line validation with config file support
- ✅ **FastAPI REST API** - Server-side validation endpoint
- ✅ **HTML Web Interface** - Browser-based validator with syntax highlighting
- ✅ **11 Business Rules** - UNH, UNT, UNZ (conditional), BGM, DTM, NAD, TOD, GDS, DGS validation
- ✅ **Structure Validation** - Segment group hierarchy, order, max occurrences
- ✅ **Config-Driven** - JSON-based rule configuration
- ✅ **227 Tests** - Comprehensive test coverage

## Quick Start

### 1. Python CLI

```bash
python validator.py message.edi
```

### 2. FastAPI Server

**Windows:**
```bash
# Double-click in File Explorer:
START_SERVER.bat

# Or run manually:
python -m uvicorn api:app --reload --port 8000
```

**Other OS:**
```bash
python -m uvicorn api:app --reload --port 8000
```

Visit **http://127.0.0.1:8000/docs** for interactive API documentation.

### 3. HTML Interface

**Windows - Easiest Method:**
```bash
# Double-click in File Explorer:
OPEN_VALIDATOR.bat
```

**Or manually:**
- Press `Ctrl + O` in your browser → Navigate to `C:\Users\Prajakta\GitHub\EDI Validator\index.html` → Open
- Or double-click `index.html` in File Explorer
- Or paste in browser: `file:///C:/Users/Prajakta/GitHub/EDI Validator/index.html`

## API Usage

### Standard Validation (Conditional UNZ)

```bash
curl -X POST http://127.0.0.1:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "edi": "UNH+1+IFTMIN:D:04A:UN:BIG14'\''BGM+610+ORD001+9'\''...",
    "validate_interchange": false
  }'
```

**Behavior**: UNZ only required when UNB (interchange header) is present.

### Strict Interchange Validation

```bash
curl -X POST http://127.0.0.1:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "edi": "UNB+UNOC:3+SENDER:ZZZ+...'\''UNH+1+...",
    "validate_interchange": true
  }'
```

**Behavior**: UNB and UNZ are **mandatory**, and their reference numbers must match.

### Response Format

```json
{
  "status": "PASS|FAIL",
  "errors": [
    {
      "segment": "UNZ",
      "error": "Missing UNZ (interchange trailer)",
      "suggestion": "Add UNZ segment at end, e.g. UNZ+1+REF123"
    }
  ],
  "warnings": []
}
```

## HTML Interface Modes

The HTML validator supports two modes:

### Client-Side Validation (Default)
- Fast, instant validation in browser
- No network required
- Uses JavaScript implementation of all rules

### API Mode (Server-Side)
1. Check **"Use API (server-side)"** checkbox
2. Optionally check **"Strict interchange validation"** for UNB/UNZ enforcement
3. Click **Validate**

## Validation Rules

### Content Validation (11 Rules)

1. **UNH** - Message type must be IFTMIN:D:04A:UN:BIG14
2. **UNT** - Segment count must match actual segments (UNH–UNT inclusive)
3. **UNZ** - Conditional on UNB presence (or mandatory in strict mode)
4. **BGM** - Document code must be 610, 335, or 730
5. **DTM+137** - Document date required
6. **NAD+CZ** - Sender required
7. **NAD+CN** - Consignee required
8. **TOD→NAD+FP** - If TOD has TP qualifier, NAD+FP (freight payer) required
9. **GDS+11→DGS** - If dangerous goods indicated, DGS segment required
10. **DGS UN format** - UN number must match pattern `UN\d{4}`
11. **DGS→MEA** - If DGS present, MEA (measurement) required

### Structure Validation

- Segment group hierarchy (SG11, SG18, SG32)
- Correct segment order within groups
- Max occurrence limits

## Configuration

Edit `bring_rules.json`:

```json
{
  "mandatory_segments": ["UNH", "BGM", "DTM", "CNT"],
  "nad_required": ["CZ", "CN"],
  "dgs_required_if_gds": true
}
```

## Testing

```bash
pytest                                    # Run all 227 tests
pytest test_edifact_validator.py         # Content validation tests
pytest test_edifact_structure_validator.py # Structure tests
pytest -v                                 # Verbose output
```

## Files

- `edifact_parser.py` - Core parser (raw EDI → structured segments)
- `edifact_validator.py` - Content/business rule validation
- `edifact_structure_validator.py` - Structure validation
- `validator.py` - CLI entry point
- `api.py` - FastAPI REST API
- `index.html` - Web interface with syntax highlighting
- `bring_rules.json` - Configuration file

## API Endpoints

- `GET /` - Health check
- `POST /validate` - Validate EDI message
  - Body: `{"edi": string, "validate_interchange": boolean}`
  - Returns: `{"status": string, "errors": array, "warnings": array}`

## Development

API server runs with auto-reload:
```bash
python -m uvicorn api:app --reload --port 8000
```

Access interactive docs at: http://127.0.0.1:8000/docs

## License

MIT
