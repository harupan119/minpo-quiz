"""解説の一括生成パイプライン（レジューム対応・逐次JSON書き出し）。

方式: Claude(このセッション)が中身を生成し、少量バッチごとに explanations.json へ
確定する。レートリミット等で中断しても explanations.json に確定済みの分は残る。

使い方:
    python gen_explanations.py status            # 進捗（確定数/対象数）
    python gen_explanations.py pending [N]        # 未生成の先頭N件を出力(既定12)
    python gen_explanations.py merge              # _expl_batch.json を取り込み確定

対象: テスト範囲（TEST_RANGES）の本則条文を優先。
explanations.json 形式: { "90": {"caption": "（公序良俗）", "point": "…解説…"}, ... }
"""

from __future__ import annotations

import json
import os
import sys

import minpo_core as m

EXPL_PATH = "explanations.json"
BATCH_PATH = "_expl_batch.json"


def _targets() -> list[m.Article]:
    arts = m.main_articles(m.load_articles("civil_code.json"))
    test = m.filter_by_ranges(arts, m.TEST_RANGES)
    # 主条番号ごとに1件（枝番号は代表1つ）。番号順。
    seen: set[int] = set()
    out: list[m.Article] = []
    for a in sorted(test, key=lambda x: (x.num or 0, x.num_raw)):
        if a.num in seen:
            continue
        seen.add(a.num)
        out.append(a)
    return out


def _load_expl() -> dict:
    if os.path.exists(EXPL_PATH):
        with open(EXPL_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_expl(data: dict):
    # 番号順に整列して書き出し（差分を見やすく）
    ordered = {k: data[k] for k in sorted(data, key=lambda x: int(x))}
    with open(EXPL_PATH, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)


def cmd_status():
    expl = _load_expl()
    targets = _targets()
    done = sum(1 for a in targets if str(a.num) in expl)
    print(f"確定 {done} / 対象 {len(targets)} 条（テスト範囲）")
    if done < len(targets):
        nxt = [a.num for a in targets if str(a.num) not in expl][:12]
        print("次の未生成:", nxt)


def cmd_pending(n: int):
    expl = _load_expl()
    targets = _targets()
    pending = [a for a in targets if str(a.num) not in expl][:n]
    out = []
    for a in pending:
        text = a.text.replace("\n", " ")
        if len(text) > 260:
            text = text[:260] + "…"
        out.append({"num": a.num, "caption": a.caption, "text": text})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_merge():
    if not os.path.exists(BATCH_PATH):
        print(f"{BATCH_PATH} がありません。バッチを書き出してから実行してください。")
        sys.exit(1)
    with open(BATCH_PATH, encoding="utf-8") as f:
        batch = json.load(f)
    expl = _load_expl()
    cap = {str(a.num): a.caption for a in _targets()}
    added = 0
    for num, point in batch.items():
        num = str(num)
        if not point or not str(point).strip():
            continue
        expl[num] = {"caption": cap.get(num, ""), "point": str(point).strip()}
        added += 1
    _save_expl(expl)
    os.remove(BATCH_PATH)
    targets = _targets()
    done = sum(1 for a in targets if str(a.num) in expl)
    print(f"取り込み {added} 件 / 確定 {done} / 対象 {len(targets)}")
    nxt = [a.num for a in targets if str(a.num) not in expl][:12]
    print("次の未生成:", nxt)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        cmd_status()
    elif cmd == "pending":
        cmd_pending(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
    elif cmd == "merge":
        cmd_merge()
    else:
        print(__doc__)
