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

LOW_RELIABILITY_SERVICES = {"トリファ", "Saily"}


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
        '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;">'
        "<thead><tr>"
        "<th>サービス/渡航先</th><th>利用可能日数</th><th>データ容量</th><th>価格</th>"
        "<th>円/日</th><th>円/GB</th><th>お得度スコア</th><th>公式サイト</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )

    if has_low_reliability:
        # 社長依頼: トリファ・Sailyのデータを使う記事では、比較表のすぐ近くに
        # 価格変動リスクの注意書きを明記する。
        table_html += (
            '<p style="background:#fff8e1;border-left:4px solid #f5c542;padding:8px 12px;'
            'font-size:0.9em;margin-top:8px;">'
            "※上記のうちトリファ・Sailyの料金は、公式サイトへの直接アクセスが難しく"
            "二次情報源を突き合わせて収集したデータです。価格は変動する可能性があるため、"
            "購入前に必ず公式サイト/アプリで最新価格をご確認ください。"
            "</p>"
        )

    return table_html


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
