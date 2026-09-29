from pathlib import Path
import json
import pytest
from tools.validate_rtl_entry_assertion_matrix import validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "analysis" / "rtl_entry_assertion_matrix.json"

def test_assertion_matrix_is_valid(): validate(MATRIX)

def test_progress_without_assumption_is_rejected(tmp_path: Path):
    data = json.loads(MATRIX.read_text())
    next(record for record in data["records"] if record["kind"] == "progress")["environment_assumption"] = ""
    path = tmp_path / "bad.json"; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="progress lacks assumption"): validate(path)
