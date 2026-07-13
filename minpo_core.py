"""民法穴埋めクイズ 中核ロジック（UI非依存）

e-Gov 法令検索 API v2 で取得した民法JSON(civil_code.json)を読み、
- 条文を編（総則/物権/債権/親族/相続）ごとに構造化
- 法律的に重要な語を優先して穴埋め問題を生成
- 表記ゆれに寛容な答え合わせ
を提供する。
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import dataclass, field

from janome.tokenizer import Tokenizer

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

KANJI_NUM = {
    "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000,
}

# 穴にすると学習効果が薄い語（手続き語・指示語・形式語など）
STOPWORDS = {
    "前条", "前項", "前号", "本条", "本項", "同条", "同項", "同号", "次条", "次項",
    "前各項", "前各号", "各号", "各項", "当該", "場合", "とき", "こと", "もの",
    "ため", "ほか", "これ", "それ", "あれ", "その", "この", "第", "者", "以下",
    "以上", "規定", "前二項", "前三項", "次の", "次に", "本節", "本款", "本目",
}

# 末尾がこれらで終わる語は優先度を下げる（形式的な語尾）
_LOW_PRIORITY_TAIL = re.compile(r"(条|項|号|もの|こと|とき|ため|ほか|等|場合)$")

# 全角/半角・記号を落として比較するための除去対象
_PUNCT = re.compile(r"[\s、。，．・「」『』（）\(\)\[\]【】〔〕,.:：;；\-ー―─]")

# 日本語（漢字・かな・カタカナ）のみで構成される語
_JP_ONLY = re.compile(r"^[一-鿿぀-ゟ゠-ヿァ-ンヴー々]+$")
_KANJI = re.compile(r"[一-鿿]")
_KATAKANA = re.compile(r"[゠-ヿァ-ンヴ]")

# 民法で頻出・重要な語（穴にする優先度を上げる。網羅ではなく加点用の辞書）
IMPORTANT_TERMS = {
    "意思表示", "法律行為", "権利能力", "行為能力", "意思能力", "制限行為能力者",
    "成年被後見人", "被保佐人", "被補助人", "未成年者", "法定代理人", "代理人",
    "代理権", "無権代理", "表見代理", "善意", "悪意", "過失", "重大な過失",
    "第三者", "対抗", "対抗要件", "登記", "引渡し", "占有", "所有権", "共有",
    "地上権", "地役権", "留置権", "先取特権", "質権", "抵当権", "根抵当権",
    "物権", "債権", "債務", "債務者", "債権者", "連帯債務", "保証", "連帯保証",
    "保証人", "履行", "不履行", "債務不履行", "履行遅滞", "履行不能", "受領遅滞",
    "損害賠償", "損害", "解除", "同時履行", "危険負担", "弁済", "供託", "相殺",
    "更改", "免除", "混同", "契約", "申込み", "承諾", "売買", "贈与", "賃貸借",
    "使用貸借", "消費貸借", "請負", "委任", "寄託", "不当利得", "不法行為",
    "故意", "因果関係", "権利", "利益", "時効", "取得時効", "消滅時効", "援用",
    "追認", "取消し", "取り消し", "無効", "錯誤", "詐欺", "強迫", "虚偽表示",
    "心裡留保", "条件", "期限", "停止条件", "解除条件", "相続", "相続人",
    "被相続人", "遺産", "遺言", "遺留分", "相続分", "遺贈", "配偶者", "扶養",
    "婚姻", "離婚", "親権", "養子", "嫡出", "認知", "抵当権者", "求償", "求償権",
    "催告", "通知", "背信的悪意者", "使用者", "占有者", "果実", "元本", "利息",
    "特定物", "種類物", "履行の提供", "受働債権", "自働債権", "詐害行為",
}

# 民法の編（law_full_text 内の Part 順）
PART_ORDER = ["総則", "物権", "債権", "親族", "相続"]

# 元コード由来の「テスト最適化範囲」（主条番号ベース）。プリセットとして保持
TEST_RANGES = [(1, 169), (175, 207), (239, 294)]


# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------

@dataclass
class Article:
    num: int | None          # 主条番号（第709条 -> 709）。枝番号は無視した整数
    num_raw: str             # 元のNum属性（"709", "709_2" 等）
    title: str               # 表示見出し（"第七百九条"）
    caption: str             # 見出し（"（不法行為による損害賠償）"）
    part: str | None         # 編名（"債権" 等）。附則等はNone
    text: str                # クイズ本文（項を改行で連結）
    chapter: str | None = None   # 章名（"法律行為" 等）。単元ブロック用


# ---------------------------------------------------------------------------
# JSON 解析
# ---------------------------------------------------------------------------

def _plain_text(node) -> str:
    """ルビ(Rt)を除いてテキストを再帰的に抽出。"""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("tag") == "Rt":
            return ""
        return "".join(_plain_text(c) for c in node.get("children", []))
    if isinstance(node, list):
        return "".join(_plain_text(c) for c in node)
    return ""


def _structured_text(node, depth: int = 0) -> str:
    """項・号・イの階層を軽くインデントしつつテキスト化。"""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if node.get("tag") == "Rt":
        return ""

    tag = node.get("tag") or ""
    is_item = tag == "Item"
    is_subitem = tag.startswith("Subitem")

    inner = ""
    for child in node.get("children", []):
        inner += _structured_text(child, depth + 1)

    if is_item:
        return f"\n　　{inner.strip()}"
    if is_subitem:
        return f"\n　　　{inner.strip()}"
    return inner


def _kanji_to_int(s: str) -> int | None:
    s = s.replace("第", "").replace("条", "").replace("の", "-")
    parts = re.split(r"[^" + "".join(KANJI_NUM.keys()) + r"]", s)
    for part in parts:
        if not part:
            continue
        total, tmp = 0, 0
        for ch in part:
            if ch not in KANJI_NUM:
                break
            val = KANJI_NUM[ch]
            if val >= 10:
                if tmp == 0:
                    tmp = 1
                total += tmp * val
                tmp = 0
            else:
                tmp = val
        total += tmp
        if total > 0:
            return total
    return None


def _article_num(art: dict) -> tuple[int | None, str]:
    raw = art.get("attr", {}).get("Num", "") or ""
    if raw:
        m = re.match(r"(\d+)", raw)
        if m:
            return int(m.group(1)), raw
    # Num属性が無ければ ArticleTitle から漢数字変換
    for c in art.get("children", []):
        if c.get("tag") == "ArticleTitle":
            title = _plain_text(c).strip()
            return _kanji_to_int(title), raw
    return None, raw


def load_articles(json_path: str = "civil_code.json") -> list[Article]:
    """civil_code.json を読み、編ごとに構造化した Article のリストを返す。"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    root = data.get("law_full_text", data) if isinstance(data, dict) else data

    articles: list[Article] = []

    def walk(node, current_part: str | None, current_chapter: str | None):
        if isinstance(node, dict):
            tag = node.get("tag")
            if tag == "Part":
                title = ""
                for c in node.get("children", []):
                    if c.get("tag") == "PartTitle":
                        title = _plain_text(c)
                        break
                # "第三編　債権" -> "債権"
                m = re.search(r"編[\s　]*(.+)$", title)
                current_part = m.group(1).strip() if m else title.strip()
                current_chapter = None
            if tag == "Chapter":
                title = ""
                for c in node.get("children", []):
                    if c.get("tag") == "ChapterTitle":
                        title = _plain_text(c)
                        break
                # "第五章　法律行為" -> "法律行為"
                m = re.search(r"章[\s　]*(.+)$", title)
                current_chapter = m.group(1).strip() if m else title.strip()
            if tag == "Article":
                articles.append(_build_article(node, current_part,
                                               current_chapter))
            for c in node.get("children", []):
                walk(c, current_part, current_chapter)
        elif isinstance(node, list):
            for x in node:
                walk(x, current_part, current_chapter)

    walk(root, None, None)
    return articles


def _build_article(art: dict, part: str | None,
                   chapter: str | None = None) -> Article:
    num, raw = _article_num(art)
    caption = ""
    title = ""
    paragraphs: list[str] = []
    for c in art.get("children", []):
        t = c.get("tag")
        if t == "ArticleCaption":
            caption = _plain_text(c).strip()
        elif t == "ArticleTitle":
            title = _plain_text(c).strip()
        elif t == "Paragraph":
            paragraphs.append(_structured_text(c).strip())
    text = "\n".join(p for p in paragraphs if p)
    return Article(num=num, num_raw=raw, title=title, caption=caption,
                   part=part, text=text, chapter=chapter)


def main_articles(articles: list[Article]) -> list[Article]:
    """本則（5編に属し本文のある条文）のみ。附則・改正条文・削除条文を除く。"""
    return [
        a for a in articles
        if a.part in PART_ORDER
        and a.text
        and a.text.replace("　", "").strip() != "削除"
    ]


def filter_by_parts(articles: list[Article], parts: list[str]) -> list[Article]:
    if not parts:
        return list(articles)
    s = set(parts)
    return [a for a in articles if a.part in s]


def filter_by_ranges(articles: list[Article],
                     ranges: list[tuple[int, int]]) -> list[Article]:
    if not ranges:
        return list(articles)
    out = []
    for a in articles:
        if a.num is None:
            continue
        if any(lo <= a.num <= hi for lo, hi in ranges):
            out.append(a)
    return out


def blocks_by_chapter(articles: list[Article]) \
        -> list[tuple[str, str, list[Article]]]:
    """(編, 章, 条文リスト) を本文中の出現順で返す（単元ブロック用）。"""
    order: list[tuple[str, str]] = []
    grouped: dict[tuple[str, str], list[Article]] = {}
    for a in articles:
        if not a.part or not a.chapter:
            continue
        key = (a.part, a.chapter)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(a)
    return [(p, c, grouped[(p, c)]) for p, c in order]


def build_index(articles: list[Article]) -> dict[int, Article]:
    """主条番号 -> Article。本則を優先（最初に現れたものを採用）。"""
    idx: dict[int, Article] = {}
    for a in articles:
        if a.num is not None and a.num not in idx:
            idx[a.num] = a
    return idx


def display_title(art: Article) -> str:
    """'第709条' / '第709条の2' 形式の見出しを返す。"""
    if art.num_raw:
        parts = re.split(r"[-_]", art.num_raw)
        if len(parts) == 1:
            return f"第{parts[0]}条"
        return f"第{parts[0]}条の" + "の".join(parts[1:])
    if art.num is not None:
        return f"第{art.num}条"
    return art.title or "不明な条文"


# ---------------------------------------------------------------------------
# 穴埋め問題の生成
# ---------------------------------------------------------------------------

_tokenizer = Tokenizer(mmap=False)


def _extract_candidates(text: str) -> list[str]:
    """janomeで複合名詞を抽出し、重複を除いた候補語を返す（出現順）。"""
    candidates: list[str] = []
    seen: set[str] = set()
    buf: list[str] = []

    def flush():
        if not buf:
            return
        word = "".join(buf).strip()
        buf.clear()
        if len(word) < 2 or not _JP_ONLY.match(word):
            return
        if word in seen:
            return
        seen.add(word)
        candidates.append(word)

    for token in _tokenizer.tokenize(text):
        pos = token.part_of_speech.split(",")
        is_noun = pos[0] == "名詞" and pos[1] not in ("代名詞", "数", "非自立", "接尾")
        is_prefix = pos[0] == "接頭詞"
        if is_noun or is_prefix:
            buf.append(token.surface.strip())
        else:
            flush()
    flush()
    return candidates


def _score(word: str) -> float:
    """穴にする優先度スコア。高いほど良問になりやすい。"""
    if word in STOPWORDS:
        return 0.0
    score = 1.0
    n = len(word)
    score += min(n, 6) * 0.6                      # 長い複合語ほど加点
    kanji = len(_KANJI.findall(word))
    if kanji == n and n >= 2:                      # 全て漢字（法律用語らしい）
        score += 2.0
    elif _KATAKANA.search(word):                   # カタカナ語
        score += 0.5
    if word in IMPORTANT_TERMS:                    # 重要語辞書に一致
        score += 6.0
    if _LOW_PRIORITY_TAIL.search(word):            # 形式的な語尾
        score *= 0.4
    return score


def _weighted_sample(items: list[tuple[str, float]], k: int,
                     rng: random.Random) -> list[str]:
    """スコアを重みにした非復元の重み付きサンプリング。"""
    pool = [(w, s) for w, s in items if s > 0]
    chosen: list[str] = []
    while pool and len(chosen) < k:
        total = sum(s for _, s in pool)
        r = rng.uniform(0, total)
        acc = 0.0
        for i, (w, s) in enumerate(pool):
            acc += s
            if r <= acc:
                chosen.append(w)
                pool.pop(i)
                break
    return chosen


def load_vocab(path: str = "vocab.json") -> list[str]:
    """選択肢の誤答候補となる語彙を読み込む。無ければ重要語辞書で代用。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return sorted(IMPORTANT_TERMS)


def _make_choices(answer: str, vocab: list[str], rng: random.Random,
                  exclude: set[str], k: int = 4) -> list[str]:
    """正答 answer に対し、紛らわしい誤答を混ぜた k 択を作って返す。"""
    L = len(answer)
    ans_all_kanji = len(_KANJI.findall(answer)) == L and L > 0

    cands = [
        w for w in vocab
        if w != answer and w not in exclude
        and w not in answer and answer not in w
    ]

    def similarity(w: str) -> int:
        s = 0
        d = abs(len(w) - L)
        if d == 0:
            s += 3
        elif d == 1:
            s += 2
        elif d == 2:
            s += 1
        if (len(_KANJI.findall(w)) == len(w)) == ans_all_kanji:
            s += 1
        return s

    rng.shuffle(cands)
    cands.sort(key=similarity, reverse=True)
    # 紛らわしい上位から少しランダムに選ぶ
    top = cands[:max(k * 8, 24)]
    rng.shuffle(top)
    distractors = top[:k - 1]

    # 候補が足りなければ重要語で補完
    if len(distractors) < k - 1:
        for w in IMPORTANT_TERMS:
            if w != answer and w not in exclude and w not in distractors:
                distractors.append(w)
            if len(distractors) >= k - 1:
                break

    options = distractors[:k - 1] + [answer]
    rng.shuffle(options)
    return options


@dataclass
class Quiz:
    title: str                       # "第709条"
    caption: str                     # "（不法行為による損害賠償）"
    part: str | None
    body: str                        # 【1】等に置換済みの本文
    answers: list[str]               # blank番号順の正答（0-indexed）
    source_text: str                 # 元の本文（答え合わせ後の全文表示用）
    num: int | None = None           # 主条番号（復習リスト用）
    choices: list[list[str]] = field(default_factory=list)  # blank順の選択肢（正答含む）
    combined: list[str] = field(default_factory=list)       # 全空所を1問にまとめた選択肢
    combined_answer: str = ""                               # combined の正答


def generate_quiz(art: Article, num_blanks: int | None = None,
                  rng: random.Random | None = None,
                  vocab: list[str] | None = None,
                  n_choices: int = 4) -> Quiz | None:
    """1条文から穴埋め問題を生成する。生成不能なら None。

    vocab を渡すと各空所に n_choices 択の選択肢（正答含む）を付与する。
    """
    rng = rng or random.Random()
    text = art.text
    if not text or len(_KANJI.findall(text)) < 3:
        return None

    candidates = _extract_candidates(text)
    scored = [(w, _score(w)) for w in candidates]
    scored = [(w, s) for w, s in scored if s > 0]
    if not scored:
        return None

    # 穴の数：本文長と項数から自動決定（指定があれば優先）
    if num_blanks is None:
        auto = max(1, len(text) // 110)
        num_blanks = auto
    num_blanks = max(1, min(num_blanks, len(scored), 8))

    picked = _weighted_sample(scored, num_blanks, rng)
    if not picked:
        return None

    # 出現位置順に並べて blank 番号を割り当て
    picked = sorted(set(picked), key=lambda w: text.find(w))
    answers = picked

    # 長い語から順に一意プレースホルダへ（部分文字列衝突を回避）
    order_by_len = sorted(enumerate(picked), key=lambda x: len(x[1]), reverse=True)
    tmp = text
    for idx, word in order_by_len:
        tmp = tmp.replace(word, f"\x00{idx}\x00")
    for idx in range(len(picked)):
        tmp = tmp.replace(f"\x00{idx}\x00", f"【 {idx + 1} 】")

    choices: list[list[str]] = []
    combined: list[str] = []
    combined_answer = ""
    if vocab:
        answer_set = set(answers)
        for ans in answers:
            exclude = answer_set - {ans}
            choices.append(_make_choices(ans, vocab, rng, exclude, n_choices))

        # 参考アプリ方式：全空所を1問にまとめた選択肢（正答の組み合わせ＋誤答の組み合わせ）
        combined_answer = "／".join(answers)
        combined = [combined_answer]
        tries = 0
        while len(combined) < n_choices and tries < 300:
            tries += 1
            combo = list(answers)
            k = rng.randint(1, len(answers))         # いくつの空所を誤答に差し替えるか
            for p in rng.sample(range(len(answers)), k):
                distr = [c for c in choices[p] if c != answers[p]]
                if distr:
                    combo[p] = rng.choice(distr)
            s = "／".join(combo)
            if s != combined_answer and s not in combined:
                combined.append(s)
        rng.shuffle(combined)

    return Quiz(
        title=display_title(art),
        caption=art.caption,
        part=art.part,
        body=tmp,
        answers=answers,
        source_text=text,
        num=art.num,
        choices=choices,
        combined=combined,
        combined_answer=combined_answer,
    )


# ---------------------------------------------------------------------------
# 答え合わせ（表記ゆれに寛容）
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.strip().lower()
    s = _PUNCT.sub("", s)
    return s


def judge(user: str, answer: str) -> str:
    """'correct' / 'almost' / 'wrong' を返す。"""
    nu, na = _normalize(user), _normalize(answer)
    if not nu:
        return "wrong"
    if nu == na:
        return "correct"
    # 送り仮名・部分入力の許容
    if nu in na or na in nu:
        return "almost"
    # 近似（送り仮名ゆれなど）
    import difflib
    if difflib.SequenceMatcher(None, nu, na).ratio() >= 0.75:
        return "almost"
    return "wrong"


def is_pass(status: str) -> bool:
    """正解扱い（correct/almost）か。"""
    return status in ("correct", "almost")
