
# ✅ 기능 확장 코드: lawgg 기능 추가용

import sqlite3
import re
import requests
import xml.etree.ElementTree as ET

API_KEY = '79deed587e6043f291a36420cfd972de'
URL_LAW = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"

# 1. 학력 및 경력 구분 파서 개선
def parse_brf_hst_by_category(raw):
    patterns = r'(전[)\s:]+|현[)\s:]+|▪︎|•|\n)'
    items = re.split(patterns, raw)
    output = {"학력": [], "경력": [], "기타": []}
    i = 0
    while i < len(items) - 1:
        if re.match(patterns, items[i]):
            label = items[i].strip()
            text = items[i + 1].strip()
            if any(x in text for x in ['학교', '학과', '졸업', '대학교']):
                output["학력"].append(text)
            elif any(x in text for x in ['대표', '위원', '사무총장', '근무', '임명']):
                output["경력"].append(text)
            else:
                output["기타"].append(text)
            i += 2
        else:
            i += 1
    return output

# 2. 법률안 상세 요약 추출용
def get_law_summary(row):
    return row.findtext('RST_PROPOSER') or row.findtext('PURPOSE') or '요약 정보 없음'

# 3. 법률안 리스트에서 찬반 점수 조회
def get_vote_score(content_id, content_type):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT vote, COUNT(*) FROM content_votes WHERE content_id=? AND type=? GROUP BY vote", (content_id, content_type))
    score = 0
    for vote, count in c.fetchall():
        if vote == '찬성':
            score += count
        elif vote == '반대':
            score -= count
    conn.close()
    return score

# 4. 제안글 목록 조회수 포함 출력
def show_proposals_with_views():
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.title, IFNULL(v.count, 0) FROM proposals p LEFT JOIN views v ON p.id = v.id AND v.type = 'proposal' ORDER BY p.id DESC")
    for id, title, count in c.fetchall():
        print(f"{id}. {title} 👁 {count}회")
    conn.close()

# 5. 법률안명 자동완성 목록 리턴 (콘솔)
def search_laws_by_keyword(keyword):
    params = {'key': API_KEY, 'numOfRows': 1000}
    res = requests.get(URL_LAW, params=params)
    results = []
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for row in root.findall('.//row'):
            title = row.findtext('BILL_NAME') or ''
            if keyword in title:
                results.append(row)
    return results

def get_matching_laws(keyword):
    results = search_laws_by_keyword(keyword)
    return [row.findtext('BILL_NAME') for row in results]

# 6. 제안글 작성 확장: 제목, 제안자, 법률안명, 게시일, 현황, 문제점, 제안내용
def create_proposal_expanded():
    title = input("제목: ")
    proposer = input("제안자: ")
    law_name = input("법률안명 (자동완성 사용): ")
    posted = input("게시 연월일: ")
    status = input("현황: ")
    problem = input("문제점: ")
    suggestion = input("제안 내용: ")

    # DB 저장
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            proposer TEXT,
            law_name TEXT,
            posted TEXT,
            status TEXT,
            problem TEXT,
            suggestion TEXT
        )
    ''')
    c.execute("INSERT INTO proposals (title, proposer, law_name, posted, status, problem, suggestion) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              (title, proposer, law_name, posted, status, problem, suggestion))
    conn.commit()
    conn.close()
    print("제안이 성공적으로 등록되었습니다.")
