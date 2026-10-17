# -*- coding: utf-8 -*-
"""2026-10-17 社長の答え「a」: Demon 本文の「トリファ」のうち、トリファを**おすすめしている文だけ**を
airalo・Saily をすすめる文に書き換える(トリファは 2026-08-25 で提携終了・リンクは 10-17 に0本)。
トリファを比較・説明しているだけの文(比較表の行・点数・価格・注意書き・記事タイトル・内部リンクの題)は残す。

- 書き換える前の全記事は scheduled/demon_links/trifa_1017/entries_before.json と
  Desktop/_archive/2026-10-17_demon_trifa/entries_before.json に控えた(scan.py で取得)
- 記事の日付を変えないため、取得した元の <updated> をそのまま送る(hatena_client.update_entry は今の時刻を送るので使わない)
- 書き換えは「記事URL・元の文(HTMLの一部)・新しい文」の表。元の文が記事に1回だけあることを確かめてから置き換える

使い方: python fix_trifa_recommend_text_1017.py --dry-run / --apply
"""
import argparse
import json
import os
import sys
import time
from xml.sax.saxutils import escape

import requests
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
from blog_auto_post.hatena_client import _build_wsse_header  # noqa: E402

BEFORE = os.path.join(os.path.dirname(os.path.dirname(APP)), "scheduled", "demon_links", "trifa_1017", "entries_before.json")
E = "https://magicaidemon.hatenablog.com/entry/"
AG = "airaloの地域・グローバル向けプラン"

# (記事, 元, 新, 書き換えた「トリファの文」の数)
FIXES = [
    (E + "2026/08/20/120227",
     "そして、複数国を移動する予定がある方や、グローバル共通で使えるプランを求める方にはトリファのようなグローバル対応プランが選択肢になりますが、価格はやや高めである点と、情報の信頼度が「低」である点を踏まえ、契約直前に公式情報を再確認する一手間をおすすめします。",
     f"そして、複数国を移動する予定がある方は、{AG}や、Sailyの地域プランも選択肢になります。対応する国や価格は変わることがあるため、契約直前に公式情報を再確認する一手間をおすすめします。", 1),
    (E + "2026/08/18/120047",
     "弾丸旅行派の方には、価格の安いトリファが向いていると言えるでしょう。1日あたりの単価が抑えられている分、予算を他の観光費用に回しやすいというメリットもあります。",
     "弾丸旅行派の方は、airaloやSailyの少量プランから必要な分だけ選ぶとよいでしょう。容量を絞れば、予算を他の観光費用に回しやすいというメリットもあります。", 1),
    (E + "2026/08/18/120047",
     "地図やSNSなど軽めの利用が中心という方はトリファ(3日間1GB・¥790)、",
     "地図やSNSなど軽めの利用が中心という方はairaloやSailyの少量プラン、", 1),
    (E + "2026/08/17/120528",
     "トリファ(¥5,000・20GB)はグローバル共通で使える利便性が魅力で、韓国以外への渡航も視野に入れている方には有力な候補です。",
     f"韓国以外への渡航も視野に入れている方は、{AG}も公式サイトで確認してみてください。", 1),
    (E + "2026/07/25/142051",
     "短期集中でデータ大量消費:トリファ20GBプランのGB単価の強み",
     "短期集中でデータ大量消費:GB単価で大容量プランを比べる", 1),
    (E + "2026/07/25/142051",
     "データ消費が集中するタイプの滞在者には、トリファの30日20GBプラン(¥5,000・¥250.0/GB)が候補になります。無制限プランほど高額にならず、それでいて容量に余裕を持たせたい方に向いている構成です。ただしこのプランも二次情報源経由の収集データ(信頼度低)であるため、購入直前には必ずトリファ公式サイトで価格と容量を再確認するようにしてください。",
     "データ消費が集中するタイプの滞在者は、airaloやSailyの大容量プランをGB単価(円/GB)で比べて選ぶとよいでしょう。無制限プランほど高額にならず、それでいて容量に余裕を持たせたい方に向いている選び方です。価格と容量は変わることがあるため、購入直前には必ず公式サイトで再確認するようにしてください。", 2),
    (E + "2026/07/25/142051",
     "30〜40日程度の留学で容量を気にせず使いたいならairaloの40日無制限プラン(¥11,700)、データ消費が集中する短期集中型の滞在ならトリファの30日20GBプラン(¥5,000)が、それぞれお得度スコアの面でも有力な候補になります。",
     "30〜40日程度の留学で容量を気にせず使いたいならairaloの40日無制限プラン(¥11,700)が、お得度スコアの面でも有力な候補になります。データ消費が集中する短期集中型の滞在なら、airaloやSailyの大容量プランをGB単価で比べて選ぶとよいでしょう。", 1),
    (E + "2026/07/21/142618",
     "</strong>:トリファは3日間・1GBというシンプルな設定で、日数のムダが出ない点がメリットです。ただし信頼度が「低」と付記されているデータのため、購入前に公式サイトで最新価格を確認するひと手間を忘れないようにしましょう。",
     "</strong>:airaloやSailyで旅程の日数に近いプランを選ぶと、日数のムダを減らせます。購入前に公式サイトで最新価格を確認するひと手間を忘れないようにしましょう。", 1),
    (E + "2026/07/21/142618",
     "トリファは3日間ぴったりのシンプルなグローバル共通プランとして、日数を無駄にしたくない方の選択肢になり得ますが、Saily同様に信頼度「低」のデータである点は念頭に置いてください。",
     "日数を無駄にしたくない方は、旅程の日数に近いプランがあるかをairaloやSailyの公式サイトで確認してみてください。", 1),
    (E + "2026/07/19/142747",
     "一方で、渡航先を問わず柔軟に使える点を重視するなら、グローバル共通のトリファの3日間・1GBプランも候補になるでしょう。",
     f"一方で、渡航先を問わず柔軟に使える点を重視するなら、{AG}も候補になるでしょう。", 1),
    (E + "2026/07/17/112536",
     "短期出張などで「とにかく複数国をまたぐ可能性がある」という方には、グローバル共通で使えるトリファが安心感の面で候補に挙がります。",
     f"短期出張などで「とにかく複数国をまたぐ可能性がある」という方は、{AG}を候補に入れておくと安心です。", 1),
    (E + "2026/07/17/112536",
     "一方、複数国を渡航する可能性がある、グローバル共通の安心感を重視したいという方には、トリファも選択肢として検討する価値があります。",
     f"一方、複数国を渡航する可能性がある方は、{AG}やSailyの地域プランも検討する価値があります。", 1),
    (E + "2026/07/16/102739",
     "1日あたりの高速データ上限が明記されていないトリファやairaloの無制限プランの方が、",
     "1日あたりの高速データ上限が明記されていないairaloの無制限プランの方が、", 1),
    (E + "2026/07/16/102739",
     "トリファ(¥525.0/日、54.3点)は価格面では「標準」判定ですが、渡航先を問わないグローバル共通プランという特性を持つため、台湾以外への渡航も併せて検討している方には検討材料になり得ます。",
     f"台湾以外への渡航も併せて検討している方は、{AG}も検討材料になり得ます。", 1),
    (E + "2026/07/15/140545",
     "</strong>:3日間1GB・¥790のトリファは、シンプルに短期の通信手段を確保したい方に選ばれやすいプランです。",
     "</strong>:airaloやSailyの1GB前後の少量プランなら、シンプルに短期の通信手段を確保できます。", 1),
    (E + "2026/07/15/140545",
     "7日間程度の滞在でコストを抑えたいならSaily、まずはシンプルに試してみたいならトリファ、というのが",
     "7日間程度の滞在でコストを抑えたいならSaily、というのが", 1),
    (E + "2026/07/13/130148",
     "グローバル共通プランという柔軟性を重視するならトリファも候補になりますが、円/日単価では今回の3社の中では最も高い水準である点は理解した上で検討するとよいでしょう。",
     f"グローバル共通プランという柔軟性を重視するなら、{AG}も候補になります。", 1),
    (E + "2026/07/13/130148",
     "「お得」判定のairalo、グローバル共通の柔軟性を求めるならトリファ、という形で整理できます。",
     "「お得」判定のairalo、という形で整理できます。", 1),
]


def put(env, e, content):
    hid, key = env["HATENA_ID"], env["HATENA_API_KEY"]
    cats = "".join(f'<category term="{escape(c, {chr(34): "&quot;"})}" />' for c in e["categories"] if c)
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app">
  <title>{escape(e["title"])}</title>
  <author><name>{escape(hid)}</name></author>
  <content type="text/html">{escape(content)}</content>
  <updated>{e["updated"]}</updated>
  {cats}
  <app:control><app:draft>{"yes" if e["draft"] else "no"}</app:draft></app:control>
</entry>"""
    for _ in range(3):
        r = requests.put(e["member_uri"], data=body.encode("utf-8"), timeout=30,
                         headers={"Content-Type": "application/atom+xml;type=entry;charset=utf-8",
                                  "X-WSSE": _build_wsse_header(hid, key)})
        if r.status_code in (200, 201):
            return True
        time.sleep(5)
    print("   × PUT失敗", r.status_code, r.text[:200])
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    env = dotenv_values(os.path.join(APP, ".env"))
    es = {e["url"]: e for e in json.load(open(BEFORE, encoding="utf-8"))}
    new = {}
    for url, old, rep, _n in FIXES:
        c = new.get(url, es[url]["content"])
        assert c.count(old) == 1, f"元の文が1回ではない: {url} {old[:40]}"
        new[url] = c.replace(old, rep)
    before = sum(e["content"].count("トリファ") for e in es.values())
    after = before - sum(es[u]["content"].count("トリファ") - c.count("トリファ") for u, c in new.items())
    print(f"記事 {len(new)} 本 / 書き換える文 {sum(f[3] for f in FIXES)} / 本文のトリファ {before} → {after}")
    if not a.apply:
        return
    ok = 0
    for url, c in new.items():
        done = put(env, es[url], c)
        ok += done
        print("  ", "OK" if done else "NG", url)
    print(f"更新 {ok}/{len(new)}")


if __name__ == "__main__":
    main()
