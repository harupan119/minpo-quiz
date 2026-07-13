"""民法条文 穴埋めクイズ (Streamlit・4択)

「無機化学」アプリ風の 4択・即判定・問題数モード・復習リスト。
スマホ／PC 両対応。e-Gov 法令検索データ(civil_code.json)を使用。
"""

from __future__ import annotations

import random
import re
import time

import streamlit as st

import minpo_core as m

st.set_page_config(page_title="民法 穴埋めクイズ", page_icon="⚖️",
                   layout="centered", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# テーマ（ロイヤルブルー背景＋白い問題カード＋淡青の選択肢）
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .stApp { background: #2540e8; }
      .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 720px; }
      /* 見出し・キャプションを白系に */
      h1, h2, h3, .stMarkdown p, label, .stCaption, [data-testid="stMetricValue"],
      [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] { color: #fff !important; }
      /* 問題カード */
      .qcard { background:#fff; color:#111; border-radius:14px; padding:20px 18px;
               font-size:1.12rem; line-height:2.0; white-space:pre-wrap;
               box-shadow:0 3px 10px rgba(0,0,0,.18); }
      .blank { color:#c0392b; font-weight:800; }
      .qcaption { color:#0b1e7a; font-weight:700; margin-bottom:6px; }
      /* 選択肢ボタン（未回答） */
      div[data-testid="stButton"] > button {
          background:#dbe6ff; color:#0b1e7a; border:none; border-radius:12px;
          padding:14px 16px; font-size:1.05rem; font-weight:700; width:100%;
          box-shadow:0 2px 5px rgba(0,0,0,.15); }
      div[data-testid="stButton"] > button:hover { background:#c3d5ff; color:#0b1e7a; }
      /* 回答後の結果行 */
      .opt { border-radius:12px; padding:13px 16px; font-size:1.05rem; font-weight:700;
             margin-bottom:10px; }
      .opt-correct { background:#1e8e3e; color:#fff; }
      .opt-wrong   { background:#d93025; color:#fff; }
      .opt-plain   { background:#dbe6ff; color:#0b1e7a; }
      .statusbar { color:#dbe6ff; font-weight:700; font-size:.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="民法データを読み込み中...")
def get_data():
    arts = m.load_articles("civil_code.json")
    main = m.main_articles(arts)
    return main, m.build_index(main), m.load_vocab()


MAIN, INDEX, VOCAB = get_data()


# ---------------------------------------------------------------------------
# セッション状態
# ---------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("stage", "setup")     # setup / playing / result
    ss.setdefault("sel", None)
    ss.setdefault("pool", [])
    ss.setdefault("target", 10)         # 問題数（None=無制限）
    ss.setdefault("asked", 0)
    ss.setdefault("correct", 0)
    ss.setdefault("quiz", None)
    ss.setdefault("qid", 0)
    ss.setdefault("answered", False)
    ss.setdefault("chosen", None)
    ss.setdefault("wrong_nums", [])
    ss.setdefault("history", [])        # 今回セッションの回答履歴
    ss.setdefault("start_ts", 0.0)


init_state()


def make_quiz(pool, blanks):
    rng = random.Random()
    for _ in range(30):
        art = rng.choice(pool)
        quiz = m.generate_quiz(art, num_blanks=blanks, rng=rng, vocab=VOCAB)
        if quiz and quiz.combined:
            return quiz
    return None


def next_question():
    ss = st.session_state
    quiz = make_quiz(ss.pool, ss.sel["blanks"])
    if quiz is None:
        st.warning("出題できる条文が見つかりませんでした。")
        return
    ss.quiz = quiz
    ss.qid += 1
    ss.answered = False
    ss.chosen = None


def start_session(sel, target):
    ss = st.session_state
    ss.sel = sel
    ss.target = target
    ss.asked = 0
    ss.correct = 0
    ss.history = []
    ss.start_ts = time.time()

    if sel["scope"] == "条番号を指定":
        art = INDEX.get(int(sel["direct"]))
        if not art:
            st.error("その条番号は見つかりませんでした。")
            return
        ss.pool = [art]
        ss.target = 1
    elif sel["scope"] == "テスト範囲（既定）":
        ss.pool = m.filter_by_ranges(MAIN, m.TEST_RANGES)
    elif sel["scope"] == "編で選ぶ":
        ss.pool = m.filter_by_parts(MAIN, sel["parts"])
    elif sel["scope"] == "復習":
        ss.pool = [INDEX[n] for n in ss.wrong_nums if n in INDEX]
    else:
        ss.pool = MAIN

    if not ss.pool:
        st.warning("この条件で出題できる条文がありません。")
        return
    ss.stage = "playing"
    next_question()


def grade(choice: str):
    ss = st.session_state
    ss.chosen = choice
    ss.answered = True
    ss.asked += 1
    q = ss.quiz
    ok = choice == q.combined_answer
    if ok:
        ss.correct += 1
    elif q.num and q.num not in ss.wrong_nums:
        ss.wrong_nums.append(q.num)
    ss.history.append({
        "title": q.title, "caption": q.caption,
        "body": render_body(q, reveal=True),
        "answer": q.combined_answer, "chosen": choice, "ok": ok,
    })


def render_body(quiz, reveal=False) -> str:
    html = (quiz.body.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\n", "<br>"))

    def repl(mo):
        n = int(mo.group(1))
        if reveal:
            return f'<span style="color:#1e8e3e;font-weight:800;">{quiz.answers[n-1]}</span>'
        return f'<span class="blank">【&nbsp;{n}&nbsp;】</span>'

    html = re.sub(r"【\s*(\d+)\s*】", repl, html)
    return f'<div class="qcard">{html}</div>'


# ===========================================================================
# 画面：セットアップ
# ===========================================================================
if st.session_state.stage == "setup":
    st.title("⚖️ 民法 穴埋めクイズ")
    st.caption("4択で条文の重要語を確認。範囲と問題数を選んでスタート。")

    scope = st.radio("出題範囲",
                     ["テスト範囲（既定）", "編で選ぶ", "民法全体", "条番号を指定"],
                     help="テスト範囲＝1〜169・175〜207・239〜294 条")
    parts, direct = [], 709
    if scope == "編で選ぶ":
        parts = st.multiselect("編", m.PART_ORDER, default=["総則"])
    if scope == "条番号を指定":
        direct = st.number_input("条番号", 1, 1050, 709, 1)

    tgt = st.radio("問題数", ["5", "10", "20", "無制限"], index=1, horizontal=True)
    target = None if tgt == "無制限" else int(tgt)

    blank_choice = st.selectbox("空所の数", ["自動", "1", "2", "3", "4"])
    blanks = None if blank_choice == "自動" else int(blank_choice)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("スタート", type="primary", use_container_width=True):
            start_session({"scope": scope, "parts": parts,
                           "direct": direct, "blanks": blanks}, target)
            st.rerun()
    with c2:
        if st.session_state.wrong_nums and st.button(
                f"復習（{len(st.session_state.wrong_nums)}問）",
                use_container_width=True):
            start_session({"scope": "復習", "parts": [], "direct": None,
                           "blanks": blanks}, None)
            st.rerun()

    st.stop()


# ===========================================================================
# 画面：結果
# ===========================================================================
if st.session_state.stage == "result":
    ss = st.session_state
    rate = ss.correct / ss.asked * 100 if ss.asked else 0
    if rate >= 100:
        msg = "★ Perfect！ ★"
    elif rate >= 70:
        msg = "★ Good！ ★"
    elif rate >= 40:
        msg = "その調子"
    else:
        msg = "Good try！"
    elapsed = int(time.time() - ss.start_ts) if ss.start_ts else 0
    mm, sscnd = divmod(elapsed, 60)

    st.markdown(
        f'''<div class="qcard" style="text-align:center;">
        <div style="font-size:1.3rem;font-weight:800;">{msg}</div>
        <div style="margin-top:8px;">正解 <b>{ss.correct}/{ss.asked}</b> 問
        正答率 <b>{rate:.0f}%</b></div>
        <div style="color:#555;margin-top:4px;">学習時間 {mm}分{sscnd}秒</div>
        </div>''', unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("もう一度（同じ設定）", type="primary", use_container_width=True):
            start_session(ss.sel, ss.target)
            st.rerun()
    with c2:
        if st.button("設定に戻る", use_container_width=True):
            ss.stage = "setup"
            st.rerun()

    st.markdown('<div class="statusbar">── 振り返り ──</div>',
                unsafe_allow_html=True)
    for i, h in enumerate(ss.history, 1):
        mark = "◯" if h["ok"] else "✕"
        clr = "#1e8e3e" if h["ok"] else "#d93025"
        head = f'{h["title"]}　{h["caption"]}'.strip()
        st.markdown(
            f'<div class="qcaption" style="color:#dbe6ff;">'
            f'{i}. <span style="color:{clr};">{mark}</span> {head}</div>',
            unsafe_allow_html=True)
        st.markdown(h["body"], unsafe_allow_html=True)
        got = h["chosen"] or "（未選択）"
        st.markdown(
            f'<div class="statusbar" style="margin:4px 0 14px;">'
            f'正答： {h["answer"]}　／　あなた： {got}</div>',
            unsafe_allow_html=True)
    st.stop()


# ===========================================================================
# 画面：出題中
# ===========================================================================
ss = st.session_state
quiz = ss.quiz

# ステータスバー
prog = f"{ss.asked + (0 if ss.answered else 1)} / {ss.target}問" if ss.target \
    else f"{ss.asked + (0 if ss.answered else 1)} 問目"
top = st.columns([2, 1, 1])
top[0].markdown(f'<div class="statusbar">{prog}</div>', unsafe_allow_html=True)
top[1].markdown(f'<div class="statusbar">正解 {ss.correct}</div>',
                unsafe_allow_html=True)
with top[2]:
    if st.button("終了", use_container_width=True):
        ss.stage = "result"
        st.rerun()

# 問題カード（回答後は見出しと答えを表示）
if ss.answered and quiz.caption:
    st.markdown(f'<div class="qcaption">{quiz.title}　{quiz.caption}</div>',
                unsafe_allow_html=True)
st.markdown(render_body(quiz, reveal=ss.answered), unsafe_allow_html=True)
st.write("")

if not ss.answered:
    # 選択肢（タップで即判定）
    for i, opt in enumerate(quiz.combined):
        if st.button(opt, key=f"opt_{ss.qid}_{i}", use_container_width=True):
            grade(opt)
            st.rerun()
else:
    # 結果表示
    for opt in quiz.combined:
        if opt == quiz.combined_answer:
            cls = "opt-correct"
            label = f"◯ {opt}"
        elif opt == ss.chosen:
            cls = "opt-wrong"
            label = f"✕ {opt}（あなたの回答）"
        else:
            cls = "opt-plain"
            label = opt
        st.markdown(f'<div class="opt {cls}">{label}</div>',
                    unsafe_allow_html=True)

    if ss.chosen == quiz.combined_answer:
        st.success("正解！")
    else:
        st.error(f"不正解　正答： {quiz.combined_answer}")

    # 次へ / 終了判定
    reached = ss.target is not None and ss.asked >= ss.target
    if reached:
        if st.button("結果を見る", type="primary", use_container_width=True):
            ss.stage = "result"
            st.rerun()
    else:
        if st.button("次の問題へ", type="primary", use_container_width=True):
            next_question()
            st.rerun()
