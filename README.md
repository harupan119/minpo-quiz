# ⚖️ 民法 穴埋めクイズ

民法の条文の重要語を **4択** で確認できる学習アプリ。
e-Gov 法令検索 API のデータを使い、法律的に重要な語を優先して穴埋め問題を自動生成します。

## 🌐 Web版（スマホ・PC対応・インストール不要）

**▶ https://harupan-civil-code-jp-quiz.streamlit.app/**

ブラウザで開くだけ。スマホでもそのまま使えます。

### 特徴
- **4択・タップで即判定**（複数空所は組み合わせて1問に、選択肢はTapで表示、パスも可）
- 出題範囲：**テスト範囲プリセット** / **単元（章）ブロック** / 民法全体 / 条番号の範囲指定
- 問題数 5 / 10 / 20 / 無制限
- **条文マップ**：条文ごとの正解/不正解/未出題を色分け表示（網羅状況が一目で分かる）
- **間違えた条文の復習リスト**（正解すると自動で消える）
- **学習データはブラウザに自動保存**（閉じても消えない。「学習データをリセット」で消去）
- 結果画面：正答率・所要時間・全問振り返り

> ※ 選択肢の生成と正誤判定は機械的なものです。学習の補助としてお使いください。

---

## 💻 ターミナル版（Windows / macOS / Linux）

コマンドラインで遊べる版です（`cli.py`）。番号を入力して回答します。

### セットアップ

**Windows（PowerShell / Windows Terminal）**
```powershell
git clone https://github.com/harupan119/minpo-quiz.git
cd minpo-quiz
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python cli.py
```

**macOS / Linux**
```bash
git clone https://github.com/harupan119/minpo-quiz.git
cd minpo-quiz
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python cli.py
```

データ（`civil_code.json` / `vocab.json`）はリポジトリに同梱済みなので、そのまま起動できます。

> Windows で日本語が文字化けする場合は、Windows Terminal を使うか、先に `chcp 65001` を実行してください。

### 操作
- 範囲（テスト範囲 / 編 / 全体 / 条番号）を番号で選ぶ
- 各問、選択肢の**番号を入力**して回答
- `q` = 終了、`m` = メニューに戻る

---

## 🖥️ Web版をローカルで動かす

```bash
# 上記セットアップ後
streamlit run app.py
```

---

## 🛠️ 構成

| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit Web アプリ |
| `cli.py` | ターミナル版 |
| `minpo_core.py` | 中核ロジック（条文解析・4択生成・答え合わせ） |
| `fetch_data.py` | e-Gov API から民法データを取得 → `civil_code.json` |
| `build_vocab.py` | 選択肢の誤答用語彙を生成 → `vocab.json` |

データを更新したいときは `python fetch_data.py` → `python build_vocab.py` を実行します。

## 📚 データ出典・ライセンス

- 条文データ：[e-Gov 法令検索 API v2](https://laws.e-gov.go.jp/)（民法：129AC0000000089）
- 形態素解析：[Janome](https://mocobeta.github.io/janome/)（Apache License 2.0）
- 本アプリは友人が作成した Colab ノートブックの発想を基に再実装したものです。
- License: MIT
