"""11-09 社長「3 外して」: data/_backup_trifa14_1109 の after 本文を14本へ送る(題名・カテゴリ・updated は元のまま)"""
import os, sys, json, re, requests
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _q7_remove_trifa_1109 import parse, HID, ATOM_NS, APP_NS
from blog_auto_post.hatena_client import _build_wsse_header
from _q7_remove_trifa_1109 import KEY
BK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_backup_trifa14_1109")
idx = json.load(open(os.path.join(BK, "index.json"), encoding="utf-8"))
def put(eid):
    m = idx[eid]; old = parse(open(os.path.join(BK, f"{eid}.xml"), "rb").read())
    new = open(os.path.join(BK, f"{eid}_content_after.html"), encoding="utf-8").read()
    assert not re.search("トリファ|trifa", new, re.I)
    cats = "".join(f'<category term="{escape(c)}" />' for c in old["categories"])
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="{ATOM_NS}" xmlns:app="{APP_NS}">
  <title>{escape(old["title"])}</title>
  <author><name>{escape(HID)}</name></author>
  <content type="text/html">{escape(new)}</content>
  <updated>{old["updated"]}</updated>
  {cats}
  <app:control><app:draft>{old["draft"]}</app:draft></app:control>
</entry>"""
    r = requests.put(m["member_uri"], data=body.encode("utf-8"), headers={"Content-Type": "application/atom+xml;type=entry;charset=utf-8", "X-WSSE": _build_wsse_header(HID, KEY)}, timeout=30)
    r.raise_for_status(); d = parse(r.content)
    ok = d["title"] == old["title"] and d["published"] == old["published"] and not re.search("トリファ|trifa", d["content"], re.I)
    print(r.status_code, "OK" if ok else "★要確認", d["url"][-20:], d["title"][:30], d["published"], d["draft"])
for eid in (sys.argv[1:] or list(idx)):
    put(eid)
