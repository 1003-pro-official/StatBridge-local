"""Search only the checked-in Bank of Korea KOSIS catalog."""
from statbridge_mcp.observability import observed
import hashlib
import json
import re
from expression_tree_validator import DerivedValidationError


class DerivedCatalogTools:
    def __init__(self, store):
        self.store = store
        # Fail closed if the registry changes; a migration must review the boundary.
        self.approved = frozenset(store.table_ids())
        if len(self.approved) != 349 or any(str(store.get(t).org_id) != '301' for t in self.approved):
            raise DerivedValidationError('한국은행 349개 승인 통계표 목록을 확인할 수 없습니다.')
        content = [store.get(t).canonical_dict() for t in sorted(self.approved)]
        self.version = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    @observed('catalog.metadata', 'span')
    def get_table_metadata(self, table_id):
        if table_id not in self.approved:
            raise DerivedValidationError(f'승인 목록 밖의 통계표: {table_id}')
        meta = self.store.get(table_id).canonical_dict()
        # Avoid sending contact details to the model.
        return {k: meta[k] for k in ('table_id', 'table_name', 'frequencies', 'periods', 'items', 'dimensions', 'comments')}

    @observed('catalog.search', 'span')
    def search_approved_tables(self, query, limit=6):
        words = re.findall(r'[가-힣A-Za-z]+', query.lower())
        terms = {re.sub(r'(?:으로|부터|까지|에서|기준으로|의|와|과|로|를|을|은|는|에)$', '', word) for word in words}
        terms -= {'계산', '주세요', '보여', '비교', '기준', '전년', '동월', '상승률', '변화율', '기간', '월별', '연간'}
        years = [int(y) for y in re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', query)]
        scored = []
        for table_id in sorted(self.approved):
            meta = self.store.get(table_id)
            ranges = [(int(str(p['start_period'])[:4]), int(str(p['end_period'])[:4]))
                      for p in meta.periods if str(p.get('start_period', ''))[:4].isdigit() and str(p.get('end_period', ''))[:4].isdigit()]
            if years and ranges and not any(start <= max(years) and min(years) <= end for start, end in ranges):
                continue
            haystack = meta.search_text.lower()
            title = meta.table_name.lower()
            score = sum(len(term) * (5 if term in title else 1) for term in terms if len(term) > 1 and term in haystack)
            if score:
                scored.append((score, table_id))
        def latest(table_id):
            return max((str(p.get('end_period') or '') for p in self.store.get(table_id).periods), default='')
        scored.sort(key=lambda item: (-item[0], -int((latest(item[1]) or '0000')[:4]), len(self.store.get(item[1]).table_name), item[1]))
        return [{'table_id': tid, 'table_name': self.store.get(tid).table_name, 'score': score}
                for score, tid in scored[:min(limit, 10)]]

    @observed('source.validate', 'span')
    def validate_source_selection(self, source):
        meta = self.get_table_metadata(source.table_id)
        if source.item_id not in {str(i['item_id']) for i in meta['items']}:
            raise DerivedValidationError(f'{source.table_id}: 존재하지 않는 세부항목 {source.item_id}')
        if source.frequency not in meta['frequencies']:
            raise DerivedValidationError(f'{source.table_id}: 지원하지 않는 주기 {source.frequency}')
        dimensions = {d['mcp_param']: {str(v['class_id']) for v in d['values']} for d in meta['dimensions'] if d['values']}
        if set(source.classifications) != set(dimensions):
            raise DerivedValidationError(f'{source.table_id}: 필요한 분류 {list(dimensions)}를 각각 하나씩 지정해야 합니다.')
        for key, value in source.classifications.items():
            if value not in dimensions[key]:
                raise DerivedValidationError(f'{source.table_id}: 잘못된 분류 {key}={value}')
        return meta

    def selection_text(self, source):
        meta = self.validate_source_selection(source)
        selected = [meta['table_name'], next(i['item_name'] for i in meta['items'] if i['item_id'] == source.item_id)]
        selected += [v['class_name'] for d in meta['dimensions'] for v in d['values']
                     if source.classifications.get(d['mcp_param']) == v['class_id']]
        return ' '.join(selected)

    def bounded_metadata(self, table_id, query=''):
        metadata = self.get_table_metadata(table_id)
        terms = re.findall(r'[가-힣A-Za-z0-9]+', query.lower())
        def select(values, limit):
            if terms:
                ranked = sorted(values, key=lambda v: -sum(len(t) for t in terms if t in json.dumps(v, ensure_ascii=False).lower()))
            else:
                ranked = values
            return ranked[:limit]
        return {**metadata, 'items': select(metadata['items'], 48),
                'dimensions': [{**d, 'values': select(d['values'], 32), 'total_values': len(d['values'])}
                               for d in metadata['dimensions']], 'comments': metadata['comments'][:4],
                'total_items': len(metadata['items']),
                'note': '항목·분류는 일부 후보입니다. 필요한 값이 없으면 metadata에 query 검색어를 추가해 요청하세요.'}
