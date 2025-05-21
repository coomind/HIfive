
# lawgg 전체 콘솔 기반 통합 코드 (기능별 분류)
# API + 검색 + 투표 + 댓글 + 제안 + 자동완성 + IP 차단 + 신고 + 중복 방지 포함
import sqlite3
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

API_KEY = 'YOUR_API_KEY'
URL_MEMBER = "https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER"
URL_LAW = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"

# -------------------- API 연동 -------------------- #
def search_member(name):
    params = {'key': API_KEY, 'NAAS_NM': name}
    response = requests.get(URL_MEMBER, params=params)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        return root.findall('.//row')
    return []

def display_member_info(row):
    def get(tag): return row.findtext(tag) or "정보 없음"
    print(f"이름: {get('NAAS_NM')}, 정당: {get('PLPT_NM')}")
    print(f"생년월일: {get('BIRDY_DT')}, 성별: {get('NTR_DIV')}")
    print(f"위원회: {get('BLNG_CMIT_NM')}")
    print("📘 약력:")
    brf = get('BRF_HST')
    if brf != "정보 없음":
        for line in parse_brf_hst(brf): print(f"- {line}")
    else:
        print("약력 정보 없음")

def parse_brf_hst(raw):
    patterns = r'(전[)\s:]+|현[)\s:]+|▪︎|•|\n)'
    items = re.split(patterns, raw)
    return [items[i+1].strip() for i in range(0, len(items)-1) if re.match(patterns, items[i])]

# -------------------- 법률안 -------------------- #
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

def get_vote_score(content_id, content_type):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT vote, COUNT(*) FROM content_votes WHERE content_id=? AND type=? GROUP BY vote", (content_id, content_type))
    score = 0
    for vote, count in c.fetchall():
        score += count if vote == '찬성' else -count
    conn.close()
    return score

# -------------------- 제안 -------------------- #
def create_proposal():
    title = input("제목: ")
    proposer = input("제안자: ")
    law = input("법률안명: ")
    posted = input("게시일: ")
    status = input("현황: ")
    problem = input("문제점: ")
    suggestion = input("제안내용: ")

    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, proposer TEXT, law_name TEXT,
        posted TEXT, status TEXT, problem TEXT, suggestion TEXT)''')
    c.execute("INSERT INTO proposals (title, proposer, law_name, posted, status, problem, suggestion) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (title, proposer, law, posted, status, problem, suggestion))
    conn.commit()
    conn.close()
    print("✅ 제안 등록 완료")

# -------------------- 댓글 + 투표 -------------------- #
def init_reporting_tables():
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS content_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_id TEXT, type TEXT, user TEXT, comment TEXT, ip TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS content_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_id TEXT, type TEXT, vote TEXT, ip TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_id TEXT, type TEXT, ip TEXT, reason TEXT,
        reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_ips (
        ip TEXT PRIMARY KEY, reason TEXT,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def is_ip_banned(ip):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned_ips WHERE ip=?", (ip,))
    result = c.fetchone()
    conn.close()
    return result is not None

def report_content(content_id, content_type, ip, reason="신고"):
    if is_ip_banned(ip): return
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO reports (content_id, type, ip, reason) VALUES (?, ?, ?, ?)",
              (content_id, content_type, ip, reason))
    c.execute("SELECT COUNT(*) FROM reports WHERE ip=?", (ip,))
    if c.fetchone()[0] >= 3:
        c.execute("INSERT OR IGNORE INTO banned_ips (ip, reason) VALUES (?, ?)",
                  (ip, "신고 누적"))
    conn.commit()
    conn.close()

def has_already_interacted(table, content_id, content_type, ip):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute(f"SELECT 1 FROM {table} WHERE content_id=? AND type=? AND ip=?", (content_id, content_type, ip))
    result = c.fetchone()
    conn.close()
    return result is not None

def comment_secure(content_id, content_type, ip, user, text):
    if is_ip_banned(ip): return
    if has_already_interacted("content_comments", content_id, content_type, ip): return
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO content_comments (content_id, type, user, comment, ip) VALUES (?, ?, ?, ?, ?)",
              (content_id, content_type, user, text, ip))
    conn.commit()
    conn.close()

def vote_secure(content_id, content_type, ip, vote_value):
    if is_ip_banned(ip): return
    if has_already_interacted("content_votes", content_id, content_type, ip): return
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO content_votes (content_id, type, vote, ip) VALUES (?, ?, ?, ?)",
              (content_id, content_type, vote_value, ip))
    conn.commit()
    conn.close()
