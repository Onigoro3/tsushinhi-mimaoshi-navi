# -*- coding: utf-8 -*-
"""ブログ記事の文章生成の受け口(2026-09-15 社長指示)。

「MAXで書かせて、使えないときはGemini 3 Flashで書かせて」
  1. このPCの Claude Code(Maxプラン、追加課金なし)
  2. 使えなければ Gemini 3 Flash(Google従量課金)
Claude API(クレジット)は使わない。claude を子プロセスで呼ぶときは ANTHROPIC_API_KEY を
環境から外す(入っているとMaxではなくクレジット払いで動くため。09-15に約8ドル無断消費)。

4ブログ(Dragon/Angel/Demon/Venus)とホテル直前予約ナビで同じファイルを使う。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

CLAUDE_MODEL = os.environ.get("SA_BLOG_CLAUDE_MODEL", "sonnet")
GEMINI_MODEL = "gemini-3-flash-preview"
CLAUDE_TIMEOUT = 900
_VIDEO_ENV = r"C:\Users\user\Desktop\launch\ai-company\video\app\.env"
_EMPTY_CWD = os.path.join(os.environ.get("TEMP") or os.path.expanduser("~"), "sa_claude_text_empty")


def _log(msg: str) -> None:
    print(f"[sa_llm] {msg}", file=sys.stderr, flush=True)


def _find_claude() -> str | None:
    cand = os.environ.get("SA_CLAUDE_CLI") or shutil.which("claude")
    if cand:
        return cand
    p = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    return p if os.path.exists(p) else None


def _claude(system: str, user_content: str) -> str:
    cli = _find_claude()
    if not cli:
        raise RuntimeError("claude コマンドが見つかりません")
    os.makedirs(_EMPTY_CWD, exist_ok=True)
    cmd = [cli, "-p", "--model", CLAUDE_MODEL, "--output-format", "json",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", system]
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    proc = subprocess.run(cmd, input=user_content.encode("utf-8"), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=CLAUDE_TIMEOUT, cwd=_EMPTY_CWD, env=env)
    raw = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"claude rc={proc.returncode}: {(raw or proc.stderr.decode('utf-8', 'replace'))[:300]}")
    env_json = json.loads(raw)
    if env_json.get("is_error"):
        raise RuntimeError(f"claude error: {str(env_json)[:300]}")
    text = (env_json.get("result") or "").strip()
    if not text:
        raise RuntimeError("claude が空の応答を返しました")
    return text


def _gemini_key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k and os.path.exists(_VIDEO_ENV):
        with open(_VIDEO_ENV, encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        raise RuntimeError("GEMINI_API_KEY が読めません")
    return k


def _gemini(system: str, user_content: str, max_tokens: int) -> tuple[str, bool]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={_gemini_key()}")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        # 考える分も出力上限に数えられるので、元の上限より広めに取り、考える量は low に抑える(費用も抑える)
        "generationConfig": {"maxOutputTokens": max(max_tokens * 2, 4096),
                             "thinkingConfig": {"thinkingLevel": "low"}},
    }
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode("utf-8"))
            cand = (data.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", [])
                           if not p.get("thought")).strip()
            if not text:
                raise RuntimeError(f"Gemini 空応答: {str(data)[:200]}")
            return text, cand.get("finishReason") == "MAX_TOKENS"
        except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
            last = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Gemini 3回失敗: {last}")


def generate(system: str, user_content: str, max_tokens: int) -> tuple[str, bool]:
    """(本文, 上限で打ち切られたか) を返す。Max → Gemini 3 Flash の順。"""
    if os.environ.get("SA_BLOG_ENGINE", "").lower() != "gemini":
        try:
            t0 = time.time()
            text = _claude(system, user_content)
            _log(f"Max({CLAUDE_MODEL})で生成 {time.time() - t0:.0f}秒 / {len(text)}字")
            return text, False
        except Exception as e:  # noqa: BLE001
            _log(f"Maxが使えないのでGemini 3 Flashへ: {e}")
    text, truncated = _gemini(system, user_content, max_tokens)
    _log(f"Gemini({GEMINI_MODEL})で生成 / {len(text)}字")
    return text, truncated
