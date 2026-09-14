# -*- coding: utf-8 -*-
"""2026-09-15: GitHub Actions(Claude APIクレジット)から、このPCの予定タスクへ移した起動口。
.env を読み込み、ANTHROPIC_API_KEY は消してから本体を動かす(文章は sa_llm.py で Max→Gemini 3 Flash)。
使い方: python run_local_post.py [main.py | last_minute_hotel_navi_main.py]"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
except ImportError:
    with open(os.path.join(HERE, ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.pop("ANTHROPIC_API_KEY", None)
script = sys.argv[1] if len(sys.argv) > 1 else "main.py"
if script.startswith("last_minute_hotel_navi"):
    os.environ.setdefault("HOTEL_NAVI_CONTENT_TYPE", "discovery")  # 08-31社長承認の穴場・発見型
sys.argv = [script]
runpy.run_path(script, run_name="__main__")
