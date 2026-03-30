import streamlit as st

# ================= 0. 页面配置（必须是第一个 st 命令）=================
st.set_page_config(page_title="Hardcore English Coach", layout="wide")

import sqlite3
import json
import os
from datetime import date
from openai import OpenAI

# ================= 0.5 终极防盗门：平行宇宙双账号系统 =================
with st.sidebar:
    st.header("🔒 专属验证")
    pwd = st.text_input("🔑 请输入暗号：", type="password")

# 从 Streamlit Secrets 安全读取密码，代码中不出现真实密码
ADMIN_PWD = st.secrets["ADMIN_PWD"]
GUEST_PWD = st.secrets["GUEST_PWD"]

if pwd == ADMIN_PWD:
    db_name = "notebook.db"
    st.sidebar.success("👑 欢迎回来，主人！已加载您的专属数据。")
elif pwd == GUEST_PWD:
    db_name = "guest.db" # 这是一个完全独立的数据库文件！
    st.sidebar.info("👋 欢迎体验！你目前处于【访客模式】，数据独立存储，尽情受虐吧。")
elif pwd != "":
    st.sidebar.warning("✋ 停！暗号不对。")
    st.stop()
else:
    st.title("🔒 零容忍英语训练营 (已锁定)")
    st.info("👈 请在左侧侧边栏输入暗号以解锁内容。")
    st.stop()
# ==============================================================

# ================= 1. 注入 CSS =================
st.markdown("""
<style>
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
    .badge-bronze { background: linear-gradient(135deg, #e8c4a0, #cd9b6e); color: #333; }
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
    achievements_def = [
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
    for a in achievements_def:
        c.execute("INSERT OR IGNORE INTO achievements (id, name, description, icon, tier) VALUES (?, ?, ?, ?, ?)", a)
    conn.commit()
    return conn

# 这里的 db_name 是根据上面输入的暗号动态决定的！
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
    xp = stats["xp"] + amount
    total_msg = stats["total_messages"] + 1
    perfect_msg = stats["perfect_messages"] + (1 if perfect else 0)
    level = stats["level"]
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
    today_str = date.today().isoformat()
    last = stats["last_active"]
    streak = stats["streak"]
    if last != today_str:
        if last and date.fromisoformat(last).toordinal() == date.today().toordinal() - 1:
            streak += 1
        else:
            streak = 1
    c.execute("UPDATE user_stats SET xp=?, level=?, streak=?, last_active=?, total_messages=?, perfect_messages=? WHERE id=1",
              (xp, level, streak, today_str, total_msg, perfect_msg))
    conn.commit()
    check_achievements(level, streak, total_msg, perfect_msg, stats["total_sessions"], is_roast)

def increment_sessions():
    c.execute("UPDATE user_stats SET total_sessions = total_sessions + 1 WHERE id = 1")
    conn.commit()
    stats = get_stats()
    check_achievements(stats["level"], stats["streak"], stats["total_messages"],
                       stats["perfect_messages"], stats["total_sessions"], False)

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
    vocab_count = c.fetchone()[0]
    if vocab_count >= 10: unlocks.append("vocab_10")
    if vocab_count >= 50: unlocks.append("vocab_50")
    roast_msgs = st.session_state.get("roast_msg_count", 0)
    if is_roast:
        roast_msgs += 1
        st.session_state["roast_msg_count"] = roast_msgs
    if roast_msgs >= 10: unlocks.append("roast_survivor")
    today_str = date.today().isoformat()
    for aid in unlocks:
        c.execute("UPDATE achievements SET unlocked=1, unlock_date=? WHERE id=? AND unlocked=0", (today_str, aid))
    conn.commit()

def render_stats_bar():
    stats = get_stats()
    xp_needed = xp_for_level(stats["level"])
    pct = min(stats["xp"] / xp_needed * 100, 100)
    col_lvl, col_streak, col_msg = st.columns([2, 1, 1])
    with col_lvl:
        titles = {1: "Newbie", 5: "Rising Star", 10: "Veteran", 15: "Expert", 20: "Master", 25: "Legend", 30: "God Mode"}
        title = "Newbie"
        for lv, t in sorted(titles.items(), reverse=True):
            if stats["level"] >= lv:
                title = t
                break
        st.markdown(f"### Lv.{stats['level']} — {title}")
    with col_streak:
        fire = "🔥" * min(stats["streak"], 5)
        st.markdown(f"<span class='streak-fire'>{fire if fire else '❄️'}</span> **{stats['streak']}天连续**", unsafe_allow_html=True)
    with col_msg:
        accuracy = (stats["perfect_messages"] / stats["total_messages"] * 100) if stats["total_messages"] > 0 else 0
        st.markdown(f"🎯 **正确率 {accuracy:.0f}%**")
    st.markdown(f"""
    <div class="xp-bar-bg">
        <div class="xp-bar-fill" style="width: {pct}%;"></div>
        <div class="xp-bar-text">{stats['xp']} / {xp_needed} XP</div>
    </div>""", unsafe_allow_html=True)
    st.write("")

# ================= 4. API 配置 =================
def get_api_key():
    try:
        return st.secrets["DEEPSEEK_API_KEY"]
    except Exception:
        return os.environ.get("DEEPSEEK_API_KEY", "")

api_key = get_api_key()
if not api_key:
    st.error("⚠️ 未检测到 API Key！请在 `.streamlit/secrets.toml` 中设置 `DEEPSEEK_API_KEY`。")
    st.code('# .streamlit/secrets.toml\nDEEPSEEK_API_KEY = "sk-your-key-here"', language="toml")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ================= 5. AI 性格系统 =================
PERSONALITY_MODES = {
    "🔥 毒舌模式 (Roast)": {
        "tag_class": "mode-roast", "tag_text": "ROAST MODE",
        "prompt_extra": """
PERSONALITY: You are BRUTALLY sarcastic and savage. You roast the user's mistakes HARD with dark humor.
Your replies drip with sarcasm. If they make no errors, act DISAPPOINTED you can't roast them.
Use phrases like "Oh honey...", "Bless your heart...", "Are you even trying?", "My 5-year-old writes better..."
BUT: Still be HELPFUL underneath. Always provide the correct answer. Funny, not cruel. Think Gordon Ramsay teaching English."""
    },
    "🌈 夸夸模式 (Hype)": {
        "tag_class": "mode-hype", "tag_text": "HYPE MODE",
        "prompt_extra": """
PERSONALITY: You are the world's most ENTHUSIASTIC cheerleader. Celebrate EVERYTHING.
Even tiny things deserve fireworks. "OH MY GOD you used a SEMICOLON?! INCREDIBLE!"
If they make errors, frame it as "you're SO CLOSE, just tweak this tiny thing!"
Use ALL CAPS frequently. Every message should make the user feel like a SUPERSTAR.
Think: motivational speaker who had 5 espressos."""
    },
    "😎 正常模式 (Normal)": {
        "tag_class": "mode-normal", "tag_text": "NORMAL",
        "prompt_extra": """
PERSONALITY: Friendly, natural, like a cool friend who's great at English. Casual and relaxed."""
    }
}

def chat_and_correct_agent(user_text, scenario, history=None, personality="😎 正常模式 (Normal)"):
    mode = PERSONALITY_MODES.get(personality, PERSONALITY_MODES["😎 正常模式 (Normal)"])
    system_prompt = f"""
You are an English conversation partner and a strict grammar teacher.
Current Scenario: {scenario}
{mode['prompt_extra']}

You have TWO tasks:
1. Reply to the user's message. Use AUTHENTIC, COLLOQUIAL SPOKEN ENGLISH.
   CRITICAL: Completely adopt the persona. NEVER break character. NEVER say you are an AI.
   Make up details to fit the scenario naturally.
   If the user misunderstood, gently clarify and rephrase.

2. Review the user's input.
   Point out grammatical mistakes, spelling errors, or highly unnatural phrasing.
   CRITICAL RULE: If the user writes ANY Chinese characters, this is ALWAYS an error.
   You MUST put the Chinese text in
