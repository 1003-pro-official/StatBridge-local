from __future__ import annotations
import re
from .common import UNKNOWN,normalize,number,BLACKLIST,ref_pattern,bad_sentence,sentence_key

CHART_NAMES={'line':'선그래프','spline':'선그래프','column':'막대','bar':'막대','scatter':'산점도','area':'영역','areaspline':'영역','pie':'pie','이미지/사진':'사진·이미지','image':'사진·이미지'}

def canonical_chart(value):
    if value==UNKNOWN:return value
    parts=re.split(r'\s*\+\s*',value)
    names=list(dict.fromkeys(CHART_NAMES.get(x,x) for x in parts))
    return names[0] if len(names)==1 else '혼합'

def choose_description(row,context,used):
    pat=ref_pattern(row['구분'],row['번호'])
    if pat is None:return UNKNOWN,'번호 불명으로 직접 언급 문장을 검증할 수 없음'
    candidates=context.get('direct_sentences',[])
    existing=row['설명']
    # Keep an already correct quote only if the exact quote is located in the source.
    ordered=sorted(candidates,key=lambda x:(sentence_key(x['text'])!=sentence_key(existing),len(x['text']),x['source']))
    for candidate in ordered:
        text=candidate['text']
        if bad_sentence(text) or not pat.search(normalize(text)):continue
        key=sentence_key(text)
        if key in used:continue
        used.add(key);return text,candidate['source']+'; 본문 직접인용'
    return UNKNOWN,'번호 직결 본문 문장 없음 또는 동일 문장 중복 배정 방지'

def infer_chart(row,context):
    shape=row['데이터 형태'];units=row['단위'];series=context.get('series',UNKNOWN)
    if re.search(r'(?:좌축|우축|좌안|우안|왼쪽 축|오른쪽 축)',series+' '+context.get('text','')):
        unit_parts=set(re.findall(r'(?:%p|%|bp|조원|억원|억달러|조달러)',units))
        if len(unit_parts)>=2:return '혼합(추정)','두 지표 축과 서로 다른 단위: '+units
    if '시계열' in shape and not re.search(r'계열\s*0개',shape):
        if re.search(r'시계열,\s*연(?:,|\s)',shape):return '막대(추정)','연도 라벨의 시계열: '+shape
        return '선그래프(추정)','시계열 구조: '+shape
    match=re.search(r'단면,\s*관측\s*(\d+)건',shape)
    if match and int(match.group(1))>=2:return '막대(추정)','범주형 단면 관측: '+shape
    return UNKNOWN,''

UNIT=re.compile(r'\(([^()]{1,65})\)')
def pdf_metadata(context):
    lines=context.get('lines',[]);updates={}
    for i,line in enumerate(lines):
        match=re.match(r'^자료\s*[:：]\s*(.+)',line)
        if match:
            source=match.group(1).strip()
            if source.endswith(',') and i+1<len(lines) and not re.match(r'^(?:주|단위|그림|표)\s*[:：]?',lines[i+1]):source+=' '+lines[i+1]
            if len(source)<=220:updates['사용 데이터·출처']=(source,'자료: '+source)
            break
    units=[]
    for line in lines:
        match=re.match(r'^단위\s*[:：]\s*(.+)',line)
        if match:units.append((match.group(1).strip(),line));continue
        for m in UNIT.finditer(line):
            value=m.group(1).strip()
            if re.fullmatch(r'(?:전년(?:동기)?대비|전기대비|전월대비|연율|계절조정|%p?|bp|[천백십억조만]?\s*(?:원|달러|유로|엔|명|건|개|배)|[A-Z]{3}|\d{2,4}(?:[.년]\s*\d{1,2})?\s*=\s*100)(?:\s*[,/·]\s*(?:%p?|bp|[천백십억조만]?(?:원|달러|명|건)|연율|계절조정))*',value):units.append((value,m.group(0)))
    if units:
        values=list(dict.fromkeys(x[0] for x in units))
        updates['단위']=('; '.join(values),' / '.join(dict.fromkeys(x[1] for x in units)))
    ticks=[]
    for line in lines:
        # Only axis-like numeric lines. Never infer a date range from prose or footnotes.
        if len(line)>90 or re.search(r'[가-힣A-Za-z]',line):continue
        ticks += re.findall(r'(?<!\d)(?:20\d{2}(?:[./]\d{1,2})?|\d{2}[./]\d{1,2})(?!\d)',line)
    ticks=list(dict.fromkeys(ticks))
    if len(ticks)>=3:
        updates['데이터 형태']=(f'시계열, 표시 축 {ticks[0]}~{ticks[-1]}, 관측 주기·계열 수 불명(추정)','축 라벨: '+', '.join(ticks))
    return updates

# Tags are explicit measures as well as estimators/models. Generic economic topics
# (e.g. "대출", "물가") are deliberately not a method tag.
LEXICON=[
 ('지수(FSI)',r'\bFSI\b|금융\s*스트레스\s*지수'),('지수(FVI)',r'\bFVI\b|금융\s*취약성\s*지수'),
 ('지수(PMI)',r'\bPMI\b|구매\s*관리자\s*지수'),('통화지표(M2)',r'\bM2\b'),('통화지표(Lf)',r'\bLf\b'),('통화지표(L)',r'(?<![A-Za-z])L(?![A-Za-z])'),
 ('지수(DXY)',r'\bDXY\b|달러화\s*지수|달러\s*인덱스'),('지수(CSI)',r'\bCSI\b|소비자\s*심리\s*지수'),('지수(BSI)',r'\bBSI\b|기업\s*경기\s*실사\s*지수'),('지수(ESI)',r'\bESI\b|경제\s*심리\s*지수'),
 ('기여도',r'기여도'),('스프레드',r'스프레드|금리\s*(?:차|격차)|수익률\s*격차'),('스트레스테스트',r'스트레스\s*테스트|stress\s*test'),
 ('회귀',r'회귀|regression'),('DSGE',r'\bDSGE\b|동태\s*확률\s*일반\s*균형'),('nowcasting',r'nowcasting|나우\s*캐스팅'),('CGE',r'\bCGE\b|연산\s*가능\s*일반\s*균형'),('VAR',r'\bVAR\b|벡터\s*자기\s*회귀'),
 ('실질',r'실질|real\s+(?:GDP|income)'),('명목',r'명목|nominal'),('성장률',r'성장률'),('증가율',r'증가율'),('변화율',r'변화율|상승률|하락률|변동률'),
 ('잔액',r'잔액'),('비중',r'비중|구성비|점유율'),('비율',r'비율|GDP\s*대비'),('연체율',r'연체율'),('수익률',r'수익률|\bROA\b|\bROE\b'),
 ('자기자본비율',r'자기\s*자본\s*비율|\bCET1\b|\bBIS\s*(?:비율|자본)'),('변동성',r'변동성|volatility'),('상관계수',r'상관\s*계수|correlation'),('평균',r'평균|이동\s*평균'),('분포',r'분포|분위|히스토그램'),
 ('지수(주가지수)',r'주가\s*지수|코스피|\bKOSPI\b|\bNASDAQ\b|\bS&P\s*500\b'),('지수(가격지수)',r'가격\s*지수|물가\s*지수'),('지수(경기선행지수)',r'경기\s*선행\s*지수'),
 ('지수(기타)',r'지수'),('PER',r'\bPER\b|주가\s*수익\s*비율'),('PBR',r'\bPBR\b|주가\s*순자산\s*비율'),('DSR',r'\bDSR\b|총부채\s*원리금\s*상환\s*비율'),('DTI',r'\bDTI\b|총부채\s*상환\s*비율'),('LTV',r'\bLTV\b|담보\s*인정\s*비율'),
 ('레버리지',r'레버리지|leverage'),('가동률',r'가동률'),('고용률',r'고용률'),('실업률',r'실업률'),('계절조정',r'계절\s*조정'),('로그변환',r'로그\s*(?:변환|차분)|logarithm'),('HP 필터',r'\bHP\s*필터|Hodrick'),('GDP갭',r'GDP\s*갭|산출\s*갭'),('확률',r'확률'),('추정',r'추정치|추정\s*결과'),('전망',r'전망치|전망\s*경로'),('순증감',r'순증|순감|순변동|증감액'),
]
OLD_ALIASES={'성장률/변화율':r'성장률|증가율|상승률|하락률|변동률|변화율','지수':r'지수'}

def tags_from_sources(row,context):
    sources=[('제목',row['제목']),('계열',context.get('series',UNKNOWN)),('본문 직접인용',row['설명'])]
    # Local chart text supports explicitly printed measures, not adjacent prose.
    if context.get('caption'):sources.append(('PDF 캡션',context['caption']))
    tags=[];quotes=[]
    for old in row.get('통계기법·지수',UNKNOWN).split(';'):
        old=old.strip()
        pattern=OLD_ALIASES.get(old) or next((p for label,p in LEXICON if label==old),None)
        if pattern:
            for source,text in sources:
                match=re.search(pattern,text,re.I)
                if match:tags.append(old);quotes.append((source,match.group(0)));break
    for tag,pattern in LEXICON:
        for source,text in sources:
            match=re.search(pattern,text,re.I)
            if match:
                if tag not in tags:tags.append(tag);quotes.append((source,match.group(0)))
                break
    if any(t.startswith('지수(') and t!='지수(기타)' for t in tags):tags=[t for t in tags if t!='지수(기타)']
    return '; '.join(tags) if tags else UNKNOWN,quotes
