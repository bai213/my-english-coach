import streamlit as st

# ================= 0. 页面配置 =================
st.set_page_config(page_title="Hardcore English Coach", layout="wide")

import sqlite3
import json
import os
from datetime import datetime
from openai import OpenAI

# ================= 数据库工具函数 (新增：解决并发锁定) =================
def run_query(db_file, query, params=(), fetch=False, commit=False):
    """通用的数据库执行函数，确保线程安全"""
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit:
            conn.commit()
        if fetch:
            return c.fetchall()
        return None

# ================= 日志表初始化 =================
def init_visit_log():
    run_query('visit_log.db', '''
    CREATE TABLE IF NOT EXISTS visit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login_time TEXT, user_type TEXT, ip TEXT
    )''', commit=True)

init_visit_log()

def log_visit(user_type):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = st.runtime.media_file_storage.get_session_id()
    run_query('visit_log.db', "INSERT INTO visit_log (login_time, user_type, ip) VALUES (?, ?, ?)",
              (now, user_type, ip), commit=True)

def show_visit_log():
    st.subheader("👀 访客登录记录（仅管理员可见）")
    logs = run_query('visit_log.db', "SELECT login_time, user_type, ip FROM visit_log ORDER BY id DESC LIMIT 50", fetch=True)
    if logs:
        for t, ut, ip in logs:
            st.markdown(f"**{t}** | {ut} | 会话：{ip[:12]}...")
    else:
        st.info("暂无访客记录")

# ================= 0.5 验证系统 =================
with st.sidebar:
    st.header("🔒 专属验证")
    show_pwd = st.checkbox("显示暗号（输入中文请勾选）")
    pwd_type = "default" if show_pwd else "password"
    pwd = st.text_input("🔑 请输入暗号：", type=pwd_type)

ADMIN_PWD = st.secrets["ADMIN_PWD"]
GUEST_PWD = st.secrets["GUEST_PWD"]

if pwd == ADMIN_PWD:
    db_name = "notebook.db"
    log_visit("ADMIN")
    st.sidebar.success("👑 欢迎回来，主人！")
elif pwd == GUEST_PWD:
    db_name = "guest.db"
    log_visit("GUEST")
    st.sidebar.info("👋 欢迎体验！")
elif pwd != "":
    st.sidebar.warning("✋ 停！暗号不对。")
    st.stop()
else:
    st.title("🔒 零容忍英语训练营 (已锁定)")
    st.info("👈 请在左侧侧边栏输入暗号以解锁内容。")
    st.markdown("<style>header, footer, .stAppToolbar {display:none !important;}</style>", unsafe_allow_html=True)
    st.stop()

# ================= 1. 注入 CSS =================
st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    .stAppToolbar { display: none !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }
    footer { visibility: hidden !important; }
    .stDeployButton { display:none !important; }

    section[data-testid="stSidebar"] button[kind="secondary"] { font-size: 0.75em !important; }
    .xp-bar-bg { background: #2c2c2c; border-radius: 10px; height: 22px; width: 100%; position: relative; overflow: hidden; }
    .xp-bar-fill { height: 100%; border-radius: 10px; background: linear-gradient(90deg, #f39c12, #e74c3c, #e91e63); transition: width 0.5s ease; }
    .xp-bar-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 0.75em; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
    .badge { display: inline-block; padding: 4px 10px; margin: 3px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
    .badge-gold { background: linear-gradient(135deg, #f7dc6f, #f0b027); color: #333; }
    .badge-silver { background: linear-gradient(135deg, #d5d8dc, #aab7b8); color: #333; }
    .badge-bronze { background: linear-gradient(135deg, #e8c40a, #cd9b6e); color: #333; }
    .badge-locked { background: #3a3a3a; color: #777; }
    .streak-fire { font-size: 1.4em; }
    .mode-tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; margin-left: 8px; }
    .mode-roast { background: #e74c3c; color: white; }
    .mode-hype { background: #2ecc71; color: white; }
    .mode-normal { background: #3498db; color: white; }
</style>
""", unsafe_allow_html=True)

# ================= 2. 数据库配置初始化 =================
def init_db(database_file):
    with sqlite3.connect(database_file) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS mistakes (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, source TEXT, wrong_sentence TEXT, correction TEXT, explanation_en TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS vocab (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, word TEXT, definition_en TEXT, translation_zh TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, scenario TEXT, chat_log TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS user_stats (id INTEGER PRIMARY KEY CHECK (id = 1), xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, streak INTEGER DEFAULT 0, last_active TEXT, total_messages INTEGER DEFAULT 0, perfect_messages INTEGER DEFAULT 0, total_sessions INTEGER DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS achievements (id TEXT PRIMARY KEY, name TEXT, description TEXT, icon TEXT, tier TEXT, unlocked INTEGER DEFAULT 0, unlock_date TEXT)')
        c.execute("INSERT OR IGNORE INTO user_stats (id, xp, level, streak, total_messages, perfect_messages, total_sessions) VALUES (1, 0, 1, 0, 0, 0, 0)")
        ach_def = [
            ("first_blood", "First Blood", "Send your first message", "⚔️", "bronze"),
            ("chatterbox", "Chatterbox", "Send 50 messages", "💬", "silver"),
            ("marathon", "Marathon", "Send 200 messages", "🏃", "gold"),
            ("perfectionist", "Perfectionist", "10 error-free messages", "✨", "silver"),
            ("flawless", "Flawless Legend", "50 error-free messages", "💎", "gold"),
            ("streak_3", "Getting Warm", "3-day streak", "🔥", "bronze"),
            ("streak_7", "On Fire", "7-day streak", "🔥", "silver"),
            ("streak_30", "Unstoppable", "30-day streak", "🔥", "gold"),
            ("vocab_10", "Word Collector", "Save 10 words", "📚", "bronze"),
            ("vocab_50", "Walking Dictionary", "Save 50 words", "🧠", "gold"),
            ("level_5", "Rising Star", "Reach level 5", "⭐", "bronze"),
            ("level_10", "Veteran", "Reach level 10", "🏅", "silver"),
            ("level_25", "English Master", "Reach level 25", "👑", "gold"),
            ("sessions_10", "Regular", "Complete 10 chat sessions", "🎯", "silver"),
            ("roast_survivor", "Roast Survivor", "Survive 10 msgs in Roast mode", "🌶️", "silver"),
        ]
        for a in ach_def:
            c.execute("INSERT OR IGNORE INTO achievements (id, name, description, icon, tier) VALUES (?, ?, ?, ?, ?)", a)
        conn.commit()

init_db(db_name)

# ================= 3. 游戏化系统逻辑 (已修正) =================
def get_stats():
    res = run_query(db_name, "SELECT xp, level, streak, last_active, total_messages, perfect_messages, total_sessions FROM user_stats WHERE id = 1", fetch=True)
    row = res[0]
    return {"xp": row[0], "level": row[1], "streak": row[2], "last_active": row[3], "total_messages": row[4], "perfect_messages": row[5], "total_sessions": row[6]}

def add_xp(amount, perfect=False, is_roast=False):
    stats = get_stats()
    xp, level = stats["xp"] + amount, stats["level"]
    total_msg, perfect_msg = stats["total_messages"] + 1, stats["perfect_messages"] + (1 if perfect else 0)
    while xp >= (80 + (level - 1) * 30):
        xp -= (80 + (level - 1) * 30)
        level += 1
    today_str = datetime.today().date().isoformat()
    streak = stats["streak"]
    if stats["last_active"] != today_str:
        try:
            from datetime import date
            last_date = date.fromisoformat(stats["last_active"])
            streak = streak + 1 if last_date.toordinal() == date.today().toordinal() - 1 else 1
        except: streak = 1
    run_query(db_name, "UPDATE user_stats SET xp=?, level=?, streak=?, last_active=?, total_messages=?, perfect_messages=? WHERE id=1",
              (xp, level, streak, today_str, total_msg, perfect_msg), commit=True)
    check_achievements(level, streak, total_msg, perfect_msg, stats["total_sessions"], is_roast)

def increment_sessions():
    run_query(db_name, "UPDATE user_stats SET total_sessions = total_sessions + 1 WHERE id = 1", commit=True)
    s = get_stats()
    check_achievements(s["level"], s["streak"], s["total_messages"], s["perfect_messages"], s["total_sessions"], False)

def check_achievements(level, streak, total_msg, perfect_msg, sessions, is_roast):
    unlocks = []
    if total_msg >= 1: unlocks.append("first_blood")
    if total_msg >= 50: unlocks.append("chatterbox")
    if total_msg >= 200: unlocks.append("marathon")
    if perfect_msg >= 10: unlocks.append("perfectionist")
    if perfect_msg >= 50: unlocks.append("flawless")
    if streak >= 3: unlocks.append("streak_3")
    if streak >= 7: unlocks.append("streak_7")
    if streak >= 30: unlocks.append("streak_30")
    if level >= 5: unlocks.append("level_5")
    if level >= 10: unlocks.append("level_10")
    if level >= 25: unlocks.append("level_25")
    if sessions >= 10: unlocks.append("sessions_10")
    
    vc_res = run_query(db_name, "SELECT COUNT(*) FROM vocab", fetch=True)
    if vc_res[0][0] >= 10: unlocks.append("vocab_10")
    if vc_res[0][0] >= 50: unlocks.append("vocab_50")
    
    rm = st.session_state.get("roast_msg_count", 0) + (1 if is_roast else 0)
    if is_roast: st.session_state["roast_msg_count"] = rm
    if rm >= 10: unlocks.append("roast_survivor")
    
    today = datetime.today().date().isoformat()
    for aid in unlocks:
        run_query(db_name, "UPDATE achievements SET unlocked=1, unlock_date=? WHERE id=? AND unlocked=0", (today, aid), commit=True)

def render_stats_bar():
    stats = get_stats()
    xp_needed = 80 + (stats["level"] - 1) * 30
    pct = min(stats["xp"] / xp_needed * 100, 100)
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        titles = {1: "Newbie", 5: "Rising Star", 10: "Veteran", 20: "Master", 25: "Legend"}
        title = next((t for lv, t in sorted(titles.items(), reverse=True) if stats["level"] >= lv), "Newbie")
        st.markdown(f"### Lv.{stats['level']} — {title}")
    with col2:
        fire = "🔥" * min(stats["streak"], 5)
        st.markdown(f"<span class='streak-fire'>{fire if fire else '❄️'}</span> **{stats['streak']}天连续**", unsafe_allow_html=True)
    with col3:
        acc = (stats["perfect_messages"] / stats["total_messages"] * 100) if stats["total_messages"] > 0 else 0
        st.markdown(f"🎯 **正确率 {acc:.0f}%**")
    st.markdown(f'<div class="xp-bar-bg"><div class="xp-bar-fill" style="width: {pct}%;"></div><div class="xp-bar-text">{stats["xp"]} / {xp_needed} XP</div></div>', unsafe_allow_html=True)
    st.write("")

# ================= 4. API & AI 性格 (已修正 Hype 模式) =================
api_key = st.secrets["DEEPSEEK_API_KEY"]
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

MODES = {
    "🔥 毒舌模式 (Roast)": {"tag": "mode-roast", "text": "ROAST", "extra": "Sarcastic, savage. Roast mistakes hard."},
    "🌈 夸夸模式 (Hype)": {"tag": "mode-hype", "text": "HYPE", "extra": "Super enthusiastic cheerleader. Use normal sentence casing (no all-caps), but lots of exclamation marks!"},
    "😎 正常模式 (Normal)": {"tag": "mode-normal", "text": "NORMAL", "extra": "Friendly, natural conversation partner."}
}

def chat_and_correct_agent(user_text, scenario, history=None, personality="😎 正常模式 (Normal)"):
    mode = MODES.get(personality, MODES["😎 正常模式 (Normal)"])
    system_prompt = f"English teacher. Scenario: {scenario}. Personality: {mode['extra']}\nTask: 1. Reply in character. 2. Point out errors. Chinese = error. JSON ONLY: {{\"ai_reply\": \"...\", \"errors\": [{{ \"wrong_sentence\": \"...\", \"correction\": \"...\", \"explanation_en\": \"...\" }}]}}"
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for m in history: messages.append({"role": m["role"], "content": m.get("content", "")})
    else: messages.append({"role": "user", "content": user_text})
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=messages, response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except: return {"ai_reply": "Connection error.", "errors": []}

# ================= 7. 界面渲染 =================
render_stats_bar()
if pwd == ADMIN_PWD: show_visit_log(); st.divider()

st.title("🔥 Zero Tolerance English Bootcamp")
t1, t2, t3, t4, t5 = st.tabs(["🗣️ Roleplay", "📝 Journal", "📖 Notebook", "🕰️ History", "🏆 Achievements"])

with t1:
    c1, c2 = st.columns([1, 2])
    with c1:
        personality = st.radio("AI Personality:", list(MODES.keys()), index=2)
    with c2:
        selected = st.selectbox("Scenario:", ["🎓 University Dorm", "💻 Tech Lab", "🎮 Voice Chat", "👔 Job Interview", "🤬 Stubborn Troll", "🕵️ Police Interrogation"])
        current_scenario = selected

    if current_scenario:
        sk = f"{current_scenario}_{personality}"
        if "messages" not in st.session_state or st.session_state.get("state_key") != sk:
            st.session_state.messages = [{"role": "assistant", "content": "Hey there! Ready to start?"}]
            st.session_state.state_key = sk

        if st.button("💾 Save & End Session"):
            if len(st.session_state.messages) > 1:
                run_query(db_name, "INSERT INTO chat_history (scenario, chat_log) VALUES (?, ?)", (current_scenario, json.dumps(st.session_state.messages)), commit=True)
                increment_sessions(); add_xp(30)
                st.session_state.messages = [{"role": "assistant", "content": "Session saved!"}]
                st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg.get("errors"):
                    for e in msg["errors"]: st.error(f"❌ {e['wrong_sentence']} -> ✅ {e['correction']}")
                st.markdown(msg["content"])

        if user_in := st.chat_input("English only..."):
            st.session_state.messages.append({"role": "user", "content": user_in})
            with st.chat_message("user"): st.markdown(user_in)
            res = chat_and_correct_agent(user_in, current_scenario, st.session_state.messages, personality)
            errs = res.get("errors", [])
            st.session_state.messages.append({"role": "assistant", "content": res.get("ai_reply", ""), "errors": errs})
            is_p = len(errs) == 0
            add_xp(20 if is_p else 10, perfect=is_p, is_roast="毒舌" in personality)
            for e in errs:
                run_query(db_name, "INSERT INTO mistakes (source, wrong_sentence, correction, explanation_en) VALUES (?, ?, ?, ?)", ("Chat: " + current_scenario, e['wrong_sentence'], e['correction'], e['explanation_en']), commit=True)
            st.rerun()

with t3:
    st.subheader("Knowledge Base")
    recs = run_query(db_name, "SELECT id, date, source, wrong_sentence, correction, explanation_en FROM mistakes ORDER BY id DESC", fetch=True)
    for r in recs:
        with st.expander(f"📅 {r[1]} | {r[2]}"):
            st.markdown(f"❌ {r[3]}\n\n✅ {r[4]}")
            if st.button("🗑️", key=f"del_m_{r[0]}"):
                run_query(db_name, "DELETE FROM mistakes WHERE id=?", (r[0],), commit=True); st.rerun()

# 侧边栏生词本也已改为安全模式
with st.sidebar:
    st.divider(); st.subheader("Vocab Book")
    nw = st.text_input("Quick search:")
    if st.button("Search & Save"):
        if nw:
            res = run_query(db_name, "SELECT word FROM vocab WHERE word=?", (nw,), fetch=True)
            if not res:
                run_query(db_name, "INSERT INTO vocab (word, definition_en, translation_zh) VALUES (?, ?, ?)", (nw, "Def", "中"), commit=True)
                st.success("Saved!")
