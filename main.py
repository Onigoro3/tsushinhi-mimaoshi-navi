"""完全自動投稿ブログ「通信費見直しナビ」 メイン実行スクリプト。

フロー: トピック選択 -> plans.json(キュレーション型プランDB)から該当プラン情報を取得
        -> 独自スコアリング(お得度判定) -> Claude記事生成(アウトライン/本文/タイトル/自己レビュー)
        -> 比較表HTML + 免責文言(鮮度表記強化)の組み込み -> はてなブログへ公開投稿
        -> トピック使用済みマークの保存

実行方法:
    python main.py

必要な環境変数は README.md 参照(.env または GitHub Secrets から供給)。

Dragon(`app/main.py`, 型落ち家電ラボ・楽天API版)/Angel(`angel/app/main.py`, 型落ちガジェット
比較所・Yahoo API版)とほぼ同一のフロー構成だが、データソースが「商品検索API」ではなく
ローカルの`plans.json`(キュレーション型DB)である点が最大の違い。通信キャリアの料金プランを
横断検索できる公開APIが一般的に存在しないための設計(`demon/developer/tasks.md`
「## データソース設計検討」参照)。API呼び出しが無い分、`plans_client.get_plans_by_ids()` は
例外(IDの不整合)以外は即座に返り、レートリミット・ネットワークエラーハンドリングは不要。

拡張ポイント(将来対応時にコメントを参照):
- エラー通知: 現状はログ出力のみ。Discord Webhook等を追加する場合は
  `notify_failure()` を実装して except節から呼び出す形にする。
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

# Windowsのローカルコンソール(既定cp932)で絵文字を含まない日本語print自体は通常問題ないが、
# 一部の記号(半角カナ由来のマイクロ記号「¥」の一部表現等)でUnicodeEncodeErrorが発生する
# ケースが実機検証(2026-07-13)で確認されたため、標準出力/エラー出力をUTF-8に固定する
# (GitHub Actions実行時(Linux, 既定UTF-8)には影響しない安全な変更)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from blog_auto_post import topics
from blog_auto_post.affiliate import to_affiliate_url
from blog_auto_post.article_pipeline import ArticlePipeline
from blog_auto_post.config import ConfigError, load_settings
from blog_auto_post.hatena_client import HatenaAPIError, post_entry
from blog_auto_post.plans_client import PlanRepositoryError, get_plans_by_ids
from blog_auto_post.scoring import compute_scores
from blog_auto_post.table_builder import (
    PLAN_TABLE_PLACEHOLDER,
    build_comparison_table_html,
    build_disclaimer_html,
)

JST = timezone(timedelta(hours=9))


def notify_failure(stage: str, error: Exception) -> None:
    """失敗時の通知処理。

    現状はGitHub Actionsのログに出力するのみ(要件通りPoCではこれで十分)。
    拡張ポイント: ここでDiscord Webhook(requests.post)等を呼び出せば
    実行失敗を即座に検知できるようになる。
    """
    print(f"::error::[{stage}] 失敗しました: {error}", file=sys.stderr)
    traceback.print_exc()


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        notify_failure("config", e)
        return 1

    # 1. トピック選択 ----------------------------------------------------
    try:
        topic, all_topics = topics.pick_topic()
        print(f"[main] 選定トピック: {topic['title']} (id={topic['id']})")
    except Exception as e:
        notify_failure("topic_selection", e)
        return 1

    # 2. plans.jsonからプラン情報取得(APIではなくローカルJSON参照) -------------
    try:
        plans = get_plans_by_ids(topic["plan_ids"])
        if not plans:
            raise PlanRepositoryError("プランデータが1件も取得できませんでした")
        # A8.net提携後、アフィリエイトURLへ変換(未提携の間はsource_urlのまま)
        for p in plans:
            p["affiliate_url"] = to_affiliate_url(
                p.get("source_url", ""), affiliate_id=settings.a8_affiliate_id
            )
        plan_labels = [f"{p['provider']}「{p['plan_name']}」" for p in plans]
        print(f"[main] plans.jsonからプラン {len(plans)} 件取得: {plan_labels}")
    except Exception as e:  # PlanRepositoryError含む予期せぬ例外も安全に捕捉する
        notify_failure("plans_fetch", e)
        return 1

    # 3. 独自スコアリング(お得度判定) ---------------------------------------
    plans = compute_scores(plans)

    # 4. Claude記事生成 ----------------------------------------------------
    try:
        pipeline = ArticlePipeline(api_key=settings.anthropic_api_key, model=settings.claude_model)
        draft = pipeline.run(topic["title"], topic["category"], plans)
        print(f"[main] 記事生成完了: title={draft.title!r}")
        print(f"[main] 自己レビューメモ: {draft.review_notes}")
    except Exception as e:
        notify_failure("article_generation", e)
        return 1

    # 5. 比較表・免責文言の組み込み ------------------------------------------
    table_html = build_comparison_table_html(plans)
    disclaimer_html = build_disclaimer_html(plans)

    final_html = draft.body_html.replace(PLAN_TABLE_PLACEHOLDER, table_html)
    if draft.meta_description:
        final_html = (
            f'<p style="display:none">{draft.meta_description}</p>\n' + final_html
        )
    final_html += disclaimer_html

    # 6. はてなブログへ投稿(完全自動公開) -----------------------------------
    # 環境変数 DEMON_DRY_RUN=true (または 1/yes) が設定されている場合のみ、実際の投稿を
    # 行わず投稿予定内容を標準出力に表示するだけに留める(2026-07-13 実機検証時に導入。
    # Angelの `ANGEL_DRY_RUN` と同一設計)。未設定(デフォルト)の場合は通常通り
    # post_entry() を実行して本番公開する。
    dry_run = os.environ.get("DEMON_DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    if dry_run:
        dry_run_url = (
            f"https://{settings.hatena_blog_domain}/entry/"
            f"{datetime.now(JST).strftime('%Y/%m/%d/%H%M%S')}"
        )
        print("[main] === DEMON_DRY_RUN=true: post_entry() は実行していません(実際には投稿されません) ===")
        print(f"[main] 投稿予定タイトル: {draft.title!r}")
        print(f"[main] 投稿予定メタディスクリプション: {draft.meta_description!r}")
        print(f"[main] 投稿予定本文冒頭(300文字): {final_html[:300]!r}")
        print(f"[main] 投稿予定URL(推定・実際の値は投稿後に確定): {dry_run_url}")
        print(f"[main] 投稿予定カテゴリ: {[topic['category'], '通信費比較']}")
        print(f"[main] 比較表HTML(検証用、先頭800文字): {table_html[:800]!r}")
        print(f"[main] 免責文言HTML(検証用): {disclaimer_html!r}")
    else:
        try:
            result = post_entry(
                hatena_id=settings.hatena_id,
                blog_domain=settings.hatena_blog_domain,
                api_key=settings.hatena_api_key,
                title=draft.title,
                content_html=final_html,
                categories=[topic["category"], "通信費比較"],
                draft=False,  # 社長方針: 最初から完全自動公開
            )
            print(f"[main] はてなブログ投稿成功: {result.get('location')}")
        except Exception as e:  # HatenaAPIError含む予期せぬ例外も安全に捕捉する
            notify_failure("hatena_post", e)
            return 1

    # 7. トピック使用済みマークの保存 ---------------------------------------
    # (Demonはplans.jsonがAPIではなく静的データのため、Dragon/Angelのような
    #  price_history.py に相当する「毎回のAPIレスポンスの価格スナップショット蓄積」は
    #  行わない。plans.jsonの更新自体はhishoの月次リサーチにより別途行われる。)
    topics.mark_used(topic["id"], all_topics)
    print("[main] トピック使用済みマーク保存 完了")

    return 0


if __name__ == "__main__":
    sys.exit(main())
