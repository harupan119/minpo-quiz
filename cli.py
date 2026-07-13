"""民法条文 穴埋めクイズ ターミナル版（Windows / macOS / Linux 対応）

使い方:
    python cli.py

civil_code.json が同じフォルダに必要（無ければ fetch_data.py を先に実行）。
Windows Terminal / PowerShell / cmd で動作。日本語が化ける場合は
先に `chcp 65001` を実行するか、Windows Terminal を使ってください。
"""

from __future__ import annotations

import os
import random
import sys

import minpo_core as m

# --- Windows コンソールの UTF-8 / ANSI 有効化 ---
if os.name == "nt":
    os.system("")  # ANSI エスケープを有効化（Windows 10+）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

# ANSI カラー（対応しない端末では見た目が崩れないよう最小限）
C_RESET = "\033[0m"
C_TITLE = "\033[1;36m"   # シアン太字
C_BLANK = "\033[1;31m"   # 赤太字
C_OK = "\033[1;32m"      # 緑
C_NG = "\033[1;31m"      # 赤
C_DIM = "\033[2m"

MARK = {"correct": "○", "almost": "△", "wrong": "×"}
QUIT_WORDS = {"q", "quit", "exit", "終了", "しゅうりょう"}


def color(s: str, c: str) -> str:
    return f"{c}{s}{C_RESET}"


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def choose_scope() -> dict:
    print(color("\n=== 民法 穴埋めクイズ（ターミナル版） ===", C_TITLE))
    print("出題範囲を選んでください:")
    print("  1) テスト範囲（既定：1〜169・175〜207・239〜294 条）")
    print("  2) 編で選ぶ（総則/物権/債権/親族/相続）")
    print("  3) 民法全体")
    print("  4) 条番号を指定")
    sel = ask("> ") or "1"

    scope = {"1": "test", "2": "part", "3": "all", "4": "num"}.get(sel, "test")
    parts: list[str] = []
    direct = None

    if scope == "part":
        print("\n編を選択（番号をカンマ区切り。例: 1,3）:")
        for i, p in enumerate(m.PART_ORDER, 1):
            print(f"  {i}) {p}")
        raw = ask("> ") or "1"
        for tok in raw.replace("、", ",").split(","):
            tok = tok.strip()
            if tok.isdigit() and 1 <= int(tok) <= len(m.PART_ORDER):
                parts.append(m.PART_ORDER[int(tok) - 1])
        if not parts:
            parts = ["総則"]

    if scope == "num":
        raw = ask("条番号を入力（例: 709）> ")
        direct = int(raw) if raw.isdigit() else None

    raw = ask("空所の数（Enterで自動、1〜8）> ")
    blanks = int(raw) if raw.isdigit() and 1 <= int(raw) <= 8 else None

    return {"scope": scope, "parts": parts, "direct": direct, "blanks": blanks}


def build_pool(sel: dict, main: list[m.Article]) -> list[m.Article]:
    if sel["scope"] == "test":
        return m.filter_by_ranges(main, m.TEST_RANGES)
    if sel["scope"] == "part":
        return m.filter_by_parts(main, sel["parts"])
    return main


def play_one(quiz: m.Quiz) -> tuple[bool, str]:
    """1問出題して (正解か, 制御文字列) を返す。制御は ''/'__quit__'/'__menu__'。"""
    body = quiz.body
    for i in range(len(quiz.answers)):
        body = body.replace(f"【 {i + 1} 】", color(f"【 {i + 1} 】", C_BLANK))
    print(color("\n── 問題 ──", C_TITLE))
    print(body)
    print("-" * 40)

    # 選択肢（組み合わせ4択）
    options = quiz.combined
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    print(color("（番号を入力 / q=終了 / m=メニュー）", C_DIM))

    raw = ask("> ").lower()
    if raw in QUIT_WORDS:
        return False, "__quit__"
    if raw == "m":
        return False, "__menu__"
    chosen = options[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(options) else ""

    ok = chosen == quiz.combined_answer
    print()
    head = quiz.title + (f"（{quiz.part}編）" if quiz.part else "")
    print(color(f"── {head} ──", C_TITLE))
    if quiz.caption:
        print(color(quiz.caption, C_DIM))
    if ok:
        print(color("○ 正解！", C_OK))
    else:
        print(color(f"× 不正解　正答: {quiz.combined_answer}", C_NG))
        if chosen:
            print(f"  あなたの回答: {chosen}")

    # 答え合わせ後の全文
    filled = quiz.body
    for i, ans in enumerate(quiz.answers):
        filled = filled.replace(f"【 {i + 1} 】", color(ans, C_OK))
    print(color("\n【全文】", C_DIM))
    print(filled)
    return ok, ""


def main():
    if not os.path.exists("civil_code.json"):
        print("civil_code.json が見つかりません。先に `python fetch_data.py` "
              "を実行してデータを取得してください。")
        sys.exit(1)

    print("民法データを読み込み中...")
    arts = m.load_articles("civil_code.json")
    main_arts = m.main_articles(arts)
    index = m.build_index(main_arts)
    vocab = m.load_vocab()
    print(f"読み込み完了（本則 {len(main_arts)} 条 / 語彙 {len(vocab)}）")

    total = correct = 0
    wrong_nums: list[int] = []

    while True:
        sel = choose_scope()
        rng = random.Random()

        # 条番号指定は1問だけ
        if sel["scope"] == "num":
            art = index.get(sel["direct"]) if sel["direct"] else None
            if not art:
                print("その条番号は見つかりませんでした。")
                continue
            quiz = m.generate_quiz(art, num_blanks=sel["blanks"], rng=rng, vocab=vocab)
            if not quiz:
                print("この条文は穴埋めを作成できませんでした。")
                continue
            ok, ctrl = play_one(quiz)
            if ctrl == "__quit__":
                break
            if ctrl == "__menu__":
                continue
            total += 1
            correct += 1 if ok else 0
            if not ok and art.num:
                wrong_nums.append(art.num)
            if _post_question(total, correct) == "quit":
                _summary(total, correct, wrong_nums)
                return
            continue

        pool = build_pool(sel, main_arts)
        if not pool:
            print("この条件で出題できる条文がありません。")
            continue

        # 出題ループ
        while True:
            quiz = None
            for _ in range(25):
                art = rng.choice(pool)
                quiz = m.generate_quiz(art, num_blanks=sel["blanks"], rng=rng, vocab=vocab)
                if quiz:
                    break
            if not quiz:
                print("出題できる条文が見つかりませんでした。")
                break

            ok, ctrl = play_one(quiz)
            if ctrl == "__quit__":
                _summary(total, correct, wrong_nums)
                return
            if ctrl == "__menu__":
                break
            total += 1
            correct += 1 if ok else 0
            if not ok and quiz.num:
                wrong_nums.append(quiz.num)

            nxt = _post_question(total, correct)
            if nxt == "quit":
                _summary(total, correct, wrong_nums)
                return
            if nxt == "menu":
                break


def _post_question(total: int, correct: int) -> str:
    rate = f"{correct / total * 100:.0f}%" if total else "—"
    print(color(f"\n[ 成績 {correct}/{total}　正答率 {rate} ]", C_TITLE))
    nxt = ask("Enter=次の問題 / m=メニュー / q=終了 > ").lower()
    if nxt in QUIT_WORDS:
        return "quit"
    if nxt == "m":
        return "menu"
    return "next"


def _summary(total: int, correct: int, wrong_nums: list[int]):
    print(color("\n===== 終了 =====", C_TITLE))
    rate = f"{correct / total * 100:.0f}%" if total else "—"
    print(f"出題 {total} 問 / 正解 {correct} 問 / 正答率 {rate}")
    if wrong_nums:
        uniq = sorted(set(wrong_nums))
        print("間違えた条文: " + ", ".join(f"第{n}条" for n in uniq))
    print("お疲れさまでした。")


if __name__ == "__main__":
    main()
