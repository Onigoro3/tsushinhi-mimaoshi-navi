# 11-09 社長裁定 Q9「削除して」: Demon hold② 16件(11-01 会議の分類)を demon_topics から削除。控えを data/ へ
import sys, json
from dotenv import load_dotenv
load_dotenv(); sys.path.insert(0, ".")
from blog_auto_post.topics import load_topics, save_topics
IDS = open(sys.argv[1], encoding="utf-8").read().split()
go = "--go" in sys.argv
ts = load_topics()
json.dump(ts, open("data/topics_backup_before_q9_hold2_1109.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
hit = [t for t in ts if t.get("id") in IDS]
for t in hit:
    print(t["id"], "hold=", t.get("hold"), "used=", t.get("used"), "until=", t.get("hold_until"))
print("見つかった", len(hit), "/", len(IDS), "全体", len(ts))
miss = set(IDS) - {t["id"] for t in hit}
if miss: print("無い:", miss)
bad = [t["id"] for t in hit if t.get("used") or not t.get("hold")]
if bad: print("hold でない/使用済み(消さない):", bad)
if go:
    keep = [t for t in ts if not (t.get("id") in IDS and t["id"] not in bad)]
    save_topics(keep)
    after = load_topics()
    print("削除後", len(after), "残っている対象", [t["id"] for t in after if t.get("id") in IDS])
