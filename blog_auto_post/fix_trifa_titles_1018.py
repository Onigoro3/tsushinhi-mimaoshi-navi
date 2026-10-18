# -*- coding: utf-8 -*-
"""2026-10-18 社長の答え「a」: Demon の記事タイトル10本に残る「トリファ」を、airalo・Saily に合う題にする。
10-17 の fix_trifa_recommend_text_1017.py(本文のおすすめ文19文)の続き。トリファは 2026-08-25 で提携終了・リンク0本。

- 比較の題は比較の形を保ち、並びからトリファだけを外す(「トリファとairaloどっちが得?」→「airaloとSailyどっちが得?」)
- 本文・カテゴリ・下書き状態は変えない。記事の日付を変えないため、取得した元の <updated> をそのまま送る
- 書き換える前の全記事は scheduled/demon_links/titles_1018/entries_before.json と
  Desktop/_archive/2026-10-18_demon_trifa_titles/entries_before.json に控えた(scan.fetch で取得)

使い方: python fix_trifa_titles_1018.py --dry-run / --apply / --verify
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
sys.path.insert(0, HERE)
from dotenv import dotenv_values  # noqa: E402
from fix_trifa_recommend_text_1017 import put  # noqa: E402  (同じ <updated> を送る PUT)

LINKS = os.path.join(os.path.dirname(os.path.dirname(APP)), "scheduled", "demon_links")
BEFORE = os.path.join(LINKS, "titles_1018", "entries_before.json")
E = "https://magicaidemon.hatenablog.com/entry/"

# (記事, 元の題, 新しい題)
FIXES = [
    (E + "2026/08/20/120227", "eSIM「無制限」の真実|トリファ・airalo・Saily速度制限比較",
     "eSIM「無制限」の真実|airalo・Saily速度制限比較"),
    (E + "2026/08/18/120047", "タイ弾丸旅行のeSIM比較!トリファとairaloどっちが得?",
     "タイ弾丸旅行のeSIM比較!airaloとSailyどっちが得?"),
    (E + "2026/08/17/120528", "韓国長期滞在(30日)のeSIM比較!トリファ・airalo・Sailyで一番お得なのは?",
     "韓国長期滞在(30日)のeSIM比較!airalo・Sailyで一番お得なのは?"),
    (E + "2026/07/25/142051", "海外eSIMの長期滞在プラン比較|1ヶ月以上の駐在・留学・ワーホリで安いのはどれ?(トリファ/airalo/Saily)",
     "海外eSIMの長期滞在プラン比較|1ヶ月以上の駐在・留学・ワーホリで安いのはどれ?(airalo/Saily)"),
    (E + "2026/07/21/142618", "台湾3日間弾丸旅行のeSIM比較!トリファ・airalo・Saily徹底検証",
     "台湾3日間弾丸旅行のeSIM比較!airalo・Saily徹底検証"),
    (E + "2026/07/17/112536", "海外eSIM比較|トリファ・airalo・Saily徹底比較【失敗しない選び方】",
     "海外eSIM比較|airalo・Saily徹底比較【失敗しない選び方】"),
    (E + "2026/07/16/102739", "台湾ロングステイ(30日間)のeSIM徹底比較!トリファ・airalo・Saily",
     "台湾ロングステイ(30日間)のeSIM徹底比較!airalo・Saily"),
    (E + "2026/07/15/140545", "韓国弾丸旅行eSIM比較|トリファ・airalo・Saily",
     "韓国弾丸旅行eSIM比較|airalo・Saily"),
    (E + "2026/07/14/135224", "アメリカ7日間eSIM比較|トリファ・airalo・Saily徹底検証",
     "アメリカ7日間eSIM比較|airalo・Saily徹底検証"),
    (E + "2026/07/13/130148", "ヨーロッパ周遊eSIM比較|トリファ・airalo・Saily 30日間プラン",
     "ヨーロッパ周遊eSIM比較|airalo・Saily 30日間プラン"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="取り直して 題・本文・日付・下書き を控えと比べる")
    a = ap.parse_args()
    env = dotenv_values(os.path.join(APP, ".env"))
    es = {e["url"]: e for e in json.load(open(BEFORE, encoding="utf-8"))}
    for url, old, new in FIXES:
        assert es[url]["title"] == old, f"元の題が違う: {url} {es[url]['title']}"
        assert "トリファ" not in new
    left = [e["url"] for e in es.values() if "トリファ" in e["title"] and e["url"] not in {f[0] for f in FIXES}]
    print(f"書き換える題 {len(FIXES)} 本 / 表に無いトリファの題 {len(left)} 本")
    if a.apply:
        ok = 0
        for url, old, new in FIXES:
            e = dict(es[url]); e["title"] = new
            done = put(env, e, es[url]["content"])
            ok += done
            print("  ", "OK" if done else "NG", url, new)
        print(f"更新 {ok}/{len(FIXES)}")
    if a.verify:
        sys.path.insert(0, LINKS)
        from scan import fetch
        now = {e["url"]: e for e in fetch()}
        json.dump(list(now.values()), open(os.path.join(LINKS, "titles_1018", "entries_after.json"), "w", encoding="utf-8"), ensure_ascii=False)
        bad = 0
        for url, old, new in FIXES:
            n, b = now[url], es[url]
            chk = {"題": n["title"] == new, "本文": n["content"] == b["content"], "日付": n["updated"] == b["updated"],
                   "公開日": n["published"] == b["published"], "下書き": n["draft"] == b["draft"], "カテゴリ": n["categories"] == b["categories"]}
            bad += not all(chk.values())
            print("  ", "OK" if all(chk.values()) else "NG " + ",".join(k for k, v in chk.items() if not v), url, n["updated"])
        print(f"照合 NG {bad} / 題にトリファが残る記事 {sum('トリファ' in e['title'] for e in now.values())} 本")


if __name__ == "__main__":
    main()
