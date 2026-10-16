"""Recovery actions describe the failing step, never inferred request dates."""
import re


def recovery_question(message, stage='query', *, issue=None):
    text = str(message)[:1200]
    if issue is None:
        if any(word in text for word in ('API_KEY', 'API 키', '권한', '설정이 필요')):
            issue = 'configuration'
        elif re.search(r'호출\s*제한|요청이\s*많|HTTP 429', text, re.I):
            issue = 'rate_limit'
        elif '전년 같은 시점의 값이 없거나 0' in text or '금리·비중·비율의 전년동기 비교' in text:
            issue='calculation'
        elif re.search(r'(기간|날짜|시작일|종료일|시점).{0,30}(선택해|잘못|형식|범위|없습니다|이후|이전)|시작일.{0,20}종료일', text):
            issue = 'period'
        elif re.search(r'HTTP (?:429|5\d\d)|timeout|timed out|연결.*실패|호출.*실패|일시적|network', text, re.I):
            issue = 'connection'
        else:
            issue = 'input'
    actions = {
        'no_match': ('지원 목록에서 확인되지 않은 지표를 수정해 주세요. 입력하신 조회 기간은 유지됩니다.', [('revise', '질문 수정'), ('table', '지원 통계표 찾아보기')]),
        'period': ('조회 기간의 오류를 확인하고 시작일과 종료일을 수정해 주세요.', [('period', '기간 수정'), ('revise', '질문 수정')]),
        'configuration': ('연결 설정과 권한을 확인한 뒤 다시 실행해 주세요.', [('retry', '설정 후 다시 시도')]),
        'rate_limit': ('호출 제한 대기 시간이 안내됐다면 그 시간이 지난 뒤 같은 요청을 다시 시도해 주세요. 현재 작업은 유지됩니다.', [('retry', '대기 후 같은 요청 다시 시도'), ('revise', '질문 수정')]),
        'connection': ('조회 연결에 실패했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.', [('retry', '같은 요청 다시 시도'), ('revise', '질문 수정')]),
        'calculation': (text+' 원자료 수준을 표시할지, 다른 비교 기준을 사용할지 질문을 수정해 주세요. 현재 통계표와 조회 조건은 유지됩니다.', [('revise', '계산 기준·질문 수정')]+([] if '금리·비중·비율' in text else [('period','비교 기간 변경')])),
        'input': ('안내된 오류에 해당하는 입력을 수정해 주세요.', [('revise', '수정 내용 보완' if stage == 'edit' else '질문 수정')]),
    }
    question, choices = actions.get(issue, actions['input'])
    if issue == 'input' and stage == 'edit' and ('?' in text or '알려' in text or '선택' in text):
        question = text
    return {'stage': stage, 'issue': issue, 'message': text, 'question': question,
            'choices': [{'id': key, 'label': label} for key, label in choices], 'preserveState': True}
