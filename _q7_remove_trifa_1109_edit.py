"""11-09 Q7: 記事 /entry/2026/07/17/112536 の本文からトリファを外す置換(控え→after を作る)。"""
import os, re
BK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_backup_q7_trifa_1109")
EID = "14945776032054433597"
s = open(os.path.join(BK, f"{EID}_content_before.html"), encoding="utf-8").read()
R = [
 ("海外eSIM主要3社(トリファ・airalo・Saily)を", "海外eSIM主要2社(airalo・Saily)を"),
 ("海外eSIMおすすめ比較:トリファ・airalo・Sailyどれを選ぶべきか", "海外eSIMおすすめ比較:airalo・Sailyどちらを選ぶべきか"),
 ("海外eSIM主要3社である<strong>トリファ・airalo・Saily</strong>を", "海外eSIM主要2社である<strong>airalo・Saily</strong>を"),
 ("まずは3社の主要プランを整理してみましょう。今回比較するのは、トリファのグローバル共通7日間プラン、airaloのアメリカ向け7日間プラン、Sailyのアメリカ向け7日間プランです。いずれも",
  "まずは2社の主要プランを整理してみましょう。今回比較するのは、airaloのアメリカ向け7日間プラン、Sailyのアメリカ向け7日間プランです。どちらも"),
 ("トリファは価格¥5,990、airaloは¥4,550、Sailyは¥4,493(参考:$28.99)となっており、表面上の価格だけを見るとトリファがやや高めに感じる方も多いはずです。ただしトリファはグローバル共通で使えるプランである一方、airaloとSailyは渡航先(アメリカ)に特化したプランという違いがある点も見逃せません。",
  "airaloは価格¥4,550、Sailyは¥4,493(参考:$28.99)となっており、表面上の価格はほぼ並んでいます。どちらも渡航先(アメリカ)に特化したプランです。"),
 ('※上記のうちトリファ・Sailyの料金は、', '※上記のうちSailyの料金は、'),
 ("なお、トリファとSailyについては二次情報源経由", "なお、Sailyについては二次情報源経由"),
 ("この単価で見ると、トリファは¥855.7/日、airaloは¥650.0/日、Sailyは¥641.9/日となっており、airaloとSailyのほうがトリファよりも割安であることが分かります。",
  "この単価で見ると、airaloは¥650.0/日、Sailyは¥641.9/日となっており、Sailyがわずかに割安であることが分かります。"),
 ("airaloが73.4点で同じく「お得」判定、トリファは55.8点で「標準」判定となりました。", "airaloが73.4点で同じく「お得」判定となりました。"),
 ("一方トリファは「標準」判定ではあるものの、グローバル共通で使えるという独自の強みがある点は数値だけでは測れない部分です。", ""),
 ("ここまで、トリファ・airalo・Sailyという海外eSIM主要3社を", "ここまで、airalo・Sailyという海外eSIM主要2社を"),
 ("ただし、トリファとSailyのデータは二次情報源経由", "ただし、Sailyのデータは二次情報源経由"),
]
for a, b in R:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
# 比較表のトリファ行を削る
row = re.findall(r"<tr><td>トリファ.*?</tr>", s)
assert len(row) == 1; s = s.replace(row[0], "")
# 関連記事: 題名にトリファが入る他記事へのリンク(3件)と、それだけの小見出しを外す
grp = re.findall(r'<p style="font-weight:bold;margin:1em 0 0.3em;">3社徹底比較\(渡航先別\)</p><ul[^>]*>.*?</ul>', s)
assert len(grp) == 1; s = s.replace(grp[0], "")
li = re.findall(r'<li><a href="[^"]+">[^<]*トリファ[^<]*</a></li>', s)
assert len(li) == 1; s = s.replace(li[0], "")
assert not re.search("トリファ|trifa", s, re.I)
open(os.path.join(BK, f"{EID}_content_after.html"), "w", encoding="utf-8").write(s)
print("ok", len(s))
