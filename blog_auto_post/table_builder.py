"""比較表(HTML)・免責文言の組み立て(海外eSIM比較向け)。

価格・データ容量・利用可能日数等の実データはLLMに生成させず、`plans.json`(plans_client経由)
から読み込んだ値をそのままコードで整形する(ハルシネーション防止・数値の正確性担保のため)。
LLMにはこの完成済みHTMLブロックを記事内の適切な位置に挿入させる形で連携する
(Dragon/Angel/旧Demon(通信費比較版)の `table_builder.py` と同じ設計思想。
データ容量・利用可能日数・円/日単価・信頼度に応じた注意書きといった海外eSIM特有の項目に
差し替えている)。

**信頼度の差への対応**: `plans.json` の airalo(30件)は公式サイト直接取得(信頼度high)だが、
トリファ(8件)・Saily(24件)は二次情報源経由での収集のため信頼度lowとしている
(`demon/developer/esim_plans.json` の `_meta.note` 参照)。比較表に信頼度lowのプランが
1件でも含まれる場合、比較表の直後に価格変動リスクを明記した注意書きを必ず挿入する
(社長依頼事項、developer/tasks.md「海外eSIM版へ全面リニューアル」参照)。
"""
from __future__ import annotations

from html import escape
from typing import Any

PLAN_TABLE_PLACEHOLDER = "<!--PLAN_TABLE-->"

# 内部リンク(関連記事)ブロックの冪等マーカー(Dragonのapp/blog_auto_post/table_builder.pyと
# 同一形式。将来update_entry()で記事を再更新する場合に既存ブロックを検出・置換できる)
RELATED_ARTICLES_START = "<!-- related-articles-block:start -->"
RELATED_ARTICLES_END = "<!-- related-articles-block:end -->"


def build_related_articles_html(links: list[dict[str, str]]) -> str:
    """「関連記事」セクションのHTMLを組み立てる(内部リンク自動挿入、2026-08-08〜)。

    2026-08-08(Fable監査・施策4): 孤立ページ解消・クロール導線強化のため、新規記事の
    投稿時に既存記事への内部リンクを自動挿入する。Dragonの内部リンク先行試験
    (apply_internal_links.py、2026-07-19社長判断)と同じ表示ブロック・冪等マーカー形式。
    links: [{"title": str, "url": str}, ...]
    """
    items_html = "".join(
        f'<li><a href="{escape(link["url"])}">{escape(link["title"])}</a></li>'
        for link in links
        if link.get("url")
    )
    if not items_html:
        return ""
    return (
        f"{RELATED_ARTICLES_START}"
        '<div style="margin:2em 0;padding:1em 1.2em;border:1px solid #ddd;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 0.5em;">関連記事</p>'
        f'<ul style="margin:0;padding-left:1.2em;">{items_html}</ul>'
        "</div>"
        f"{RELATED_ARTICLES_END}"
    )


def build_guide_service_links_html(services: list[dict[str, str]]) -> str:
    """ガイド記事末尾の「紹介サービス一覧」(収益導線)HTMLを組み立てる。

    2026-08-08(Fable監査・発見B): article_type=="guide" は plans=[] となり
    to_affiliate_url() の変換ブロックごとスキップされるため、2026-07-22のガイド型
    全面振替以降、Demonの新規記事にはアフィリエイトリンクが1本も存在しなかった
    (=収益経路ゼロの記事だけを生産していた)。ガイド記事の「具体的な料金・数値を
    一切書かない」設計(ハルシネーション対策・plans.json鮮度問題の回避)は維持した
    まま、末尾に3社へのreferralリンクを中立的な紹介形式で置く。

    services: [{"service_name": str, "affiliate_url": str, "description": str}, ...]
    description には料金・数値を含めないこと(ガイド記事の設計原則を守るため)。
    リンクは比較表(build_comparison_table_html)と同じ rel="nofollow noopener sponsored"。
    """
    items_html = "".join(
        '<li style="margin:0.4em 0;">'
        f'<a href="{escape(s["affiliate_url"])}" target="_blank" '
        'rel="nofollow noopener sponsored">'
        f'{escape(s["service_name"])}</a>: {escape(s.get("description", ""))}'
        "</li>"
        for s in services
        if s.get("affiliate_url")
    )
    if not items_html:
        return ""
    return (
        '<div style="margin:2em 0;padding:1em 1.2em;border:1px solid #ddd;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 0.5em;">この記事の内容に対応している主な海外eSIMサービス</p>'
        '<p style="font-size:0.9em;margin:0 0 0.5em;">実際にeSIMを使ってみる場合は、以下の各社公式サイト/アプリで'
        "渡航先のプラン・最新料金をご確認ください。</p>"
        f'<ul style="margin:0;padding-left:1.2em;">{items_html}</ul>'
        "</div>"
    )

# 【2026-08-20】トリファはバリューコマース提携終了(2026-08-25)のため今後の新規記事対象外
# (affiliate.py参照)。このセットはコード内で未参照だが、履歴として残す。
LOW_RELIABILITY_SERVICES = {"Saily"}


def _data_label(p: dict[str, Any]) -> str:
    if p.get("is_unlimited"):
        note = p.get("unlimited_note")
        return f"無制限({escape(note)})" if note else "無制限"
    gb = p.get("data_capacity_gb")
    return f"{gb}GB" if gb else "-"


def build_comparison_table_html(plans: list[dict[str, Any]]) -> str:
    """プラン一覧から比較表HTML(+信頼度に応じた注意書き)を生成する。"""
    rows = []
    has_low_reliability = False

    for p in plans:
        provider = escape(p.get("service_name", ""))
        destination = escape(p.get("destination", ""))
        days = p.get("days")
        days_text = f"{days}日間" if days else "-"
        data_text = _data_label(p)

        price = p.get("price_yen")
        price_text = f"¥{price:,}" if price else "料金情報なし"
        if p.get("currency") == "JPY" and p.get("price_usd"):
            price_text += f"(参考: ${p['price_usd']})"

        cost_per_day = p.get("cost_per_day_yen")
        cost_per_day_text = f"¥{cost_per_day:,.1f}/日" if cost_per_day else "-"
        cost_per_gb = p.get("cost_per_gb_yen")
        cost_per_gb_text = f"¥{cost_per_gb:,.1f}/GB" if cost_per_gb else "-"

        value_score = p.get("value_score", "-")
        judgment = escape(str(p.get("judgment", "-")))

        official_url = escape(p.get("official_url", ""))
        affiliate_url = escape(p.get("affiliate_url") or p.get("official_url", ""))
        fetched_at = escape(p.get("fetched_at", ""))

        reliability = p.get("reliability", "high")
        if reliability == "low":
            has_low_reliability = True
            reliability_badge = '<br><small style="color:#c0392b;">※要最新確認</small>'
        else:
            reliability_badge = ""

        rows.append(
            "<tr>"
            f"<td>{provider}<br><small>{destination}</small>{reliability_badge}</td>"
            f"<td>{days_text}</td>"
            f"<td>{data_text}</td>"
            f"<td>{price_text}</td>"
            f"<td>{cost_per_day_text}</td>"
            f"<td>{cost_per_gb_text}</td>"
            f"<td>{value_score} / 100<br><strong>{judgment}</strong></td>"
            f'<td><a href="{affiliate_url}" target="_blank" rel="nofollow noopener sponsored">'
            f"公式サイトで見る</a>"
            f"<br><small>{fetched_at}時点</small></td>"
            "</tr>"
        )

    table_html = (
        # 【2026-07-20修正】スマホ幅で全列が無理やり圧縮され、セルが1文字ずつ改行される
        # 問題が実機で見つかった。横スクロール可能なdivで囲み、tableにmin-widthを設定
        # することで、狭い画面では列を圧縮する代わりに横スクロールさせる(Dragon/Angel/
        # hotel_naviと共通の修正)。8列と他より多いため、min-widthも大きめに設定。
        '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">'
        '<table border="1" cellspacing="0" cellpadding="6" '
        'style="border-collapse:collapse;width:100%;min-width:760px;">'
        "<thead><tr>"
        "<th>サービス/渡航先</th><th>利用可能日数</th><th>データ容量</th><th>価格</th>"
        "<th>円/日</th><th>円/GB</th><th>お得度スコア</th><th>公式サイト</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )

    if has_low_reliability:
        # 社長依頼: 信頼度lowのデータ(Saily等)を使う記事では、比較表のすぐ近くに
        # 価格変動リスクの注意書きを明記する。
        table_html += (
            '<p style="background:#fff8e1;border-left:4px solid #f5c542;padding:8px 12px;'
            'font-size:0.9em;margin-top:8px;">'
            "※上記のうち信頼度が低いサービスの料金は、公式サイトへの直接アクセスが難しく"
            "二次情報源を突き合わせて収集したデータです。価格は変動する可能性があるため、"
            "購入前に必ず公式サイト/アプリで最新価格をご確認ください。"
            "</p>"
        )

    return table_html


def build_pr_notice_html() -> str:
    """記事冒頭に置く簡潔な広告表示(景品表示法ステマ規制対応、2026-08-01)。

    末尾のbuild_disclaimer_html()にも開示文はあるが、消費者庁のステマ規制運用基準は
    開示が本文の目立つ位置にあることを重視するため、記事冒頭にも短い【PR】表示を置く。
    """
    return (
        '<p style="font-size:0.95em;color:#444;font-weight:bold;margin:0 0 1.2em;">'
        "【PR】本記事はプロモーションを含みます。"
        "</p>"
    )


def build_disclaimer_html(plans: list[dict[str, Any]]) -> str:
    """料金・データ容量情報の取得日時の明記(鮮度表記) + アフィリエイト開示文(景品表示法対応)。

    海外eSIMは為替・キャンペーン等により価格が比較的頻繁に変動しうるため、Dragon/Angelの
    リアルタイムAPI取得とは異なり「取得日時点の情報である」ことを明記する重要性が高い。
    比較対象プランそれぞれの `fetched_at` を集約して文言に埋め込む。
    """
    fetched_dates = sorted({p.get("fetched_at", "") for p in plans if p.get("fetched_at")})
    if len(fetched_dates) == 1:
        fetched_text = fetched_dates[0]
    elif fetched_dates:
        fetched_text = f"{fetched_dates[0]}〜{fetched_dates[-1]}"
    else:
        fetched_text = "不明"

    has_usd = any(p.get("currency") == "JPY" and p.get("price_usd") for p in plans)
    usd_note = (
        "Sailyの料金はUSD建てのため、記事内の円表示は参考換算(1USD=155円換算)です。"
        "実際の請求額は購入時の為替レート・カード会社の手数料により変動します。<br>"
        if has_usd
        else ""
    )

    return (
        "<hr>"
        '<p style="font-size:0.85em;color:#666;">'
        f"※本記事の料金・データ容量・利用可能日数等の情報は、{escape(fetched_text)}時点で"
        "確認した内容に基づきます。海外eSIMの料金・データ容量・提供条件は為替変動やキャンペーン"
        "等により予告なく変更される場合があるため、お申し込み前に必ず各社公式サイト/アプリで"
        "最新情報をご確認ください。<br>"
        f"{usd_note}"
        "本記事はバリューコマースのアフィリエイトプログラムを利用しており、記事内リンクを"
        "経由してお申し込みされた場合、当サイトが紹介料を受け取ることがあります。"
        "</p>"
    )


def build_guide_disclaimer_html() -> str:
    """非比較型(ガイド)記事向けの免責文言。

    比較表を伴わないためbuild_disclaimer_html()のような料金取得日時の明記は
    不要だが、アフィリエイト開示文言(景品表示法対応)は記事種別によらず必須のため
    共通の一文として切り出す(2026-07-22社長判断、Demon非比較型テンプレ追加分)。
    """
    return (
        "<hr>"
        '<p style="font-size:0.85em;color:#666;">'
        "※本記事は一般的な仕組み・手順の解説であり、特定サービスの料金・提供条件を"
        "保証するものではありません。ご利用前に必ず各社公式サイト/アプリで最新情報を"
        "ご確認ください。<br>"
        "本記事はバリューコマースのアフィリエイトプログラムを利用しており、記事内リンクを"
        "経由してお申し込みされた場合、当サイトが紹介料を受け取ることがあります。"
        "</p>"
    )
