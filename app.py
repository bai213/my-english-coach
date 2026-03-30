import streamlit as st

# ================= 0. 页面配置（必须是第一个 st 命令）=================
st.set_page_config(page_title="Hardcore English Coach", layout="wide")

import sqlite3
import json
import os
from datetime import datetime
from openai import OpenAI

# ================= 日志表初始化 =================
def init_visit_log():
    conn = sqlite3.connect('visit_log.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS visit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login_time TEXT,
        user_type TEXT,
        ip TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_visit_log()

# 记录访客
def log_visit(user_type):
    try:
        conn = sqlite3.connect('visit_log.db', check_same_thread=False)
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = st.runtime.media_file_storage.get_session_id()
        c.execute("INSERT INTO visit_log (login_time, user_type, ip) VALUES (?, ?, ?)",
                  (now, user_type, ip))
        conn.commit()
        conn.close()
    except:
        pass

# 管理员查看日志
def show_visit_log():
    st.subheader("👀 访客登录记录（仅管理员可见）")
    try:
        conn = sqlite3.connect('visit_log.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT login_time, user_type, ip FROM visit_log ORDER BY id DESC LIMIT 50")
        logs = c.fetchall()
        conn.close()
        if logs:
            for t, ut, ip in logs:
                st.markdown(f"**{t}** | {ut} | 会话：{ip[:12]}...")
        else:
            st.info("暂无访客记录")
    except:
        st.error("读取日志失败")

# ================= 0.5 终极防盗门：平行宇宙双账号系统 =================
# 特别优化：加入暗号可见性切换，解决 iPad 无法输入中文的问题
with st.sidebar:
    st.header("🔒 专属验证")
    show_pwd = st.checkbox("显示暗号（输入中文请勾选）", help="iPad用户请勾选此项以唤出中文输入法")
    pwd_type = "default" if show_pwd else "password"
    pwd = st.text_input("🔑 请输入暗号：", type=pwd_type)

# 从 Streamlit Secrets 安全读取密码
ADMIN_PWD = st.secrets["ADMIN_PWD"]
GUEST_PWD = st.secrets["GUEST_PWD"]

if pwd == ADMIN_PWD:
    db_name = "notebook.db"
    log_visit("ADMIN")
    st.sidebar.success("👑 欢迎回来，主人！已加载您的专属数据。")
elif pwd == GUEST_PWD:
    db_name = "guest.db"
    log_visit("GUEST")
    st.sidebar.info("👋 欢迎体验！你目前处于【访客模式】，数据独立存储。")
elif pwd != "":
    st.sidebar.warning("✋ 停！暗号不对。")
    st.stop()
else:
    st.title("🔒 零容忍英语训练营 (已锁定)")
    st.info("👈 请在左侧侧边栏输入暗号以解锁内容。")
    # 这里的 CSS 注入是为了在锁定状态下也隐藏官方元素
    st.markdown("<style>header, footer, .stAppToolbar {display:none !important;}</style>", unsafe_allow_html=True)
    st.stop()

# ================= 1. 注入 CSS（强效隐藏所有官方组件） =================
st.markdown("""
<style>
    /* 强效隐藏官方外壳 */
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    .stAppToolbar { display: none !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }
    footer { visibility: hidden !important; }
    .stDeployButton { display:none !important; }

    /* 侧边栏按钮和游戏化样式 */
    section[data-testid="stSidebar"] button[kind="secondary"] {
        font-size: 0.75em !important;
    }
    .xp-bar-bg {
        background: #2c2c2c; border-radius: 10px; height: 22px;
        width: 100%; position: relative; overflow: hidden;
    }
    .xp-bar-fill {
        height: 100%; border-radius: 10px;
        background: linear-gradient(90deg, #f39c12, #e74c3c, #e91e63);
        transition: width 0.5s ease;
    }
    .xp-bar-text {
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        color: white; font-size: 0.75em; font-weight: bold;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    .badge {
        display: inline-block; padding: 4px 10px; margin: 3px;
        border-radius: 20px; font-size: 0.8em; font-weight: bold;
    }
    .badge-gold { background: linear-gradient(135deg, #f7dc6f, #f0b027); color: #333; }
    .badge-silver { background: linear-gradient(135deg, #d5d8dc, #aab7b8); color: #333; }
    .badge-bronze { background: linear-gradient(135deg, #e8c40a, #cd9b6e); color: #333; }
    .badge-locked { background: #3a3a3a; color: #777; }
    .streak-fire { font-size: 1.4em; }
    .mode-tag {
        display: inline-block; padding: 2px 8px; border-radius: 12px;
        font-size: 0.75em; font-weight: bold; margin-left: 8px;
    }
    .mode-roast { background: #e74c3c; color: white; }
    .mode-hype { background: #2ecc71; color: white; }
    .mode-normal { background: #3498db; color: white; }
</style>
""", unsafe_allow_html=True)

# ================= 2. 数据库配置 =================
@st.cache_resource
def get_db_connection(database_file):
    conn = sqlite3.connect(database_file, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mistakes
        (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP,
         source TEXT, wrong_sentence TEXT, correction TEXT, explanation_en TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vocab
        (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP,
         word TEXT, definition_en TEXT)''')
    try:
        c.execute("ALTER TABLE vocab ADD COLUMN translation_zh TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
        (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP,
         scenario TEXT, chat_log TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
        (id INTEGER PRIMARY KEY CHECK (id = 1),
         xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
         streak INTEGER DEFAULT 0, last_active TEXT,
         total_messages INTEGER DEFAULT 0, perfect_messages INTEGER DEFAULT 0,
         total_sessions INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
        (id TEXT PRIMARY KEY, name TEXT, description TEXT, icon TEXT,
         tier TEXT, unlocked INTEGER DEFAULT 0, unlock_date TEXT)''')
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
    return conn

conn = get_db_connection(db_name)
c = conn.cursor()

# ================= 3. 游戏化系统 =================
def get_stats():
    c.execute("SELECT xp, level, streak, last_active, total_messages, perfect_messages, total_sessions FROM user_stats WHERE id = 1")
    row = c.fetchone()
    return {"xp": row[0], "level": row[1], "streak": row[2], "last_active": row[3],
            "total_messages": row[4], "perfect_messages": row[5], "total_sessions": row[6]}

def xp_for_level(level):
    return 80 + (level - 1) * 30

def add_xp(amount, perfect=False, is_roast=False):
    stats = get_stats()
    xp, level, total_msg, perfect_msg = stats["xp"] + amount, stats["level"], stats["total_messages"] + 1, stats["perfect_messages"] + (1 if perfect else 0)
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
    today_str = datetime.today().isoformat()
    streak = stats["streak"]
    if stats["last_active"] != today_str:
        try:
            from datetime import date
            last_date = date.fromisoformat(stats["last_active"])
            streak = streak + 1 if last_date.toordinal() == date.today().toordinal() - 1 else 1
        except: streak = 1
    c.execute("UPDATE user_stats SET xp=?, level=?, streak=?, last_active=?, total_messages=?, perfect_messages=? WHERE id=1",
              (xp, level, streak, today_str, total_msg, perfect_msg))
    conn.commit()
    check_achievements(level, streak, total_msg, perfect_msg, stats["total_sessions"], is_roast)

def increment_sessions():
    c.execute("UPDATE user_stats SET total_sessions = total_sessions + 1 WHERE id = 1")
    conn.commit()
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
    c.execute("SELECT COUNT(*) FROM vocab")
    vc = c.fetchone()[0]
    if vc >= 10: unlocks.append("vocab_10")
    if vc >= 50: unlocks.append("vocab_50")
    rm = st.session_state.get("roast_msg_count", 0) + (1 if is_roast else 0)
    if is_roast: st.session_state["roast_msg_count"] = rm
    if rm >= 10: unlocks.append("roast_survivor")
    today = datetime.today().isoformat()
    for aid in unlocks:
        c.execute("UPDATE achievements SET unlocked=1, unlock_date=? WHERE id=? AND unlocked=0", (today, aid))
    conn.commit()

def render_stats_bar():
    stats = get_stats()
    xp_needed = xp_for_level(stats["level"])
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

# ================= 4. API & Personality =================
api_key = st.secrets.get("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
if not api_key: st.error("⚠️ API Key Error!"); st.stop()
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

MODES = {
    "🔥 毒舌模式 (Roast)": {"tag": "mode-roast", "text": "ROAST", "extra": "Sarcastic, savage, like Gordon Ramsay. Roast mistakes hard."},
    "🌈 夸夸模式 (Hype)": {"tag": "mode-hype", "text": "HYPE", "extra": "Super enthusiastic cheerleader. Celebrate EVERYTHING in ALL CAPS."},
    "😎 正常模式 (Normal)": {"tag": "mode-normal", "text": "NORMAL", "extra": "Friendly, natural conversation partner."}
}

def chat_and_correct_agent(user_text, scenario, history=None, personality="😎 正常模式 (Normal)"):
    mode = MODES.get(personality, MODES["😎 正常模式 (Normal)"])
    system_prompt = f"You are an English teacher. Scenario: {scenario}. Personality: {mode['extra']}\nTask: 1. Reply naturally in character. 2. Point out errors. RULE: ANY Chinese is an error. Output ONLY JSON: {{\"ai_reply\": \"...\", \"errors\": [{{ \"wrong_sentence\": \"...\", \"correction\": \"...\", \"explanation_en\": \"...\" }}]}}"
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for m in history: messages.append({"role": m["role"], "content": m.get("content", "")})
    else: messages.append({"role": "user", "content": user_text})
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=messages, response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except: return {"ai_reply": "Connection error.", "errors": []}

def get_word_definition(word):
    prompt = "You are a dictionary. Define the word/phrase, give example, and provide Chinese translation. Output JSON: {\"definition_en\": \"...\", \"example_en\": \"...\", \"translation_zh\": \"...\"}"
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": word}], response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except: return {"definition_en": "Error", "example_en": "", "translation_zh": "错误"}

# ================= 6. 场景配置 =================
SCENARIOS = {
    "🎓 University Dorm": "Hey! I'm Alex, your new roommate. Nice to meet you!",
    "💻 Tech Lab — Python": "Hey, ready to dive into this Python project? Let's clean the data.",
    "🎮 Voice Chat": "Yo! Mic check. You down for a few rounds?",
    "👔 Job Interview": "Hello! Thanks for coming in. Tell me a bit about yourself.",
    "🤬 Stubborn Troll": "Pfft. That's the dumbest take ever. Prove me wrong.",
    "💀 Villain Negotiator": "You've been caught. What's in it for me if I let you go?",
    "🕵️ Police Interrogation": "Sit down. We have footage. Start talking.",
}

# ================= 7. 界面渲染 =================
render_stats_bar()
if pwd == ADMIN_PWD: show_visit_log(); st.divider()

st.title("🔥 Zero Tolerance English Bootcamp")
t1, t2, t3, t4, t5 = st.tabs(["🗣️ Roleplay", "📝 Journal", "📖 Notebook", "🕰️ History", "🏆 Achievements"])

with t1:
    col1, col2 = st.columns([1, 2])
    with col1:
        personality = st.radio("AI Personality:", list(MODES.keys()), index=2)
        m_info = MODES[personality]
        st.markdown(f"<span class='mode-tag {m_info['tag']}'>{m_info['text']}</span>", unsafe_allow_html=True)
    with col2:
        selected = st.selectbox("Scenario:", list(SCENARIOS.keys()) + ["✨ Custom"])
        current_scenario = st.text_input("Describe custom scenario:") if selected == "✨ Custom" else selected

    if current_scenario:
        sk = f"{current_scenario}_{personality}"
        if "messages" not in st.session_state or st.session_state.get("state_key") != sk:
            st.session_state.messages = [{"role": "assistant", "content": SCENARIOS.get(current_scenario, "Go ahead!")}]
            st.session_state.state_key = sk

        if st.button("💾 Save & End Session"):
            if len(st.session_state.messages) > 1:
                c.execute("INSERT INTO chat_history (scenario, chat_log) VALUES (?, ?)", (current_scenario, json.dumps(st.session_state.messages)))
                conn.commit(); increment_sessions(); add_xp(30)
                st.session_state.messages = [{"role": "assistant", "content": "Session saved!"}]
                st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg.get("errors"):
                    st.error("🚨 Errors Detected!")
                    for e in msg["errors"]:
                        st.write(f"❌ **You:** {e['wrong_sentence']}\n✅ **Native:** {e['correction']}")
                st.markdown(msg["content"])

        if user_in := st.chat_input("English only..."):
            st.session_state.messages.append({"role": "user", "content": user_in})
            with st.chat_message("user"): st.markdown(user_in)
            with st.spinner("Thinking..."):
                res = chat_and_correct_agent(user_in, current_scenario, st.session_state.messages, personality)
                errs = res.get("errors", [])
                st.session_state.messages.append({"role": "assistant", "content": res.get("ai_reply", ""), "errors": errs})
                is_p = len(errs) == 0
                add_xp(20 if is_p else 10, perfect=is_p, is_roast="毒舌" in personality)
                for e in errs:
                    c.execute("INSERT INTO mistakes (source, wrong_sentence, correction, explanation_en) VALUES (?, ?, ?, ?)",
                              ("Chat: " + current_scenario, e['wrong_sentence'], e['correction'], e['explanation_en']))
                conn.commit()
            st.rerun()

with t2:
    st.subheader("Daily Journal")
    jt = st.text_area("Write your day...", height=150)
    if st.button("Check Journal"):
        if jt:
            res = chat_and_correct_agent(jt, "Journal Evaluation")
            errs = res.get("errors", [])
            if errs:
                st.error("Errors found.")
                for e in errs:
                    st.write(f"❌ {e['wrong_sentence']} -> ✅ {e['correction']}")
                    c.execute("INSERT INTO mistakes (source, wrong_sentence, correction, explanation_en) VALUES (?, ?, ?, ?)", ("Journal", e['wrong_sentence'], e['correction'], e['explanation_en']))
                conn.commit(); add_xp(10)
            else: st.success("Perfect!"); add_xp(25, perfect=True)

with t3:
    st.subheader("Knowledge Base")
    recs = c.execute("SELECT id, date, source, wrong_sentence, correction, explanation_en FROM mistakes ORDER BY id DESC").fetchall()
    for r in recs:
        with st.expander(f"📅 {r[1]} | {r[2]}"):
            st.markdown(f"❌ {r[3]}\n\n✅ {r[4]}\n\n💡 {r[5]}")
            if st.button("🗑️", key=f"del_m_{r[0]}"):
                c.execute("DELETE FROM mistakes WHERE id=?", (r[0],)); conn.commit(); st.rerun()

with t4:
    st.subheader("Past Conversations")
    hists = c.execute("SELECT id, date, scenario, chat_log FROM chat_history ORDER BY id DESC").fetchall()
    for h in hists:
        with st.expander(f"📅 {h[1]} | {h[2]}"):
            for m in json.loads(h[3]): st.write(f"{'🤖' if m['role']=='assistant' else '👤'}: {m['content']}")
            if st.button("🗑️", key=f"del_h_{h[0]}"):
                c.execute("DELETE FROM chat_history WHERE id=?", (h[0],)); conn.commit(); st.rerun()

with t5:
    st.subheader("Achievements")
    achs = c.execute("SELECT name, description, icon, tier, unlocked FROM achievements ORDER BY unlocked DESC").fetchall()
    html = ""
    for name, desc, icon, tier, unl in achs:
        t_cls = f"badge-{tier}" if unl else "badge-locked"
        html += f"<span class='badge {t_cls}' title='{desc}'>{icon} {name}</span> "
    st.markdown(html, unsafe_allow_html=True)

# --- Sidebar Vocab ---
with st.sidebar:
    st.divider(); st.subheader("Vocab Book")
    nw = st.text_input("Quick search:")
    if st.button("Search & Save"):
        if nw:
            res = get_word_definition(nw)
            df, ex, tr = res.get("definition_en"), res.get("example_en"), res.get("translation_zh")
            st.markdown(f"**{nw}**: {df}\n\n*Ex: {ex}*")
            c.execute("INSERT INTO vocab (word, definition_en, translation_zh) VALUES (?, ?, ?)", (nw, f"{df}\nEx: {ex}", tr))
            conn.commit(); st.success("Saved!")
    
    st.divider(); st.write("Recent Words:")
    words = c.execute("SELECT id, word, definition_en, translation_zh FROM vocab ORDER BY id DESC LIMIT 10").fetchall()
    for wid, w, d, tr in words:
        with st.expander(f"📘 {w}"):
            st.write(d)
            if st.toggle("Show Chinese", key=f"t_{wid}"): st.info(tr)
            if st.button("🗑️", key=f"dw_{wid}"): c.execute("DELETE FROM vocab WHERE id=?", (wid,)); conn.commit(); st.rerun()
