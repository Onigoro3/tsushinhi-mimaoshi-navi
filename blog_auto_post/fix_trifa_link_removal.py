"""トリファ(バリューコマース提携)終了対応: 公開済み記事のアフィリエイトリンク差し替え。

2026-08-20、バリューコマースより「海外eSIM No.1アプリ トリファプログラム」が
2026-08-25で終了する旨の通知を受領。終了日翌日以降、削除しなかったテキストリンクは
リンク切れになる(バナー広告は自動削除されるがテキストリンクは手動対応が必要、との案内)。

対応方針: 記事の内容(比較表の行・紹介文)自体は変更せず、トリファのアフィリエイト
referralリンク(`https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3775807&pid=892657918`)
だけを、公式サイトの素のURL(`https://www.trifa.co/`、アフィリエイト追跡なし)に置換する。
これにより終了後もリンク自体は生きたまま維持される(読者体験を壊さない)。

list_entries()で全記事を取得し、対象URLを含む記事のみをupdate_entry()で更新する。
"""
import json
import os

import hatena_client as hc

HATENA_ID = "MagicaiDemon"
BLOG_DOMAIN = "magicaidemon.hatenablog.com"
API_KEY = "tpwopuucte"

OLD_URL = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3775807&amp;pid=892657918"
NEW_URL = "https://www.trifa.co/"


def main():
    entries = hc.list_entries(HATENA_ID, BLOG_DOMAIN, API_KEY)
    targets = [e for e in entries if OLD_URL in e["content_html"]]
    print(f"対象記事: {len(targets)}件 / 全{len(entries)}件")

    results = []
    for e in targets:
        count = e["content_html"].count(OLD_URL)
        new_html = e["content_html"].replace(OLD_URL, NEW_URL)
        resp = hc.update_entry(
            member_uri=e["member_uri"],
            hatena_id=HATENA_ID,
            api_key=API_KEY,
            title=e["title"],
            content_html=new_html,
            categories=e.get("categories", []),
            draft=e.get("draft", False),
        )
        results.append({
            "title": e["title"],
            "url": e["url"],
            "occurrences_replaced": count,
            "status_code": resp["status_code"],
        })
        print(f"  updated ({resp['status_code']}, x{count}): {e['title']}")

    with open(os.path.join(os.path.dirname(__file__), "fix_trifa_link_removal_result.json"),
              "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("=== 完了 ===")
    print(f"更新件数: {len(results)}件 / 置換合計: {sum(r['occurrences_replaced'] for r in results)}箇所")


if __name__ == "__main__":
    main()
