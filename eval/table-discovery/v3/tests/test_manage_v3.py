import copy
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "manage_v3.py"
spec = importlib.util.spec_from_file_location("manage_v3", SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def case():
    return {
        "id": "GS-0001", "split": "dev", "query": "2025년 월별 표 A 추이", "prior_turns": [],
        "type": "single", "intent": "trend",
        "slots": {"metrics": ["표 A"], "target": None, "period": "2025년", "frequency": "월", "qualifiers": [], "comparison": False},
        "normalized_concepts": ["표 A"], "expected_status": "select",
        "table_ids": ["DT_TEST"], "candidate_table_ids": [], "clarification_dimension": [],
        "evidence": "data/tables/DT_TEST.csv: 월별 2025년 항목 확인",
        "review_status": "review_required",
        "review": {"decision": None, "approved_table_ids": [], "reviewer": None, "reviewed_at": None, "review_notes": None},
    }


class ReviewCsvTests(unittest.TestCase):
    def test_roundtrip_records_review_without_approving_gold(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.csv"
            original = case()
            manage.export_review([original], path)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0].update({"decision": "승인", "approved_table_ids": "DT_TEST", "reviewer": "PM"})
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            updated = manage.import_review_rows([original], path, {"DT_TEST"})
            self.assertEqual(updated[0]["review"]["decision"], "승인")
            self.assertEqual(updated[0]["review"]["approved_table_ids"], ["DT_TEST"])
            self.assertEqual(updated[0]["review_status"], "review_required")
            self.assertEqual(updated[0]["table_ids"], original["table_ids"])
            self.assertIsNone(original["review"]["decision"])

    def test_invalid_review_rejects_entire_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.csv"
            first = case()
            second = copy.deepcopy(first)
            second["id"] = "GS-0002"
            manage.export_review([first, second], path)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0].update({"decision": "승인", "approved_table_ids": "DT_TEST", "reviewer": "PM"})
            rows[1]["query"] = "실수로 수정한 질문"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError):
                manage.import_review_rows([first, second], path, {"DT_TEST"})
            self.assertIsNone(first["review"]["decision"])

    def test_malformed_csv_row_is_rejected_cleanly(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.csv"
            manage.export_review([case()], path)
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            path.write_text(lines[0] + "\n" + "GS-0001\n", encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError, "malformed CSV row"):
                manage.import_review_rows([case()], path, {"DT_TEST"})


class ValidationTests(unittest.TestCase):
    def test_metric_slot_must_come_from_user_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = case()
            row["slots"]["metrics"] = ["카탈로그에만 있는 표명"]
            errors = manage.validate_rows([row], {"DT_TEST"}, Path(temporary), pilot=False)
            self.assertTrue(any("metric not grounded" in error for error in errors))

    def test_rejects_duplicate_id_within_v3(self):
        with tempfile.TemporaryDirectory() as temporary:
            errors = manage.validate_rows([case(), case()], {"DT_TEST"}, Path(temporary), pilot=False)
            self.assertTrue(any("duplicate ID" in error for error in errors))

    def test_select_case_requires_a_local_csv_and_unique_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            errors = manage.validate_rows([case(), case()], {"DT_TEST"}, Path(temporary), pilot=False)
            self.assertTrue(any("local CSV missing" in error for error in errors))
            self.assertTrue(any("duplicate query" in error for error in errors))

    def test_select_case_accepts_backend_double_underscore_csv_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "DT_TEST__표 A 월별 추이.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["PRD_SE", "PRD_DE"])
                writer.writeheader()
                writer.writerow({"PRD_SE": "M", "PRD_DE": "2025-01"})
            errors = manage.validate_rows([case()], {"DT_TEST"}, Path(temporary), pilot=False)
            self.assertFalse(any("local CSV missing" in error for error in errors))

    def test_clarification_has_options_but_no_accepted_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = case()
            row.update({"type": "clarify", "expected_status": "clarify", "candidate_table_ids": ["DT_TEST"], "clarification_dimension": ["계열 선택"]})
            errors = manage.validate_rows([row], {"DT_TEST"}, Path(temporary), pilot=False)
            self.assertTrue(any("clarify has accepted table IDs" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
