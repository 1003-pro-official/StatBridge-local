import sys, unittest
from pathlib import Path
V1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V1 / "scripts"))
import score as S

DISC = {"status": "labeled", "expected_status": "select",
        "acceptable_table_ids": ["DT_A", "DT_B"], "required_set": ["DT_A", "DT_B"],
        "forbidden_table_ids": ["DT_X"]}

class TestDiscovery(unittest.TestCase):
    def test_exact_match(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B"]})
        self.assertEqual(out["exact"], True); self.assertEqual(out["f1"], 1.0)

    def test_partial_recall(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A"]})
        self.assertFalse(out["exact"]); self.assertAlmostEqual(out["recall"], 0.5)

    def test_forbidden_hit(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B", "DT_X"]})
        self.assertTrue(out["forbidden_hit"])
