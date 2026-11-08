"""11-09 Q7: はてなブログ(Demon)公開済み2記事の本文からトリファを外す作業用。
段階: fetch(控え保存) / put(書き換え本文を送る・投稿日時=元の updated を送って日付を動かさない)
"""
import os, sys, json, re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import requests
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blog_auto_post.hatena_client import _build_wsse_header, list_entries, ATOM_NS, APP_NS

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
HID = os.environ["HATENA_ID"]; DOM = os.environ["HATENA_BLOG_DOMAIN"]; KEY = os.environ["HATENA_API_KEY"]
BK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_backup_q7_trifa_1109")
TARGETS = ["/entry/2026/07/29/142716", "/entry/2026/07/17/112536"]
A = f"{{{ATOM_NS}}}"

def get(uri):
    r = requests.get(uri, headers={"X-WSSE": _build_wsse_header(HID, KEY)}, timeout=30)
    r.raise_for_status(); return r.content

def parse(raw):
    e = ET.fromstring(raw)
    return {"title": e.find(A+"title").text, "content": e.find(A+"content").text,
            "updated": e.find(A+"updated").text, "published": e.find(A+"published").text,
            "categories": [c.get("term") for c in e.findall(A+"category")],
            "draft": e.find(f"{{{APP_NS}}}control/{{{APP_NS}}}draft").text,
            "url": [l.get("href") for l in e.findall(A+"link") if l.get("rel")=="alternate"][0]}

def fetch():
    idx = {}
    for en in list_entries(HID, DOM, KEY):
        for t in TARGETS:
            if en["url"].endswith(t):
                eid = en["member_uri"].rsplit("/", 1)[1]
                raw = get(en["member_uri"])
                p = os.path.join(BK, f"{eid}.xml")
                if not os.path.exists(p):
                    open(p, "wb").write(raw)
                d = parse(raw); d["member_uri"] = en["member_uri"]; d["entry_id"] = eid
                open(os.path.join(BK, f"{eid}_content_before.html"), "w", encoding="utf-8").write(d["content"])
                idx[t] = {k: d[k] for k in ("entry_id","member_uri","title","updated","published","categories","draft","url")}
    json.dump(idx, open(os.path.join(BK, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(idx, ensure_ascii=False, indent=1))

def put(eid):
    idx = json.load(open(os.path.join(BK, "index.json"), encoding="utf-8"))
    meta = [v for v in idx.values() if v["entry_id"] == eid][0]
    new = open(os.path.join(BK, f"{eid}_content_after.html"), encoding="utf-8").read()
    assert not re.search("トリファ|trifa", new, re.I), "トリファが残っている"
    cats = "".join(f'<category term="{escape(c)}" />' for c in meta["categories"])
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="{ATOM_NS}" xmlns:app="{APP_NS}">
  <title>{escape(meta["title"])}</title>
  <author><name>{escape(HID)}</name></author>
  <content type="text/html">{escape(new)}</content>
  <updated>{meta["updated"]}</updated>
  {cats}
  <app:control><app:draft>no</app:draft></app:control>
</entry>"""
    r = requests.put(meta["member_uri"], data=body.encode("utf-8"),
                     headers={"Content-Type": "application/atom+xml;type=entry;charset=utf-8",
                              "X-WSSE": _build_wsse_header(HID, KEY)}, timeout=30)
    print(r.status_code); r.raise_for_status()
    d = parse(r.content)
    print({k: d[k] for k in ("title","updated","published","draft","url","categories")})


if __name__ == "__main__":
    if sys.argv[1] == "fetch": fetch()
    else: put(sys.argv[2])
