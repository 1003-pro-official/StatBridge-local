import json, sys, unittest
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

    def test_forbidden_overlaps_acceptable_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["discovery"] = {"status": "labeled", "expected_status": "select",
                                  "acceptable_table_ids": ["DT_A"], "required_set": ["DT_A"],
                                  "forbidden_table_ids": ["DT_A"]}
        self.assertTrue(any("forbidden overlaps" in e for e in V.validate_record(r)))

    def test_no_match_with_tables_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["discovery"] = {"status": "labeled", "expected_status": "no_match",
                                  "acceptable_table_ids": ["DT_A"], "required_set": [],
                                  "forbidden_table_ids": []}
        self.assertTrue(any("no_match has tables" in e for e in V.validate_record(r)))

    def test_context_claim_requires_source(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["interpretation"] = {"status": "labeled",
            "required_claims": [{"id": "c1", "type": "direction", "expected": "up"}],
            "context_claims": [{"id": "x1", "type": "context", "text": "맥락"}]}
        self.assertTrue(any("context claim without source" in e for e in V.validate_record(r)))

    def test_fixture_missing_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["graph"] = {"status": "labeled", "fixture": "fixtures/none.json", "snapshot_id": "x"}
        errs = V.validate_fixtures(r, V1)
        self.assertTrue(any("fixture missing" in e for e in errs))

    def test_holdout_leakage_is_error(self):
        errs = V.validate_holdout([{"id": "H1", "query": "q", "prior_turns": [], "table_ids": ["DT_A"]}])
        self.assertTrue(any("holdout leakage" in e for e in errs))
