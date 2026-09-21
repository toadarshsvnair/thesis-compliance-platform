import json
import subprocess
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "engine" / "thesis_compliance_engine_v0_2.py"

def run_validation(docx_path: str, pdf_path: str | None, output_path: str, reference_style: str | None = None):
    cmd = ["python", str(ENGINE), docx_path, "--output", output_path]
    if pdf_path:
        cmd += ["--pdf", pdf_path]
    if reference_style:
        cmd += ["--reference-style", reference_style]
    return subprocess.run(cmd, capture_output=True, text=True, check=True)
