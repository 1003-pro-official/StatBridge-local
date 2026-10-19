"""Curated acquisition guidance, never model-invented links or automatic imports."""
import re

def input_guidance(slot, query=''):
    name=slot['required_data']; text=name+' '+slot.get('reason','')
    base={'searchTerms':name[:120], 'verifiedAt':'2026-10-19', 'links':[],
          'checklist':['요청한 지표·지역·항목이 일치하는지 확인해 주세요.', '표시기간과 필요한 과거 이력을 포함하고 주기·단위·기준연도를 확인해 주세요.',
                       '파일의 source에 기관·통계표명 또는 자체 자료의 작성 기준을 기록해 주세요.']}
    if re.search(r'가상|합성|시험용|검증용',text) or re.search(r'가상|합성',query) and re.search(r'사용자|비용지수',name):
        return {**base,'kind':'self_provided','title':'직접 작성하는 시험 자료입니다',
                'description':'이 요청의 가상·합성 지수에 대응하는 공식 다운로드 자료는 안내할 수 없습니다. 사용자가 정한 실제 시험값과 산정 기준을 양식에 입력해 주세요. 공식 지수로 대체하거나 관측값을 만들어 제공하지 않습니다.'}
    if re.search(r'매출|사내|자사|개인|장부|사용자.*비용',name):
        return {**base,'kind':'self_provided','title':'보유한 원자료를 준비해 주세요',
                'description':'회사·개인의 회계 장부나 원가 관리 자료에서 해당 기간의 값을 확인해 주세요. 공개된 공식 자료가 있다고 가정하지 않습니다.'}
    if re.search(r'\bDXY\b|달러\s*인덱스|달러\s*지수|dollar\s*index',name,re.I):
        return {**base,'kind':'official_product','title':'ICE의 DXY 원지수를 확인해 주세요',
                'description':'정확한 자료명은 ICE U.S. Dollar Index (DXY/USDX)입니다. ICE 공식 페이지에서 지수 제공과 심볼 DXY를 확인했습니다. 과거 일별 종가·월평균 자료는 ICE 또는 해당 지수를 제공하는 정식 데이터 공급자에게 기간·이용권한을 확인해 주세요. 무료 파일 다운로드 가능 여부는 확인되지 않았습니다. 선물 가격이나 FRED 무역가중 달러 지수로 대체하지 마세요.',
                'links':[{'label':'ICE Currency Indices · DXY','url':'https://www.ice.com/fixed-income-data-services/index-solutions/currency-indices','note':'DXY 원지수 확인 → 과거 데이터 제공·라이선스 문의'}]}
    if re.search(r'환율|exchange\s*rate',name,re.I):
        directory=[(r'\bJPY\b|일본|엔화','일본 엔','ja'),(r'\bEUR\b|유로','유로','eu'),
            (r'\bGBP\b|영국|파운드','영국 파운드','uk'),(r'\bCAD\b|캐나다','캐나다 달러','ca'),
            (r'\bSGD\b|싱가포르','싱가포르 달러','si'),(r'\bINR\b|인도(?!네시아)|루피(?!아)','인도 루피','in'),
            (r'\bMXN\b|멕시코','멕시코 페소','mx'),(r'\bAUD\b|호주','호주 달러','al'),
            (r'\bKRW\b|한국|원화','한국 원','ko'),(r'\bCNY\b|중국|위안','중국 위안','ch')]
        indonesia=bool(re.search(r'\bIDR\b|인도네시아|루피아',name,re.I))
        country=next(((label,code) for pattern,label,code in directory if re.search(pattern,name,re.I)),None)
        links=[{'label':'한국은행 ECOS','url':'https://ecos.bok.or.kr/','note':'통계검색 → 해당 통화의 대미달러환율 → 일별/월평균 및 기간 확인'}]
        if indonesia:
            links.append({'label':'Bank Indonesia · JISDOR USD/IDR','url':'https://www.bi.go.id/en/statistik/informasi-kurs/jisdor/default.aspx','note':'JISDOR 원자료 · 기간별 관측값과 단위 IDR/USD 확인'})
        elif country:
            quote={'ja':'JPY/USD (1달러당 엔)','eu':'USD/EUR (1유로당 달러)','uk':'USD/GBP (1파운드당 달러)',
                'ca':'CAD/USD (1달러당 캐나다 달러)','si':'SGD/USD (1달러당 싱가포르 달러)',
                'in':'INR/USD (1달러당 루피)','mx':'MXN/USD (1달러당 페소)','al':'USD/AUD (1호주 달러당 미국 달러)',
                'ko':'KRW/USD (1달러당 원)','ch':'CNY/USD (1달러당 위안)'}[country[1]]
            links.append({'label':'연준 H.10 · '+country[0]+' 과거 환율','url':'https://www.federalreserve.gov/releases/h10/hist/dat00_'+country[1]+'.htm','note':'공식 페이지 단위: '+quote+' · Data Download에서 기간 선택'})
        else:
            links.append({'label':'연준 H.10 · 통화별 과거 환율','url':'https://www.federalreserve.gov/releases/h10/hist/','note':'국가/통화 선택 → Historical rates → 기간과 호가 방향 확인'})
        return {**base,'kind':'official_series_directory','title':'통화별 대미환율 원자료 입수처',
                'description':('인도네시아 루피아는 연준 H.10 목록에 없습니다. Bank Indonesia의 JISDOR USD/IDR 원자료를 확인해 주세요. ' if indonesia else '연준 H.10 공식 페이지에서 통화별 일별 환율과 자료 정의를 확인했습니다. 뉴욕 정오 매입환율이므로 한국은행 자료의 관측시각과 같다고 가정하지 마세요. ')+ '한국은행 ECOS는 해당 통화의 대미달러환율 검색 후보입니다. 필요한 과거 수록기간과 휴일 결측은 원자료에서 확인해 주세요. 월평균을 직접 만들 경우 집계 기준을 먼저 정해야 합니다.',
                'links':links,
                'checklist':base['checklist']+['단위통화/USD와 USD/단위통화를 구별하고 통화 코드·관측시각을 기록해 주세요.']}
    links=[{'label':'KOSIS 국가통계포털','url':'https://kosis.kr/','note':'자료명으로 검색 → 항목·기간·주기 선택 → 다운로드'}]
    if re.search(r'금리|환율|통화|국민|물가|생산|수출|수입|금융',text):
        links.append({'label':'한국은행 ECOS','url':'https://ecos.bok.or.kr/','note':'통계검색에서 자료명과 기간·단위를 확인해 주세요.'})
    else:
        links.append({'label':'공공데이터포털','url':'https://www.data.go.kr/','note':'파일데이터 검색에서 제공기관과 수록기간을 확인해 주세요.'})
    return {**base,'kind':'search_candidates','title':'자료를 찾아볼 공식 사이트', 'links':links,
            'description':'공식 사이트의 존재를 확인한 검색 후보입니다. 해당 지표·기간의 파일 제공 여부를 확인한 것은 아닙니다. 승인 API 밖 자료는 자동으로 가져오지 않으며 직접 확인한 파일만 올려 주세요.'}
