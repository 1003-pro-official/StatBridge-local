"""Shared, version-local contracts. No private evaluator or v1 data imports."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
MODES = ("discovery", "e2e", "output", "edit")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows), encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def local_path(base, relative):
    path = (Path(base) / relative).resolve()
    if not path.is_relative_to(Path(base).resolve()):
        raise ValueError("path escapes its declared root")
    return path


def identity(series):
    if series.get("provider") == "attachment":
        return ("attachment", series["series_id"], series["frequency"], series["unit"])
    if series.get("provider") != "kosis":
        raise ValueError("unknown series provider")
    return ("kosis", series["table_id"], series["item_id"],
            tuple(sorted(series["classifications"].items())), series["frequency"], series["unit"])


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalized_unit(table_id, source_unit):
    rules = read_json(BASE / "unit_rules.json")["rules"]
    for rule in rules:
        if table_id in rule["table_ids"] and source_unit == rule["source_unit"]:
            if rule["scale"] != 1:
                raise ValueError("unit normalization cannot rescale observations")
            return rule["display_unit"]
    return source_unit


def unit_sources(table_id):
    for rule in read_json(BASE / "unit_rules.json")["rules"]:
        if table_id in rule["table_ids"]:
            return [
                {"path": str((BASE / "unit_rules.json").relative_to(ROOT)).replace("\\", "/"),
                 "sha256": digest(BASE / "unit_rules.json"), "locator": "rules: " + table_id,
                 "extraction": rule["meaning"], "publisher": "StatBridge evaluator annotation (ai-assisted)"},
                {"path": rule["definition_path"], "sha256": rule["definition_sha256"],
                 "locator": rule["locator"], "extraction": "Unit-definition evidence only; numeric values remain from local CSV. " + rule["definition_url"],
                 "publisher": rule["publisher"]},
            ]
    return []


def transform_series(series, command):
    """Independent expected-data calculation; never imports application transforms."""
    import copy
    result = copy.deepcopy(series)
    for s in result:
        points = s["points"]
        operation = command.get("operation")
        if operation == "filter_period":
            s["points"] = [p for p in points if command["start"] <= p["period"] <= command["end"]]
        elif operation == "set_transform":
            kind = command["value"]
            if kind in {"growth_rate", "year_over_year"}:
                lag = 1 if kind == "growth_rate" else {"M": 12, "Q": 4, "Y": 1}[s["frequency"]]
                def previous_period(period):
                    freq = s["frequency"]
                    if freq == "M":
                        index = int(period[:4])*12 + int(period[4:])-1-lag
                        return str(index//12).zfill(4) + str(index%12+1).zfill(2)
                    if freq in {"Q", "H"}:
                        cycles = 4 if freq == "Q" else 2
                        index = int(period[:4])*cycles + int(period[-1])-1-lag
                        return str(index//cycles).zfill(4) + freq + str(index%cycles+1)
                    if freq == "Y":
                        return str(int(period)-lag).zfill(4)
                    from datetime import datetime, timedelta
                    return (datetime.strptime(period, "%Y%m%d")-timedelta(days=7 if freq == "W" else 1)).strftime("%Y%m%d")
                by_period = {p["period"]: p["value"] for p in points}
                calculated = []
                for p in points:
                    prior_period = previous_period(p["period"])
                    if prior_period < points[0]["period"]:
                        continue
                    previous, current = by_period.get(prior_period), p["value"]
                    value = None if previous in (None, 0) or current is None else (current / previous - 1) * 100
                    calculated.append({"period": p["period"], "value": value})
                s["points"], s["unit"] = calculated, "%"
            elif kind == "cumulative":
                # Monthly flow sums are cumulative changes, not monthly changes.
                if s["unit"].startswith("전월대비,"):
                    s["unit"] = s["unit"].split(",", 1)[1].strip()
                    s["label"] += " (누적 변화량, " + points[0]["period"] + "~" + points[-1]["period"] + ")"
                total = 0
                for p in points:
                    if p["value"] is not None:
                        total += p["value"]
                        p["value"] = total
            elif kind == "average":
                values = [p["value"] for p in points if p["value"] is not None]
                s["points"] = [{"period": points[-1]["period"], "value": sum(values) / len(values)}] if values else []
    return result
