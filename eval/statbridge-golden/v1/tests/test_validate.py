import json, subprocess, sys, unittest
from pathlib import Path
V1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V1 / "scripts"))
import validate as V

GOOD = {
    "id": "GS2-0001", "schema_version": "gs1", "split": "dev",
    "source": {"publisher": "한국은행"},
    "input": {"prior_turns": [], "query": "질의"},
    "gold": {k: {"status": "not_labeled"} for k in
             ["e2e_kpi","slots","concepts","clarification","plan","discovery","numeric","graph","interpretation"]},
    "provenance": {}, "review": {"machine_reviewed": True, "human_approved": False},
}

class TestValidateStructure(unittest.TestCase):
    def test_good_record_has_no_errors(self):
        self.assertEqual(V.validate_record(GOOD), [])

    def test_missing_gold_layer_is_error(self):
        bad = json.loads(json.dumps(GOOD)); del bad["gold"]["graph"]
        self.assertTrue(any("gold missing" in e for e in V.validate_record(bad)))

    def test_bad_status_is_error(self):
        bad = json.loads(json.dumps(GOOD)); bad["gold"]["graph"]["status"] = "maybe"
        self.assertTrue(any("status invalid" in e for e in V.validate_record(bad)))
