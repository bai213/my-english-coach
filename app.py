import streamlit as st

# ================= 0. 页面配置（必须是第一个 st 命令）=================
st.set_page_config(page_title="Hardcore English Coach", layout="wide")

import sqlite3
import json
import os
from datetime import datetime
from openai import OpenAI

# ================= 1. 数据库工具函数 =================
def run_query(db_file, query, params=(), fetch=False, commit=False):
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit:
            conn.commit()
        if fetch:
            return c.fetchall()
        return None

# ================= 2. 注入 CSS =================
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

# ================= 3. 数据库初始化 =================
db_name = "notebook.db"

def init_db(database_file):
    with sqlite3.connect(database_file) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS mistakes (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, source TEXT, wrong_sentence TEXT, correction TEXT, explanation_en TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS vocab (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, word TEXT, definition_en TEXT, translation_zh TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, scenario TEXT, chat_log TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_TIMESTAMP, title TEXT, content TEXT, feedback TEXT)')
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

# ================= 4. 游戏化逻辑 =================
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
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        titles = {1: "Newbie", 5: "Rising Star", 10: "Veteran", 20: "Master", 25: "Legend"}
        title = next((t for lv, t in sorted(titles.items(), reverse=True) if stats["level"] >= lv), "Newbie")
        st.markdown(f"### Lv.{stats['level']} — {title}")
    with c2:
        fire = "🔥" * min(stats["streak"], 5)
        st.markdown(f"<span class='streak-fire'>{fire if fire else '❄️'}</span> **{stats['streak']}天连续**", unsafe_allow_html=True)
    with c3:
        acc = (stats["perfect_messages"] / stats["total_messages"] * 100) if stats["total_messages"] > 0 else 0
        st.markdown(f"🎯 **正确率 {acc:.0f}%**")
    st.markdown(f'<div class="xp-bar-bg"><div class="xp-bar-fill" style="width: {pct}%;"></div><div class="xp-bar-text">{stats["xp"]} / {xp_needed} XP</div></div>', unsafe_allow_html=True)
    st.write("")

# ================= 5. AI & 查词逻辑 =================
api_key = st.secrets["DEEPSEEK_API_KEY"]
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

MODES = {
    "🔥 毒舌模式 (Roast)": {"tag": "mode-roast", "text": "ROAST", "extra": "Sarcastic, savage. Roast mistakes hard."},
    "🌈 夸夸模式 (Hype)": {"tag": "mode-hype", "text": "HYPE", "extra": "Super enthusiastic cheerleader. Use normal casing (no all-caps), but lots of exclamation marks!"},
    "😎 正常模式 (Normal)": {"tag": "mode-normal", "text": "NORMAL", "extra": "Friendly, natural conversation partner."}
}

def chat_and_correct_agent(user_text, scenario, history=None, personality="😎 正常模式 (Normal)"):
    mode = MODES.get(personality, MODES["😎 正常模式 (Normal)"])
    system_prompt = f"English teacher. Scenario: {scenario}. Personality: {mode['extra']}\nTask: 1. Reply in character. 2. Point out errors. JSON ONLY: {{\"ai_reply\": \"...\", \"errors\": [{{ \"wrong_sentence\": \"...\", \"correction\": \"...\", \"explanation_en\": \"...\" }}]}}"
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for m in history: messages.append({"role": m["role"], "content": m.get("content", "")})
    else: messages.append({"role": "user", "content": user_text})
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=messages, response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except: return {"ai_reply": "Connection error.", "errors": []}

def grade_journal(title, content):
    prompt = """You are a strict but encouraging English writing coach. The student wrote a journal entry.
1. Give overall feedback (2-3 sentences)
2. List specific grammar/vocabulary/expression errors with corrections
3. Give a score out of 10
Output JSON ONLY: {"overall": "...", "errors": [{"original": "...", "correction": "...", "explanation": "..."}], "score": 8, "rewritten": "A polished version of their entry"}"""
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"Title: {title}\n\n{content}"}],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except:
        return {"overall": "Connection error.", "errors": [], "score": 0, "rewritten": ""}

def get_word_definition(word):
    prompt = "You are a dictionary. Define the word/phrase, give example, and provide Chinese translation. Output JSON: {\"definition_en\": \"...\", \"example_en\": \"...\", \"translation_zh\": \"...\"}"
    try:
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": word}], response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except: return {"definition_en": "Error", "example_en": "", "translation_zh": "查询失败"}

# ================= 6. 主界面 Tab 渲染 =================
render_stats_bar()
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

with t2:
    st.subheader("📝 English Journal")
    st.caption("Write freely in English — AI will grade your grammar, vocabulary, and style.")

    with st.form("journal_form", clear_on_submit=True):
        j_title = st.text_input("Title (optional):", placeholder="e.g. My weekend, A funny thing happened...")
        j_content = st.text_area("Write your journal entry here:", height=200, placeholder="Today I went to the park and...")
        submitted = st.form_submit_button("✅ Submit for Grading")

    if submitted and j_content.strip():
        with st.spinner("AI is reading your entry..."):
            feedback = grade_journal(j_title or "Untitled", j_content)
        score = feedback.get("score", 0)
        overall = feedback.get("overall", "")
        errors = feedback.get("errors", [])
        rewritten = feedback.get("rewritten", "")

        # Score display
        score_color = "#2ecc71" if score >= 8 else "#f39c12" if score >= 5 else "#e74c3c"
        st.markdown(f"<h2 style='color:{score_color}'>Score: {score}/10</h2>", unsafe_allow_html=True)
        st.info(f"💬 {overall}")

        if errors:
            st.markdown("**✏️ Errors to fix:**")
            for i, e in enumerate(errors, 1):
                st.error(f"**{i}.** ❌ `{e.get('original', '')}` → ✅ `{e.get('correction', '')}`\n\n_{e.get('explanation', '')}_")
                run_query(db_name, "INSERT INTO mistakes (source, wrong_sentence, correction, explanation_en) VALUES (?, ?, ?, ?)",
                          ("Journal: " + (j_title or "Untitled"), e.get('original', ''), e.get('correction', ''), e.get('explanation', '')), commit=True)
        else:
            st.success("🎉 No errors found! Perfect entry!")

        if rewritten:
            with st.expander("✨ See polished version"):
                st.markdown(rewritten)

        # Save to DB and add XP
        is_perfect = len(errors) == 0
        run_query(db_name, "INSERT INTO journal (title, content, feedback) VALUES (?, ?, ?)",
                  (j_title or "Untitled", j_content, json.dumps(feedback)), commit=True)
        add_xp(25 if is_perfect else 15, perfect=is_perfect)
        st.toast("Entry saved! XP earned 🎉")

    st.divider()
    st.markdown("**📚 Past Entries:**")
    past = run_query(db_name, "SELECT id, date, title, content, feedback FROM journal ORDER BY id DESC LIMIT 20", fetch=True)
    if past:
        for pid, pdate, ptitle, pcontent, pfeedback in past:
            fb = json.loads(pfeedback) if pfeedback else {}
            score_label = f"🏅 {fb.get('score', '?')}/10" if fb else ""
            with st.expander(f"📅 {pdate[:10]} | {ptitle} {score_label}"):
                st.markdown(pcontent)
                if fb.get("overall"):
                    st.info(fb["overall"])
                if st.button("🗑️ Delete", key=f"del_j_{pid}"):
                    run_query(db_name, "DELETE FROM journal WHERE id=?", (pid,), commit=True); st.rerun()
    else:
        st.info("No journal entries yet. Write your first one above!")

with t3:
    st.subheader("📖 Knowledge Base — All Errors")
    recs = run_query(db_name, "SELECT id, date, source, wrong_sentence, correction, explanation_en FROM mistakes ORDER BY id DESC", fetch=True)
    if recs:
        # 批量删除按钮
        if st.button("🗑️ Clear All", type="secondary"):
            run_query(db_name, "DELETE FROM mistakes", commit=True); st.rerun()
        st.write(f"**{len(recs)} records**")
        for r in recs:
            rid, rdate, rsource, rwrong, rcorrect, rexplain = r
            col_exp, col_del = st.columns([10, 1])
            with col_exp:
                with st.expander(f"📅 {rdate[:16]} | {rsource}"):
                    st.markdown(f"**❌ You:** {rwrong}")
                    st.markdown(f"**✅ Native:** {rcorrect}")
                    if rexplain:
                        st.caption(rexplain)
            with col_del:
                st.write("")  # 空行对齐
                if st.button("🗑️", key=f"del_m_{rid}", help="Delete this record"):
                    run_query(db_name, "DELETE FROM mistakes WHERE id=?", (rid,), commit=True); st.rerun()
    else:
        st.info("No errors recorded yet. Keep chatting!")

with t4:
    st.subheader("🕰️ History — Chats & Journals")

    # 聊天记录
    chats = run_query(db_name, "SELECT id, date, scenario, chat_log FROM chat_history ORDER BY id DESC", fetch=True)
    # 日记记录
    journals = run_query(db_name, "SELECT id, date, title, content, feedback FROM journal ORDER BY id DESC", fetch=True)

    # 合并并按时间排序
    all_records = []
    for c in (chats or []):
        all_records.append({"type": "chat", "id": c[0], "date": c[1], "data": c})
    for j in (journals or []):
        all_records.append({"type": "journal", "id": j[0], "date": j[1], "data": j})
    all_records.sort(key=lambda x: x["date"], reverse=True)

    if not all_records:
        st.info("No history yet.")
    else:
        st.write(f"**{len(all_records)} records total** — 💬 {len(chats or [])} chats · 📝 {len(journals or [])} journals")
        for rec in all_records:
            if rec["type"] == "chat":
                _, rdate, rscenario, rchat_log = rec["data"]
                rid = rec["id"]
                label = f"💬 {rdate[:16]} | {rscenario}"
                col_exp, col_del = st.columns([10, 1])
                with col_exp:
                    with st.expander(label):
                        try:
                            msgs = json.loads(rchat_log)
                            for m in msgs:
                                role_icon = "🧑" if m["role"] == "user" else "🤖"
                                if m.get("errors"):
                                    for e in m["errors"]:
                                        st.error(f"❌ {e['wrong_sentence']} → ✅ {e['correction']}")
                                st.markdown(f"{role_icon} {m.get('content', '')}")
                        except:
                            st.write(rchat_log)
                with col_del:
                    st.write("")
                    if st.button("🗑️", key=f"del_ch_{rid}"):
                        run_query(db_name, "DELETE FROM chat_history WHERE id=?", (rid,), commit=True); st.rerun()

            elif rec["type"] == "journal":
                _, rdate, rtitle, rcontent, rfeedback = rec["data"]
                rid = rec["id"]
                fb = json.loads(rfeedback) if rfeedback else {}
                score_label = f" 🏅{fb.get('score', '?')}/10" if fb else ""
                label = f"📝 {rdate[:16]} | {rtitle}{score_label}"
                col_exp, col_del = st.columns([10, 1])
                with col_exp:
                    with st.expander(label):
                        st.markdown(rcontent)
                        if fb.get("overall"):
                            st.info(f"💬 {fb['overall']}")
                        if fb.get("errors"):
                            for e in fb["errors"]:
                                st.error(f"❌ `{e.get('original','')}` → ✅ `{e.get('correction','')}`")
                        if fb.get("rewritten"):
                            with st.expander("✨ Polished version"):
                                st.markdown(fb["rewritten"])
                with col_del:
                    st.write("")
                    if st.button("🗑️", key=f"del_j2_{rid}"):
                        run_query(db_name, "DELETE FROM journal WHERE id=?", (rid,), commit=True); st.rerun()

with t5:
    st.subheader("Achievements")
    achs = run_query(db_name, "SELECT name, description, icon, tier, unlocked FROM achievements ORDER BY unlocked DESC", fetch=True)
    html = ""
    for name, desc, icon, tier, unl in achs:
        t_cls = f"badge-{tier}" if unl else "badge-locked"
        html += f"<span class='badge {t_cls}' title='{desc}'>{icon} {name}</span> "
    st.markdown(html, unsafe_allow_html=True)

# --- Sidebar Vocab ---
with st.sidebar:
    st.subheader("Vocab Book")
    nw = st.text_input("Quick search:")
    if st.button("Search & Save"):
        if nw:
            with st.spinner("Searching AI Dictionary..."):
                res = get_word_definition(nw)
                df, ex, tr = res.get("definition_en"), res.get("example_en"), res.get("translation_zh")
                st.markdown(f"**{nw}**")
                st.write(df)
                if ex: st.info(f"Example: {ex}")
                run_query(db_name, "INSERT INTO vocab (word, definition_en, translation_zh) VALUES (?, ?, ?)", (nw, f"{df}\n\nEx: {ex}", tr), commit=True)
                st.success("Saved!")

    st.divider(); st.write("Recent Words:")
    words = run_query(db_name, "SELECT id, word, definition_en, translation_zh FROM vocab ORDER BY id DESC LIMIT 10", fetch=True)
    if words:
        for wid, w, d, tr in words:
            with st.expander(f"📘 {w}"):
                st.write(d)
                if st.toggle("Show Chinese", key=f"t_{wid}"): st.info(tr)
                if st.button("🗑️", key=f"dw_{wid}"): run_query(db_name, "DELETE FROM vocab WHERE id=?", (wid,), commit=True); st.rerun()
                    
