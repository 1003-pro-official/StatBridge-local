"""Short names for prose only; source labels and lookup keys stay intact."""
import re


def narrative_name(label, *, table_name=''):
    def parts(value):
        text = str(value or '')
        # Repeated removal handles nested annotations without eating the name.
        while True:
            clean = re.sub(r'\([^()]*\)|（[^（）]*）', '', text)
            if clean == text:
                break
            text = clean
        text = re.sub(r'\bDT_[A-Z0-9_]+\b', '', text, flags=re.I)
        result = []
        for part in re.split(r'[·ㆍ]', text):
            part = re.sub(r'\s+\d+\s*\)\s*$', '', part)
            part = re.sub(r'\s+', ' ', part).strip(' ·ㆍ,')
            if part:
                result.append(part)
        return result

    names = parts(label)
    table = parts(table_name)
    generic = {'신규취급액', '신규취급액 기준', '잔액', '잔액 기준', '대출평균', '저축성수신'}
    if table and (not names or names[0] in generic):
        return table[0]
    return names[0] if names else table[0] if table else '해당 지표'
