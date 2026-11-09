"""11-09 社長「3 外して」: はてな(Demon)の全記事でトリファ/Trifa を含む物を数えるだけ(読むだけ)"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _q7_remove_trifa_1109 import get, parse, HID, DOM, KEY
from blog_auto_post.hatena_client import list_entries
out=[]
for en in list_entries(HID, DOM, KEY):
    d=parse(get(en["member_uri"]))
    t=len(re.findall("トリファ|trifa",d["title"] or "",re.I)); c=len(re.findall("トリファ|trifa",d["content"] or "",re.I))
    if t or c: out.append({"url":d["url"],"title":d["title"],"title_hits":t,"body_hits":c,"draft":d["draft"],"member_uri":en["member_uri"]})
json.dump(out,open("data/_trifa_scan_1109.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
for o in out: print(o["title_hits"],o["body_hits"],o["draft"],o["url"][-25:],o["title"][:60])
print(len(out))
