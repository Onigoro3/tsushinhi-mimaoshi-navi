"""公開済み記事に「eSIMとレンタルWiFi、どちらが向くか」の段落を1つ足す(2026-09-21)。

社長判断(09-21「入れて」)に基づく。高単価案件(グローバルWiFi、1件¥1,320)は09-21に
バリューコマースで即時提携済み(プログラムID 2143810 / pid 892709163)。

方針:
- 置く記事は Search Console の実測(3か月)で表示が多く、かつレンタルWiFiの話が
  本文の流れに乗る4本だけ。「帰国後どうする」「主回線の確認」など購買文脈のない記事には置かない。
- eSIMを否定しない(既存のairalo・Sailyの収益を食わないため)。向き不向きの比較にする。
- 記事ごとに書き出しを変える(同じ文章の使い回しを避ける)。
- 1記事1リンクまで。末尾に広告表記を入れる(ステマ規制)。
- すでに pid=892709163 を含む記事は二重に足さない。

使い方: python add_global_wifi_block.py        (試し実行、書き込みなし)
        python add_global_wifi_block.py --apply (実際に更新)
"""
import sys

import affiliate
import hatena_client as hc

HATENA_ID = "MagicaiDemon"
BLOG_DOMAIN = "magicaidemon.hatenablog.com"
API_KEY = "tpwopuucte"

LINK = affiliate.to_affiliate_url("グローバルWiFi")

# entryのパス -> その記事に合わせた書き出し
TARGETS = {
    "/entry/2026/08/14/131317": "乗り継ぎの待ち時間だけなら空港のWi-Fiで足りますが、移動中もずっとつなぎたい場合は、eSIMとレンタルWiFiのどちらが向くかで選び方が変わります。",
    "/entry/2026/08/12/131227": "テザリングでどうしても足りない、設定が面倒だという場合は、はじめからレンタルWiFiを1台借りてしまう手もあります。",
    "/entry/2026/07/31/144028": "4〜5日でも動画をよく見る、家族の端末もつなぐ、という使い方なら、eSIMより1台のレンタルWiFiのほうが結果的に楽なことがあります。",
    "/entry/2026/08/21/120741": "残量を気にしながら使うのが性に合わない場合は、大容量のレンタルWiFiに切り替えるという選び方もあります。",
}

BODY = """
<h3>eSIMとレンタルWiFi、どちらが向くか</h3>
<p>{intro}</p>
<p>ひとり旅で、地図と連絡が中心――という使い方なら、eSIMのほうが安く、受け取りも返却もいりません。反対に、次のような場合はレンタルWiFiのほうが向きます。</p>
<ul>
<li>2人以上で行き、1つの通信を分け合いたい</li>
<li>動画やテザリングでたくさん使う予定がある</li>
<li>自分の端末がeSIMに対応しているか自信がない</li>
</ul>
<p>レンタルWiFiには、空港などでの受け取りと返却の手間、1日あたりの料金がかかります。それでも「設定でつまずきたくない」「家族全員つなぎたい」なら候補になります。<a href="{link}" rel="nofollow">海外WiFiレンタルのグローバルWiFi</a>は空港で受け取れて、対応している国も広めです。</p>
<p><small>※この段落には広告(アフィリエイトリンク)を含みます。</small></p>
"""


def main() -> None:
    apply = "--apply" in sys.argv
    entries = hc.list_entries(HATENA_ID, BLOG_DOMAIN, API_KEY)
    by_path = {}
    for e in entries:
        url = e.get("url") or ""
        for path in TARGETS:
            if url.endswith(path):
                by_path[path] = e

    print(f"全記事 {len(entries)}件 / 対象 {len(by_path)}/{len(TARGETS)}件")
    for path, intro in TARGETS.items():
        e = by_path.get(path)
        if not e:
            print(f"  × 見つからない: {path}")
            continue
        if "892709163" in e["content_html"]:
            print(f"  - すでに入っている: {e['title'][:30]}")
            continue
        new_html = e["content_html"].rstrip() + "\n" + BODY.format(intro=intro, link=LINK)
        print(f"  ✓ {'更新' if apply else '更新予定'}: {e['title'][:40]} (+{len(new_html) - len(e['content_html'])}文字)")
        if apply:
            hc.update_entry(
                member_uri=e["member_uri"],
                hatena_id=HATENA_ID,
                api_key=API_KEY,
                title=e["title"],
                content_html=new_html,
                categories=e.get("categories") or [],
                draft=False,
            )
    if not apply:
        print("※試し実行です。実際に書き込むには --apply を付けてください")


if __name__ == "__main__":
    main()
