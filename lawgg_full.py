
import requests
import xml.etree.ElementTree as ET
import re
import webbrowser
import sqlite3

API_KEY = '79deed587e6043f291a36420cfd972de'
URL_MEMBER = "https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER"
URL_LAW = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"

# === DB 초기화 ===
def init_db():
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS views (
        id TEXT,
        type TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY(id, type)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS content_comments (
        content_id TEXT,
        type TEXT,
        user TEXT,
        comment TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS content_votes (
        content_id TEXT,
        type TEXT,
        vote TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT
    )''')
    conn.commit()
    conn.close()

# === API ===
def search_member(name):
    params = {'key': API_KEY, 'NAAS_NM': name}
    res = requests.get(URL_MEMBER, params=params)
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        return root.findall('.//row')
    return None

def search_laws_by_keyword(keyword):
    params = {'key': API_KEY, 'numOfRows': 1000}
    res = requests.get(URL_LAW, params=params)
    results = []
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for row in root.findall('.//row'):
            title = row.findtext('BILL_NAME') or ''
            summary = row.findtext('RSMN') or ''
            if keyword in title or keyword in summary:
                results.append(row)
    return results

def get_laws_all_ages_by_name(name, min_age=1, max_age=22):
    grouped = {}
    for age in range(min_age, max_age+1):
        params = {'key': API_KEY, 'AGE': age, 'numOfRows': 1000}
        res = requests.get(URL_LAW, params=params)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            laws = []
            for row in root.findall('.//row'):
                if name in (row.findtext('PUBL_PROPOSER') or ''):
                    laws.append(row)
            if laws:
                grouped[age] = laws
    return grouped

# === 통합 기능 ===
def track_views(content_id, content_type):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT count FROM views WHERE id=? AND type=?", (content_id, content_type))
    row = c.fetchone()
    if row:
        c.execute("UPDATE views SET count = count + 1 WHERE id=? AND type=?", (content_id, content_type))
    else:
        c.execute("INSERT INTO views (id, type, count) VALUES (?, ?, 1)", (content_id, content_type))
    conn.commit()
    conn.close()

def vote(content_id, content_type):
    vote = input("찬성 or 반대: ").strip()
    if vote not in ('찬성', '반대'):
        print("유효하지 않은 입력입니다.")
        return
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO content_votes (content_id, type, vote) VALUES (?, ?, ?)", (content_id, content_type, vote))
    conn.commit()
    conn.close()

def show_vote_score(content_id, content_type):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT vote, COUNT(*) FROM content_votes WHERE content_id=? AND type=? GROUP BY vote", (content_id, content_type))
    score = 0
    for vote, count in c.fetchall():
        if vote == '찬성':
            score += count
        elif vote == '반대':
            score -= count
    color = '\033[94m' if score >= 0 else '\033[91m'
    print(f"🗳️ 투표 점수: {color}{score:+d}\033[0m")
    conn.close()

def comment(content_id, content_type):
    user = input("이름: ")
    text = input("댓글 입력: ")
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO content_comments (content_id, type, user, comment) VALUES (?, ?, ?, ?)", (content_id, content_type, user, text))
    conn.commit()
    conn.close()

def show_comments(content_id, content_type):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT user, comment FROM content_comments WHERE content_id=? AND type=?", (content_id, content_type))
    rows = c.fetchall()
    print("💬 댓글:")
    for user, comment in rows:
        print(f"- {user}: {comment}")
    conn.close()

def get_top_views(content_type, limit=5):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT id FROM views WHERE type=? ORDER BY count DESC LIMIT ?", (content_type, limit))
    top_ids = [row[0] for row in c.fetchall()]
    conn.close()
    return top_ids

# === 입법 제안 ===
def create_proposal(title, content):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("INSERT INTO proposals (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()

def show_proposals():
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM proposals ORDER BY id DESC")
    for id, title in c.fetchall():
        print(f"{id}. {title}")
    conn.close()

def display_proposal_detail(proposal_id):
    conn = sqlite3.connect('lawgg.db')
    c = conn.cursor()
    c.execute("SELECT title, content FROM proposals WHERE id=?", (proposal_id,))
    row = c.fetchone()
    if row:
        print(f"제목: {row[0]}
내용: {row[1]}")
        track_views(str(proposal_id), 'proposal')
        show_vote_score(str(proposal_id), 'proposal')
        show_comments(str(proposal_id), 'proposal')
        vote(str(proposal_id), 'proposal')
        comment(str(proposal_id), 'proposal')
    conn.close()
