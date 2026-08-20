"""完全自動投稿ブログ「海外SIM・eSIM比較ガイド」 メイン実行スクリプト。

フロー: トピック選択 -> plans.json(キュレーション型プランDB)から該当プラン情報を取得
        -> 独自スコアリング(お得度判定) -> Claude記事生成(アウトライン/本文/タイトル/自己レビュー)
        -> 比較表HTML + 免責文言(鮮度表記強化)の組み込み -> はてなブログへ公開投稿
        -> トピック使用済みマークの保存

実行方法:
    python main.py

必要な環境変数は README.md 参照(.env または GitHub Secrets から供給)。

Dragon(`app/main.py`, 型落ち家電ラボ・楽天API版)/Angel(`angel/app/main.py`, 型落ちガジェット
比較所・Yahoo API版)とほぼ同一のフロー構成だが、データソースが「商品検索API」ではなく
ローカルの`plans.json`(キュレーション型DB)である点が最大の違い。海外eSIM各社(トリファ・
airalo・Saily)を横断検索できる公開APIが一般的に存在しないための設計(`demon/developer/
tasks.md`「## データソース設計検討」参照)。API呼び出しが無い分、`plans_client.get_plans_by_ids()`
は例外(IDの不整合)以外は即座に返り、レートリミット・ネットワークエラーハンドリングは不要。

2026-07-13、社長判断で「通信費比較(格安SIM・光回線)」から「海外旅行用eSIM比較」へ全面
ピボットした(旧版の経緯は`demon/developer/tasks.md`「## データソース設計検討」以下、
新版の経緯は同ファイル「## 海外eSIM版へ全面リニューアル」参照)。アフィリエイトも
A8.net(未提携)からバリューコマース(トリファ・airalo・Saily 3社と即時提携済み)に切り替えた。

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

from blog_auto_post import pexels_client, topics
from blog_auto_post.affiliate import to_affiliate_url
from blog_auto_post.article_pipeline import ArticlePipeline
from blog_auto_post.config import ConfigError, load_settings
from blog_auto_post.hatena_client import HatenaAPIError, list_entries, post_entry
from blog_auto_post.image_enrichment import insert_eyecatch, insert_theme_image_before_first_h2
from blog_auto_post.plans_client import PlanRepositoryError, get_plans_by_ids
from blog_auto_post.scoring import compute_scores
from blog_auto_post.table_builder import (
    PLAN_TABLE_PLACEHOLDER,
    build_comparison_table_html,
    build_disclaimer_html,
    build_guide_disclaimer_html,
    build_guide_service_links_html,
    build_pr_notice_html,
    build_related_articles_html,
)
from sa_common.production_gate import load_department_index_rate

CATEGORY_ESIM = "海外eSIM比較"

# Pexels検索の対象から除外する渡航先(特定の国・地域を指さない値)
_GENERIC_DESTINATION_LABELS = {"グローバル共通"}

# 非比較型(ガイド)記事向けの画像検索クエリ(渡航先を持たないため固定の汎用クエリを使う)
_GUIDE_IMAGE_QUERIES = ["esim smartphone travel", "airport phone travel"]

# ガイド記事末尾で紹介する提携サービス(バリューコマース即時提携済み、affiliate.VC_PID_MAPと対応)。
# 2026-08-08(Fable監査・発見B): ガイド記事は plans=[] のため収益リンクが1本も入らない
# 問題への対応。説明文には料金・データ容量等の具体的数値を一切書かない(ガイド記事の
# 「数値を書かせない」設計原則=ハルシネーション対策・plans.json鮮度問題の回避を維持)。
# 【2026-08-20】トリファはバリューコマース提携終了(2026-08-25)のため除外(affiliate.py参照)。
_GUIDE_SERVICE_DESCRIPTIONS: dict[str, str] = {
    "airalo": "世界の幅広い国・地域に対応する大手eSIMストア",
    "Saily": "Nord Security(NordVPN)系列のeSIMサービス。アプリで購入から管理まで完結する",
}

JST = timezone(timedelta(hours=9))


def _already_posted_today(all_topics: list, now_jst: datetime) -> bool:
    """本日(JST)分の投稿が既にあるかどうかを判定する。

    2026-07-16、Dragon(app/main.py)でGitHub Actionsのスケジュール実行遅延を
    手動workflow_dispatchで補ったところ、後から遅延していたスケジュール実行も
    発火し、同日に記事が2本投稿される事故が発生した(Angel/Demonでも同日に同型の
    事故が実際に発生していたことを2026-07-17に確認)。再発防止のため、トピックの
    使用済み日時(JST換算)が本日と一致するものが1件でもあれば、それ以降の実行は
    投稿をスキップする。
    """
    today = now_jst.date()
    for t in all_topics:
        used_at = t.get("used_at")
        if not used_at:
            continue
        try:
            used_dt = datetime.fromisoformat(used_at)
        except ValueError:
            continue
        if used_dt.astimezone(JST).date() == today:
            return True
    return False


def notify_failure(stage: str, error: Exception) -> None:
    """失敗時の通知処理。

    現状はGitHub Actionsのログに出力するのみ(要件通りPoCではこれで十分)。
    拡張ポイント: ここでDiscord Webhook(requests.post)等を呼び出せば
    実行失敗を即座に検知できるようになる。
    """
    print(f"::error::[{stage}] 失敗しました: {error}", file=sys.stderr)
    traceback.print_exc()


def _build_internal_links_html(settings, primary_category: str, own_title: str) -> str:
    """同カテゴリの既存記事への内部リンク(最大3本)HTMLを組み立てる。

    2026-08-08(Fable監査・施策4): 孤立ページ解消・クロール導線のため、新規記事の
    末尾(免責文言の直前)に既存記事への内部リンクを自動挿入する。同カテゴリの
    過去記事を優先し、足りなければ他カテゴリの新しい記事で最大3本まで埋める
    (list_entries()ははてなのAtomフィード順=新しい順で返るため、先頭から採るだけで
    新着優先になる)。特にガイド記事→比較記事への導線は、発見B(ガイド記事の収益
    経路ゼロ)対応の一部として、読者を収益導線のある比較記事へ回遊させる役割も持つ。

    記事一覧の取得はGETのみで安全。取得に失敗した場合は空文字を返し、投稿自体は
    必ず継続する(内部リンクは付加要素であり、これを理由に日次投稿を落とさない)。
    """
    try:
        entries = list_entries(
            settings.hatena_id, settings.hatena_blog_domain, settings.hatena_api_key
        )
    except Exception as e:
        print(f"[main] 内部リンク用の既存記事一覧取得に失敗しました(内部リンクなしで投稿を継続): {e}")
        return ""

    candidates = [
        e
        for e in entries
        if not e.get("draft") and e.get("url") and e.get("title") and e["title"] != own_title
    ]
    same_cat = [
        e for e in candidates if primary_category and primary_category in e.get("categories", [])
    ]
    others = [e for e in candidates if e not in same_cat]
    picked = (same_cat + others)[:3]
    if not picked:
        return ""
    print(f"[main] 内部リンクを{len(picked)}本挿入します: {[e['title'] for e in picked]}")
    return build_related_articles_html(
        [{"title": e["title"], "url": e["url"]} for e in picked]
    )


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        notify_failure("config", e)
        return 1

    # 1. トピック選択 ----------------------------------------------------
    # 2026-07-23社長承認(ceo/tasks.md 論点6): 全社共通「量産ゲート」。週次URL
    # Inspection実測のインデックス率をSupabase経由で読み、pick_topic()側で
    # 閾値未満なら記事型を制限する。取得失敗時はNoneのままゲートを効かせない
    # (週次検査未実施時に投稿が止まらないようにするフォールバック)。
    try:
        index_rate = load_department_index_rate("Demon")
    except Exception:
        index_rate = None

    try:
        topic, all_topics = topics.pick_topic(index_rate=index_rate)
    except topics.TopicsExhaustedError as e:
        print(
            f"[main] {e}\n[main] 未使用トピックがないため、本日の投稿をスキップします"
            "(エラーではありません。2026-07-24社長判断論点15③により自動リセットは廃止)。"
        )
        return 0
    except Exception as e:
        notify_failure("topic_selection", e)
        return 1

    now_jst = datetime.now(JST)
    if _already_posted_today(all_topics, now_jst):
        print(
            f"[main] 本日({now_jst:%Y-%m-%d} JST)は既に投稿済みのため、今回の実行はスキップします"
            "(スケジュール遅延と手動実行が重なった場合の二重投稿防止ガード)"
        )
        return 0

    print(f"[main] 選定トピック: {topic['title']} (id={topic['id']})")

    # 2026-07-22社長判断: Demonのインデックス率10%(3社比較テンプレの重複性が濃厚な
    # 原因)への対応として、非比較型(開通手順・端末対応・トラブル対処等)のガイド記事を
    # 導入した。トピックの article_type が "guide" の場合は plans.json 依存の比較表
    # パイプラインを丸ごとスキップし、run_guide() の専用経路を使う(未設定時は従来通り
    # "comparison" として扱うため、既存トピックへの後方互換あり)。
    article_type = topic.get("article_type", "comparison")

    if article_type == "guide":
        plans = []

        # 4. Claude記事生成(非比較型) ---------------------------------------
        try:
            pipeline = ArticlePipeline(api_key=settings.anthropic_api_key, model=settings.claude_model)
            draft = pipeline.run_guide(topic["title"], topic["category"])
            print(f"[main] 記事生成完了(非比較型): title={draft.title!r}")
            print(f"[main] 自己レビューメモ: {draft.review_notes}")
        except Exception as e:
            notify_failure("article_generation", e)
            return 1
    else:
        # 2. plans.jsonからプラン情報取得(APIではなくローカルJSON参照) -------------
        try:
            plans = get_plans_by_ids(topic["plan_ids"])
            if not plans:
                raise PlanRepositoryError("プランデータが1件も取得できませんでした")
            # バリューコマース(トリファ・airalo・Saily 3社と即時提携済み)のreferralリンクへ変換
            for p in plans:
                p["affiliate_url"] = to_affiliate_url(
                    p.get("service_name", ""), raw_url=p.get("official_url", "")
                )
            plan_labels = [
                f"{p['service_name']}「{p['destination']} {p['days']}日間」" for p in plans
            ]
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

    # 5. 画像挿入(渡航先アイキャッチ+テーマ画像、2026-07-20追加) --------------------
    # last_minute_hotel_navi/main.py(Dragonリポジトリ)と同じ設計をDemonへ横展開。
    # ただしDemonのplans.jsonは商品写真を一切持たない静的データのため、Dragon/Angelのように
    # 「既に取得済みの無料画像」は使えない。代わりに渡航先(destination)をPexelsで検索する
    # (hotel_naviの観光名所検索と同じ「地名で検索すればよい」パターン、image_enrichment.py参照)。
    # PEXELS_API_KEY未設定・API障害・翻訳失敗時は例外を出さず本文をそのまま返す設計のため、
    # ここで個別にtry/exceptする必要はない。
    body_with_images = draft.body_html
    if settings.pexels_api_key:
        if article_type == "guide":
            # 渡航先(destination)を持たないため、固定の汎用クエリで画像検索する
            dest_queries = list(_GUIDE_IMAGE_QUERIES)
            alt_text = topic["title"]
        else:
            unique_destinations: list[str] = []
            for p in plans:
                dest = (p.get("destination") or "").strip()
                if dest and dest not in _GENERIC_DESTINATION_LABELS and dest not in unique_destinations:
                    unique_destinations.append(dest)
                if len(unique_destinations) >= 2:
                    break

            dest_queries = (
                pipeline.translate_destination_queries(unique_destinations)
                if unique_destinations
                else []
            )
            alt_text = unique_destinations[0] if unique_destinations else topic["title"]

        photos = [
            pexels_client.search_photo(q, settings.pexels_api_key) for q in dest_queries
        ]
        photos = [p for p in photos if p is not None]

        eyecatch_photo = photos[0] if len(photos) >= 1 else None
        theme_photo = photos[1] if len(photos) >= 2 else eyecatch_photo

        body_with_images = insert_theme_image_before_first_h2(
            body_with_images, theme_photo, alt_text
        )
        # アイキャッチは本文の一番先頭に挿入する(hotel_naviと同じ順序: テーマ画像挿入後に
        # 先頭へ追加。挿入対象が異なる位置のため、どちらを先に行っても結果は変わらない)。
        body_with_images = insert_eyecatch(body_with_images, eyecatch_photo, alt_text)

    # 6. 比較表・免責文言の組み込み ------------------------------------------
    # 非比較型(guide)はplans.jsonを一切使わないため比較表を組み込まず、免責文言も
    # 料金取得日時に触れない汎用版(build_guide_disclaimer_html())を使う。
    if article_type == "guide":
        table_html = ""
        # 2026-08-08(Fable監査・発見B): ガイド記事は plans=[] のため従来は
        # アフィリエイトリンクが1本も入らなかった(2026-07-22のガイド型全面振替以降、
        # 収益経路ゼロの記事だけを生産していた)。ガイド記事の「数値を書かない」設計は
        # 維持したまま、末尾に提携3社のreferralリンクを中立的な紹介形式で追加する。
        guide_service_links_html = build_guide_service_links_html(
            [
                {
                    "service_name": name,
                    "affiliate_url": to_affiliate_url(name),
                    "description": desc,
                }
                for name, desc in _GUIDE_SERVICE_DESCRIPTIONS.items()
            ]
        )
        disclaimer_html = build_guide_disclaimer_html()
    else:
        guide_service_links_html = ""
        table_html = build_comparison_table_html(plans)
        disclaimer_html = build_disclaimer_html(plans)

    # 内部リンク(同カテゴリの過去記事優先、最大3本)を免責文言の直前に挿入する
    # (2026-08-08、Fable監査・施策4。取得失敗時は空文字が返り投稿は継続する)
    internal_links_html = _build_internal_links_html(settings, topic["category"], draft.title)

    final_html = body_with_images.replace(PLAN_TABLE_PLACEHOLDER, table_html)
    final_html = build_pr_notice_html() + final_html
    # 【重要・順序を変えないこと】メタディスクリプションの隠しpタグは必ず本文全体の
    # 「先頭」(【PR】表記・アイキャッチ画像より前)に置く。はてなブログは
    # <meta name="description"> を本文冒頭のテキストから自動生成するため、これが
    # 先頭に無いと検索結果スニペットが本文冒頭の可視テキスト(最悪はPexelsクレジット
    # 「Photo by…」)で汚染される(Dragonの2026-07-29投稿の実HTMLで実害確認、
    # 2026-08-08修正・Fable監査 発見A)。meta_descriptionはarticle_pipeline側の
    # フォールバックにより常に非空が保証されるが、万一空だった場合は警告で検知する。
    if draft.meta_description:
        final_html = (
            f'<p style="display:none">{draft.meta_description}</p>\n' + final_html
        )
    else:
        print(
            "::warning::[main] meta_descriptionが空です(想定外)。検索結果スニペットが"
            "本文冒頭の可視テキストから自動生成されます(article_pipeline.pyのフォールバックを確認)"
        )
    final_html += guide_service_links_html + internal_links_html + disclaimer_html

    # 7. はてなブログへ投稿(完全自動公開) -----------------------------------
    # 環境変数 DEMON_DRY_RUN=true (または 1/yes) が設定されている場合のみ、実際の投稿・
    # topics.jsonへの書き込みの両方を行わず、投稿予定内容を標準出力に表示するだけに
    # 留める(2026-07-13 実機検証時に導入。Angelの `ANGEL_DRY_RUN` と同一設計。
    # 2026-07-15修正: 従来はpost_entry()のみスキップしtopics.mark_used()は無条件実行
    # されていたため、ドライラン実行のたびに本番の使用済みトピックが意図せず書き換わって
    # しまう問題があった。dry_run時は保存処理ごとスキップするよう修正)。
    # 未設定(デフォルト)の場合は通常通りpost_entry()・保存を実行して本番公開する。
    dry_run = os.environ.get("DEMON_DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    if dry_run:
        dry_run_url = (
            f"https://{settings.hatena_blog_domain}/entry/"
            f"{datetime.now(JST).strftime('%Y/%m/%d/%H%M%S')}"
        )
        print("[main] === DEMON_DRY_RUN=true: post_entry()・データ保存は実行していません(本番未反映) ===")
        print(f"[main] 投稿予定タイトル: {draft.title!r}")
        print(f"[main] 投稿予定メタディスクリプション: {draft.meta_description!r}")
        print(f"[main] 投稿予定本文冒頭(300文字): {final_html[:300]!r}")
        print(f"[main] 投稿予定URL(推定・実際の値は投稿後に確定): {dry_run_url}")
        print(f"[main] 投稿予定カテゴリ: {[topic['category'], CATEGORY_ESIM]}")
        print(f"[main] 比較表HTML(検証用、先頭800文字): {table_html[:800]!r}")
        print(f"[main] 免責文言HTML(検証用): {disclaimer_html!r}")
        print(f"[main] ガイド収益導線HTML(検証用): {guide_service_links_html!r}")
        print(f"[main] 内部リンクHTML(検証用): {internal_links_html!r}")
        return 0

    try:
        result = post_entry(
            hatena_id=settings.hatena_id,
            blog_domain=settings.hatena_blog_domain,
            api_key=settings.hatena_api_key,
            title=draft.title,
            content_html=final_html,
            categories=[topic["category"], CATEGORY_ESIM],
            draft=False,  # 社長方針: 最初から完全自動公開
        )
        print(f"[main] はてなブログ投稿成功: {result.get('location')}")
    except Exception as e:  # HatenaAPIError含む予期せぬ例外も安全に捕捉する
        notify_failure("hatena_post", e)
        return 1

    # 8. トピック使用済みマークの保存 ---------------------------------------
    # (Demonはplans.jsonがAPIではなく静的データのため、Dragon/Angelのような
    #  price_history.py に相当する「毎回のAPIレスポンスの価格スナップショット蓄積」は
    #  行わない。plans.jsonの更新自体はhishoの月次リサーチにより別途行われる。)
    topics.mark_used(topic["id"], all_topics)
    print("[main] トピック使用済みマーク保存 完了")

    return 0


if __name__ == "__main__":
    sys.exit(main())
