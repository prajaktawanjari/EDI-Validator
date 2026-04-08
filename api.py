from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from edifact_validator import validate_raw

app = FastAPI(title="Bring EDI Validator")

# Enable CORS for the HTML frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EDIInput(BaseModel):
    edi: str
    validate_interchange: bool = False  # toggle


@app.get("/")
def home():
    return {"message": "Bring EDI Validator is running"}


@app.post("/validate")
def validate(input: EDIInput):
    edi_string = input.edi

    # Split segments
    segments = [s.strip() for s in edi_string.split("'") if s.strip()]

    # Call the existing validator
    result = validate_raw(edi_string)

    errors = result.get("errors", [])

    # 🔹 Interchange validation (UNB / UNZ)
    if input.validate_interchange:
        has_unb = any(seg.startswith("UNB") for seg in segments)
        has_unz = any(seg.startswith("UNZ") for seg in segments)

        if not has_unb:
            errors.append({
                "segment": "UNB",
                "error": "Missing UNB (interchange header)",
                "suggestion": "Add UNB segment at beginning, e.g. UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123"
            })

        if not has_unz:
            errors.append({
                "segment": "UNZ",
                "error": "Missing UNZ (interchange trailer)",
                "suggestion": "Add UNZ segment at end, e.g. UNZ+1+REF123"
            })

        # 🔥 Reference check
        if has_unb and has_unz:
            unb_ref = None
            unz_ref = None

            for seg in segments:
                if seg.startswith("UNB"):
                    parts = seg.split("+")
                    if len(parts) > 5:
                        unb_ref = parts[5].strip()

                if seg.startswith("UNZ"):
                    parts = seg.split("+")
                    if len(parts) > 2:
                        unz_ref = parts[2].strip()

            if unb_ref and unz_ref and unb_ref != unz_ref:
                errors.append({
                    "segment": "UNZ",
                    "error": f"UNB and UNZ reference mismatch: UNB={unb_ref}, UNZ={unz_ref}",
                    "suggestion": "Ensure UNB element 5 and UNZ element 2 have the same control reference"
                })

    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": result.get("warnings", [])
    }
