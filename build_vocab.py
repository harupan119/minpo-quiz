"""選択肢（誤答候補）用の語彙 vocab.json を生成する。

全条文から法律用語らしい候補語を抽出し、重要語辞書と統合して保存。
一度実行すればよい（データ更新時に再実行）。
    python build_vocab.py
"""

import json
import time

import minpo_core as m


def main():
    print("民法データ読み込み...")
    arts = m.load_articles("civil_code.json")
    main_arts = m.main_articles(arts)

    print(f"語彙を抽出中（{len(main_arts)} 条）...")
    t0 = time.time()
    words: set[str] = set(m.IMPORTANT_TERMS)
    for i, a in enumerate(main_arts):
        for w in m._extract_candidates(a.text):
            if 2 <= len(w) <= 8 and m._score(w) >= 2.0:
                words.add(w)
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(main_arts)} ... {time.time() - t0:.1f}s")

    vocab = sorted(words)
    with open("vocab.json", "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)
    print(f"vocab.json を保存（{len(vocab)} 語, {time.time() - t0:.1f}s）")


if __name__ == "__main__":
    main()
