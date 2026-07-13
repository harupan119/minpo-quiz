"""民法の条文データを e-Gov 法令検索 API v2 から取得して civil_code.json に保存。

一度実行すればオフラインで動く。データ更新したいときに再実行する。
    python fetch_data.py
"""

import json
import sys

import requests

# 129AC0000000089 = 民法（明治二十九年法律第八十九号）
URL = "https://laws.e-gov.go.jp/api/2/law_data/129AC0000000089"
OUT = "civil_code.json"


def main():
    print("e-Gov 法令検索 API から民法データを取得中...")
    try:
        r = requests.get(URL, timeout=60)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"取得に失敗しました: {e}")
        sys.exit(1)

    data = r.json()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"「{OUT}」に保存しました。")


if __name__ == "__main__":
    main()
