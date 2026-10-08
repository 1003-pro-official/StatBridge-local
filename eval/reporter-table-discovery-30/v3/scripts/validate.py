"""Validate stagewise public table-discovery gold without calling external APIs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
STATUSES = {"resolved", "need_clarification", "no_match"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def normalized_period(raw: str, frequency: str, *, end: bool = False) -> str:
    digits = re.sub(r"[^0-9Qq]", "", str(raw or ""))
    if frequency == "M":
        if len(digits) >= 6:
            return digits[:6]
        if len(digits) == 4:
            return digits + ("12" if end else "01")
    elif frequency == "Q":
        match = re.fullmatch(r"(\d{4})[Qq]?0?([1-4])", digits)
        if match:
            return f"{match.group(1)}{int(match.group(2)):02d}"
        if len(digits) == 6 and digits[-2:] in {"01", "02", "03", "04"}:
            return digits
        if len(digits) == 4:
            return digits + ("04" if end else "01")
    elif frequency in {"Y", "A"}:
        return digits[:4] if len(digits) >= 4 else str(raw)
    return str(raw)


def subtract_months(value: str, count: int) -> str:
    year, month = int(value[:4]), int(value[4:6])
    index = year * 12 + month - 1 - count
    new_year, month_zero = divmod(index, 12)
    return f"{new_year:04d}{month_zero + 1:02d}"


def subtract_quarters(value: str, count: int) -> str:
    year, quarter = int(value[:4]), int(value[4:6])
    index = year * 4 + quarter - 1 - count
    new_year, quarter_zero = divmod(index, 4)
    return f"{new_year:04d}{quarter_zero + 1:02d}"


def expected_plan_period(case: dict, table: dict, frequency: str) -> tuple[str, str]:
    period = case["workflow_gold"]["query_interpretation"]["period"]
    if period:
        years = [int(x) for x in re.findall(r"((?:19|20)\d{2})\s*년?", case["query"])]
        require(len(years) >= 2, f"{case['id']}: explicit period years missing from query")
        start_year, end_year = min(years), max(years)
        if frequency == "M":
            return f"{start_year}01", f"{end_year}12"
        if frequency == "Q":
            return f"{start_year}01", f"{end_year}04"
        return str(start_year), str(end_year)

    observed_start = normalized_period(str(table.get("period_start_observed") or ""), frequency)
    observed_end = normalized_period(str(table.get("period_end_observed") or ""), frequency, end=True)
    if frequency == "M" and observed_end:
        return subtract_months(observed_end, 11), observed_end
    if frequency == "Q" and observed_end:
        return subtract_quarters(observed_end, 7), observed_end
    if frequency in {"Y", "A"} and observed_end:
        start = max(int(observed_start[:4] or observed_end[:4]), int(observed_end[:4]) - 4)
        return str(start), observed_end[:4]
    return observed_start, observed_end


def validate_cases(cases: list[dict], catalog: dict) -> dict:
    tables = {str(table["table_id"]): table for table in catalog["tables"]}
    require(bool(cases), "Empty dataset")
    require(len({case["id"] for case in cases}) == len(cases), "Duplicate case ID")
    require(len({case["query"] for case in cases}) == len(cases), "Duplicate natural-language query")
    status_counts = Counter()
    all_table_ids: set[str] = set()
    series_count = 0

    for case in cases:
        prefix = case["id"]
        require(case.get("schema_version") == "reporter349-discovery-3", f"{prefix}: schema version")
        require(case.get("split") == "dev", f"{prefix}: public dev set only")
        require(case.get("review", {}).get("ai_assisted") is True and
                case["review"].get("human_approved") is False, f"{prefix}: approval state")
        require(case.get("query", "").strip(), f"{prefix}: empty query")

        workflow = case.get("workflow_gold") or {}
        interpretation = workflow.get("query_interpretation") or {}
        discovery = workflow.get("table_discovery") or {}
        item_selection = workflow.get("item_selection") or {}
        plan = workflow.get("classification_and_plan") or {}
        resolution = workflow.get("resolution") or {}
        post = workflow.get("post_discovery") or {}
        status = resolution.get("agent_status")
        require(status in STATUSES, f"{prefix}: unknown agent status")
        status_counts[status] += 1

        meanings = interpretation.get("series") or []
        plans = plan.get("series") or []
        selected_ids = set(discovery.get("selected_table_ids") or [])
        require(set(discovery.get("expected_table_ids") or []) == selected_ids,
                f"{prefix}: expected table set differs from selected gold")
        require(interpretation.get("comparison", {}).get("required") == (len(meanings) > 1),
                f"{prefix}: comparison slot mismatch")

        if status == "need_clarification":
            require(resolution.get("clarification_required") is True, f"{prefix}: clarification flag")
            require(discovery.get("status") == "clarification_pending", f"{prefix}: discovery state")
            require(not selected_ids and not plans and not item_selection.get("item_by_table"),
                    f"{prefix}: selected before clarification")
            clarification = resolution.get("clarification") or {}
            groups = {group["id"]: group for group in catalog.get("clarification_groups", [])}
            group = groups.get(clarification.get("id"))
            if str(clarification.get('id', '')).startswith('canonical_table:'):
                key = clarification['id'].split(':', 1)[1]
                siblings = [t for t in catalog['tables'] if re.sub(r'[^0-9a-z가-힣]', '', t['table_name'].lower()) == key]
                require(len(siblings) > 1, f"{prefix}: canonical clarification is not ambiguous")
                group = {'question': '같은 이름의 통계표가 여러 개입니다. 기준과 통계표 ID를 확인해 선택해 주세요.',
                         'options': [{'value': t['table_id']} for t in siblings]}
            require(group is not None, f"{prefix}: unknown clarification group")
            require(clarification.get("question") == group.get("question"),
                    f"{prefix}: clarification question differs from runtime contract")
            expected_options = {option["value"] for option in group.get("options", [])}
            actual_options = {option["value"] for option in clarification.get("options", [])}
            require(actual_options == expected_options, f"{prefix}: clarification options differ from runtime contract")
            require(resolution.get("api_status") == "need_clarification" and
                    post.get("response_status") == "need_clarification", f"{prefix}: API clarification status")
            require(resolution.get("table_count") == 0 and resolution.get("series_count") == 0,
                    f"{prefix}: pending resolution counts")
            continue

        if status == "no_match":
            require(discovery.get("status") == "no_match", f"{prefix}: no_match discovery state")
            require(not selected_ids and not plans and not item_selection.get("item_by_table"),
                    f"{prefix}: no_match contains selected gold")
            require(bool(resolution.get("no_match_reason")), f"{prefix}: missing no_match evidence")
            require(resolution.get("api_status") == "no_match" and
                    post.get("response_status") == "no_match", f"{prefix}: API no_match status")
            require(resolution.get("table_count") == 0 and resolution.get("series_count") == 0,
                    f"{prefix}: no_match counts")
            continue

        require(discovery.get("status") == "matched", f"{prefix}: resolved discovery state")
        require(bool(plans), f"{prefix}: resolved case has no series plan")
        require(len(meanings) == len(plans), f"{prefix}: series count mismatch")
        require({meaning.get("label") for meaning in meanings} == {item.get("label") for item in plans},
                f"{prefix}: interpreted series do not match selected series")
        table_names: dict[str, str] = {}
        expected_items: dict[str, str] = {}
        seen: set[tuple] = set()
        for item in plans:
            table_id = str(item.get("table_id") or "")
            table = tables.get(table_id)
            require(table is not None and str(table.get("org_id")) == "301",
                    f"{prefix}: table missing or outside BOK KOSIS scope")
            require(item.get("table_name") == table.get("table_name"), f"{prefix}: table name mismatch")
            require(item.get("org_id") == "301", f"{prefix}: plan organization")
            require(item.get("item_id") in table.get("item_ids", []), f"{prefix}: invalid item code")
            frequency = item.get("frequency")
            require(frequency == next(m.get("frequency", interpretation.get("frequency")) for m in meanings if m["label"] == item["label"]) == (table['api_call_params'].get('prdSe') or table.get("prd_se")),
                    f"{prefix}: frequency mismatch")

            dimensions = {str(dimension["api_param"]): dimension for dimension in table.get("dimensions", [])}
            classes = item.get("classifications") or {}
            labels = item.get("classification_labels") or {}
            require(set(classes) == set(dimensions), f"{prefix}: missing or extra classification dimension")
            require(set(labels) == set(dimensions), f"{prefix}: classification label dimensions")
            for param, dimension in dimensions.items():
                values = {str(value["value_id"]): str(value["value_name"])
                          for value in dimension.get("values", [])}
                code = str(classes[param])
                require(code in values, f"{prefix}: invalid classification code")
                require(labels[param] == values[code], f"{prefix}: classification label mismatch")

            start, end = expected_plan_period(case, table, frequency)
            require(item.get("period_start") == start and item.get("period_end") == end,
                    f"{prefix}: planned period differs from runtime policy")
            params = item.get("exact_params") or {}
            expected_params = {"method":"getList","format":"json","jsonVD":"Y","smblChk":"Y",
                "orgId":"301","tblId":table_id,"itmId":item["item_id"],"prdSe":frequency,
                "startPrdDe":start,"endPrdDe":end,**classes}
            require(params == expected_params, f"{prefix}: exact KOSIS API parameters mismatch")

            identity = (table_id, item["item_id"], tuple(sorted(classes.items())))
            require(identity not in seen, f"{prefix}: duplicate selected series")
            seen.add(identity)
            table_names[table_id] = str(table["table_name"])
            expected_items[table_id] = str(item["item_id"])
            all_table_ids.add(table_id)
            series_count += 1

        require(selected_ids == set(table_names), f"{prefix}: selected table set mismatch")
        require(discovery.get("table_names") == table_names, f"{prefix}: table-name mapping mismatch")
        require(item_selection.get("item_by_table") == expected_items, f"{prefix}: item-by-table mismatch")
        require(resolution.get("clarification_required") is False, f"{prefix}: unexpected clarification")
        require(resolution.get("table_count") == len(table_names) and
                resolution.get("series_count") == len(plans), f"{prefix}: resolution counts")
        require(resolution.get("api_status") == "need_period" and
                post.get("response_status") == "need_period", f"{prefix}: discovery API boundary")
        require(post.get("execution") is False, f"{prefix}: numeric execution must be excluded")
        period = interpretation.get("period")
        expected_reason = "period_missing" if period is None else "execution_deferred"
        require(post.get("reason") == expected_reason and
                post.get("period_selection_required") is (period is None),
                f"{prefix}: post-discovery period behavior")

    return {"cases":len(cases),"statuses":dict(sorted(status_counts.items())),
            "series":series_count,"tables":len(all_table_ids)}



def audit_catalog(catalog):
    """Compare both metadata frequency fields; annual A/Y is explicitly recorded."""
    errors = []
    aliases = []
    for table in catalog['tables']:
        params = table['api_call_params']
        prefix = table['table_id']
        if params.get('tblId') != prefix or str(params.get('orgId')) != str(table['org_id']):
            errors.append({'id': prefix, 'error': 'Catalog API table or organization differs'})
        if params.get('itmId') not in table['item_ids']:
            errors.append({'id': prefix, 'error': 'Catalog API item is not in metadata'})
        left, right = table['prd_se'], params.get('prdSe') or table['prd_se']
        if left != right:
            if {left, right} <= {'A', 'Y'}:
                aliases.append({'table_id': prefix, 'catalog_frequency': left, 'api_frequency': right})
            else:
                errors.append({'id': prefix, 'error': 'Incompatible catalog/API frequencies'})
        for dim in table['dimensions']:
            codes = [v['value_id'] for v in dim['values']]
            if not codes or len(codes) != len(set(codes)):
                errors.append({'id': prefix, 'error': 'Missing or duplicated dimension value ID'})
            if dim.get('representative_value_id') and dim['representative_value_id'] not in codes:
                errors.append({'id': prefix, 'error': 'Invalid catalog representative value'})
    return errors, aliases


def audit(cases, catalog, manifest, base_cases):
    """Exhaust every row plus coverage and independently derived metadata constraints."""
    errors, api_frequency_aliases = audit_catalog(catalog)
    if api_frequency_aliases != manifest['api_frequency_aliases']:
        errors.append({'id': 'manifest', 'error': 'API frequency aliases not documented'})
    warnings = []
    for case in cases:
        try:
            validate_cases([case], catalog)
        except (ValueError, KeyError, StopIteration, TypeError) as exc:
            errors.append({'id': case.get('id'), 'error': str(exc)})
    summary = validate_cases(cases, catalog) if not errors else None
    tables = {t['table_id']: t for t in catalog['tables']}
    ids = set(tables)
    actual_coverage = {}
    for kind in ('single_table', 'multi_table', 'multi_classification'):
        group = [c for c in cases if c['augmentation']['kind'] == kind]
        covered = set()
        identities = set()
        for case in group:
            plans = case['workflow_gold']['classification_and_plan']['series']
            selected = {p['table_id'] for p in plans}
            covered.update(selected)
            identity = tuple(sorted((p['table_id'], p['item_id'], tuple(sorted(p['classifications'].items()))) for p in plans))
            if identity in identities:
                errors.append({'id': case['id'], 'error': 'Equivalent duplicated case in same augmentation lane'})
            identities.add(identity)
            if set(case['augmentation']['anchor_table_ids']) != selected:
                errors.append({'id': case['id'], 'error': 'Anchor and selected table mismatch'})
            if kind == 'single_table' and len(plans) != 1:
                errors.append({'id': case['id'], 'error': 'Single-table case must have one series'})
            if kind == 'multi_table' and (len(plans) != 2 or len(selected) != 2):
                errors.append({'id': case['id'], 'error': 'Multi-table case must have two distinct tables'})
            if kind == 'multi_classification':
                param = case['augmentation']['varying_dimension']
                if len(plans) != 2 or len(selected) != 1:
                    errors.append({'id': case['id'], 'error': 'Classification comparison requires two series from one table'})
                else:
                    dim = next(d for d in tables[plans[0]['table_id']]['dimensions'] if d['api_param'] == param)
                    if sorted(p['classifications'][param] for p in plans) != sorted(case['augmentation']['requested_value_ids']):
                        errors.append({'id': case['id'], 'error': 'Requested comparison values missing'})
                    if f"{dim['level']}번째 분류" not in case['query']:
                        errors.append({'id': case['id'], 'error': 'Varying dimension not specified in query'})
                    for p in plans:
                        if p['classification_labels'][param] not in case['query']:
                            errors.append({'id': case['id'], 'error': 'Classification label missing from query'})
                        fixed = {k: v for k, v in p['classifications'].items() if k != param}
                        if fixed != case['augmentation']['fixed_classifications']:
                            errors.append({'id': case['id'], 'error': 'Unintended second varying dimension'})
                        if any(label not in case['query'] for k, label in p['classification_labels'].items() if k != param):
                            errors.append({'id': case['id'], 'error': 'Fixed classification missing from query'})
            for p in plans:
                if p['table_name'] not in case['query']:
                    errors.append({'id': case['id'], 'error': 'Canonical table name missing from query'})
            if any(re.search(r'(?:19|20)\d{2}', p['table_name']) for p in plans):
                warnings.append({'id': case['id'], 'kind': 'table_title_contains_vintage_years',
                                 'note': 'Vintage years are table identifiers, not a period filter'})
        actual_coverage[kind] = sorted(covered)
        if kind in {'single_table', 'multi_table'} and covered != ids:
            errors.append({'id': kind, 'error': 'Not all 349 tables covered', 'missing': sorted(ids-covered)})
    applicable = {t['table_id'] for t in tables.values() if any(
        sum(sum(v['value_name'] == other['value_name'] for other in d['values']) == 1 for v in d['values']) >= 2
        for d in t['dimensions'])}
    if set(actual_coverage['multi_classification']) != applicable:
        errors.append({'id': 'multi_classification', 'error': 'Applicable table coverage mismatch'})
    exceptions = {x['table_id'] for x in manifest['classification_exceptions']}
    if applicable | exceptions != ids or applicable & exceptions:
        errors.append({'id': 'exceptions', 'error': 'Missing or invented classification exception'})
    copied = [c for c in cases if c['augmentation']['kind'] == 'v2_original']
    source = {c['id']: c for c in base_cases}
    if len(copied) != 30:
        errors.append({'id': 'v2_original', 'error': 'Missing original cases'})
    for case in copied:
        original = source[case['augmentation']['source_id']]
        if case['query'] != original['query'] or case['workflow_gold'] != original['workflow_gold']:
            errors.append({'id': case['id'], 'error': 'Original v2 query or gold changed'})
    counts = {'cases':len(cases), 'by_kind':dict(Counter(c['augmentation']['kind'] for c in cases)),
              'by_status':dict(Counter(c['workflow_gold']['resolution']['agent_status'] for c in cases))}
    if manifest['counts'] != counts:
        errors.append({'id': 'manifest', 'error': 'Counts mismatch'})
    if summary and summary['tables'] != 349:
        errors.append({'id': 'all_tables', 'error': 'Gold table coverage incomplete'})
    return {'valid': not errors, 'checked_cases':len(cases), 'error_count':len(errors), 'errors':errors,
            'warning_count':len(warnings), 'warnings':warnings, 'counts':counts,
            'coverage':{kind:len(values) for kind, values in actual_coverage.items()},
            'classification_exceptions':manifest['classification_exceptions'],
            'metadata_summary':summary, 'api_frequency_aliases':api_frequency_aliases, 'human_approved':False,
            'semantic_review':'Template, source-name, requested-value and frozen-contract audit; not human approval'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    path = DATASET/'statbridge-reporter349.jsonl'
    catalog_path = ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json'
    base_path = DATASET.parent/'v2/statbridge-reporter30.jsonl'
    cases = [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    base = [json.loads(line) for line in base_path.read_text(encoding='utf8').splitlines()]
    manifest = json.loads((DATASET/'dataset_manifest.json').read_text(encoding='utf8'))
    require(text_sha256(path) == manifest['dataset_sha256'], 'Dataset SHA mismatch')
    require(text_sha256(catalog_path) == manifest['catalog_sha256'], 'Catalog SHA mismatch')
    require(text_sha256(base_path) == manifest['source_dataset_sha256'], 'Base v2 SHA mismatch')
    for case in cases:
        require(case['evidence']['catalog_sha256'] == manifest['catalog_sha256'], f"{case['id']}: catalog provenance")
    result = audit(cases, catalog, manifest, base)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'warnings'}},ensure_ascii=False))
    raise SystemExit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
