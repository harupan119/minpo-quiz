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
      /* Streamlit のヘッダ/ツールバーを隠してアプリらしく */
      [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
      .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 720px; }
      /* 見出し・キャプションを白系に */
      h1, h2, h3, .stMarkdown p, label, .stCaption, [data-testid="stMetricValue"],
      [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] { color: #fff !important; }
      /* セレクトボックスを淡色に（テーマに合わせる） */
      div[data-baseweb="select"] > div { background:#dbe6ff !important; border:none !important;
          border-radius:10px; color:#0b1e7a !important; }
      div[data-baseweb="select"] svg { color:#0b1e7a !important; }
      /* セグメントコントロール（大きなピル・参考アプリ風） */
      [data-testid="stButtonGroup"] [role="radiogroup"] { gap: 6px; }
      [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
          border: 1px solid rgba(255,255,255,.35) !important;
          background: rgba(255,255,255,.10) !important; border-radius: 10px;
          padding: 8px 14px; }
      [data-testid="stButtonGroup"] [role="radiogroup"] { flex-wrap: wrap; }
      [data-testid="stButtonGroup"] button[data-variant="segmented_control"] p {
          font-size: 1.02rem !important; font-weight: 700; color: #eaf0ff !important; }
      /* 選択中＝薄い青＋濃紺文字（黒文字がつぶれない明るさ） */
      [data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] {
          background: #cfe0ff !important; border-color: #cfe0ff !important;
          box-shadow: 0 2px 5px rgba(0,0,0,.18); }
      [data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] p {
          color: #0b1e7a !important; }
      /* 問題カード */
      .qcard { background:#fff; color:#111; border-radius:14px; padding:20px 18px;
               font-size:1.12rem; line-height:2.0; white-space:pre-wrap;
               box-shadow:0 3px 10px rgba(0,0,0,.18); }
      .blank { color:#c0392b; font-weight:800; }
      .qcaption { color:#0b1e7a; font-weight:700; margin-bottom:6px; }
      /* 選択肢の共通フォント（出題時ボタンと回答後divを完全統一） */
      div[data-testid="stButton"] > button[kind="secondary"],
      div[data-testid="stButton"] > button[kind="secondary"] p,
      .opt {
          font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont,
              "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", sans-serif;
          font-size: 1.05rem; font-weight: 700; letter-spacing: normal;
          text-align: center; }
      /* 選択肢・Tap・パス・終了など（白背景＋黒文字＝問題と同じ） */
      div[data-testid="stButton"] > button[kind="secondary"] {
          background:#fff; color:#111; border:none; border-radius:12px;
          padding:14px 16px; width:100%; box-shadow:0 2px 5px rgba(0,0,0,.15); }
      div[data-testid="stButton"] > button[kind="secondary"]:hover {
          background:#f0f4ff; color:#111; }
      /* 主要アクション（スタート・次の問題へ等）＝ネイビー＋白文字 */
      div[data-testid="stButton"] > button[kind="primary"] {
          border:none; border-radius:12px; padding:14px 16px;
          font-size:1.05rem; font-weight:700; width:100%; }
      /* 回答後の結果行 */
      .opt { border-radius:12px; padding:14px 16px; margin-bottom:10px;
             box-shadow:0 2px 5px rgba(0,0,0,.12); }
      .opt-correct { background:#1e8e3e; color:#fff; }
      .opt-wrong   { background:#d32f2f; color:#fff; }
      .opt-plain   { background:#fff; color:#111; }
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
    ss.setdefault("revealed", False)    # 選択肢を表示済みか（Tapで開く）
    ss.setdefault("wrong_nums", [])
    ss.setdefault("history", [])        # 今回セッションの回答履歴
    ss.setdefault("start_ts", 0.0)


init_state()


def make_quiz(pool, blanks):
    rng = random.Random()
    # 前半は短め（読みやすい）の条文を優先、後半は制限なしで確実に1問出す
    for attempt in range(30):
        art = rng.choice(pool)
        if attempt < 20 and len(art.text) > 350:
            continue
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
    ss.revealed = False


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
    st.title("民法 穴埋めクイズ")
    st.caption("4択で条文の重要語を確認。範囲と問題数を選んでスタート。")

    scope = st.segmented_control(
        "出題範囲",
        ["テスト範囲（既定）", "編で選ぶ", "民法全体", "条番号を指定"],
        default="テスト範囲（既定）") or "テスト範囲（既定）"
    if scope == "テスト範囲（既定）":
        st.caption("❔ テスト範囲＝民法 1〜169・175〜207・239〜294 条")
    parts, direct = [], 709
    if scope == "編で選ぶ":
        parts = st.multiselect("編", m.PART_ORDER, default=["総則"])
    if scope == "条番号を指定":
        direct = st.number_input("条番号", 1, 1050, 709, 1)

    tgt = st.segmented_control("問題数", ["5", "10", "20", "無制限"],
                               default="10") or "10"
    target = None if tgt == "無制限" else int(tgt)

    blank_choice = st.segmented_control("空所の数", ["自動", "1", "2", "3", "4"],
                                        default="自動") or "自動"
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

    msg_color = "#ffd54a" if rate >= 100 else "#8ef0a6" if rate >= 70 else "#ffffff"
    st.markdown(
        f'''<div style="text-align:center; margin: 4px 0 16px;">
          <div style="font-size:2.5rem; font-weight:900; color:{msg_color};
               letter-spacing:.03em; text-shadow:0 3px 8px rgba(0,0,0,.28);
               line-height:1.2;">{msg}</div>
          <div style="font-size:1.2rem; font-weight:800; color:#fff; margin-top:10px;">
               正解 {ss.correct} / {ss.asked}　正答率 {rate:.0f}%</div>
          <div style="color:#cfe0ff; margin-top:2px;">学習時間 {mm}分{sscnd}秒</div>
        </div>''', unsafe_allow_html=True)

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

# ステータスバー（1行にまとめてモバイルでも崩れないように）
prog = f"{ss.asked + (0 if ss.answered else 1)} / {ss.target}問" if ss.target \
    else f"{ss.asked + (0 if ss.answered else 1)} 問目"
top = st.columns([3, 1])
top[0].markdown(
    f'<div class="statusbar">{prog}　｜　正解 {ss.correct}</div>',
    unsafe_allow_html=True)
with top[1]:
    if st.button("終了", use_container_width=True):
        ss.stage = "result"
        st.rerun()

# ---- 上ペイン：問題（回答後は見出しと答えを表示） ----
if ss.answered and quiz.caption:
    st.markdown(f'<div class="qcaption">{quiz.title}　{quiz.caption}</div>',
                unsafe_allow_html=True)
st.markdown(render_body(quiz, reveal=ss.answered), unsafe_allow_html=True)

# ---- 下ペイン：解答（問題枠とは分離した別枠） ----
with st.container(border=True):
    if not ss.answered:
        if not ss.revealed:
            # 選択肢を隠した状態。タップで表示。
            if st.button("Tap｜タップして選択肢を表示", key=f"reveal_{ss.qid}",
                         use_container_width=True):
                ss.revealed = True
                st.rerun()
        else:
            for i, opt in enumerate(quiz.combined):
                if st.button(opt, key=f"opt_{ss.qid}_{i}",
                             use_container_width=True):
                    grade(opt)
                    st.rerun()
        # パス（未解答のまま答えを見て次へ）
        if st.button("パス（答えを見る）", key=f"pass_{ss.qid}",
                     use_container_width=True):
            grade("（パス）")
            st.rerun()
    else:
        # 結果表示
        for opt in quiz.combined:
            if opt == quiz.combined_answer:
                cls, label = "opt-correct", f"◯ {opt}"
            elif opt == ss.chosen:
                cls, label = "opt-wrong", f"✕ {opt}（あなたの回答）"
            else:
                cls, label = "opt-plain", opt
            st.markdown(f'<div class="opt {cls}">{label}</div>',
                        unsafe_allow_html=True)

        reached = ss.target is not None and ss.asked >= ss.target
        label = "結果を見る" if reached else "次の問題へ"
        if st.button(label, type="primary", use_container_width=True):
            if reached:
                ss.stage = "result"
            else:
                next_question()
            st.rerun()
