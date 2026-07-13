"""比較表(HTML)・免責文言の組み立て(通信費比較向け)。

料金・データ容量等の実データはLLMに生成させず、`plans.json`(plans_client経由)から
読み込んだ値をそのままコードで整形する(ハルシネーション防止・数値の正確性担保のため)。
LLMにはこの完成済みHTMLブロックを記事内の適切な位置に挿入させる形で連携する
(Dragon/Angelの `table_builder.py` と同じ設計思想。画像・レビュー件数等が存在しない代わりに、
データ容量・円/GB単価・出典/取得日といった通信プラン特有の項目に差し替えている)。
"""
from __future__ import annotations

from html import escape
from typing import Any

PLAN_TABLE_PLACEHOLDER = "<!--PLAN_TABLE-->"


def build_comparison_table_html(plans: list[dict[str, Any]]) -> str:
    """プラン一覧から比較表HTMLを生成する。"""
    rows = []
    for p in plans:
        provider = escape(p.get("provider", ""))
        plan_name = escape(p.get("plan_name", ""))
        price = p.get("monthly_price_yen")
        price_text = f"¥{price:,}/月" if price else "料金情報なし"
        data_cap = p.get("data_capacity_gb")
        data_text = f"{data_cap}GB" if data_cap else "無制限/固定回線"
        cost_per_gb = p.get("cost_per_gb_yen")
        cost_per_gb_text = f"¥{cost_per_gb:,.1f}/GB" if cost_per_gb else "-"
        value_score = p.get("value_score", "-")
        judgment = escape(str(p.get("judgment", "-")))
        source_url = escape(p.get("source_url", ""))
        fetched_at = escape(p.get("fetched_at", ""))

        rows.append(
            "<tr>"
            f"<td>{provider}<br><small>{plan_name}</small></td>"
            f"<td>{price_text}</td>"
            f"<td>{data_text}</td>"
            f"<td>{cost_per_gb_text}</td>"
            f"<td>{value_score} / 100<br><strong>{judgment}</strong></td>"
            f'<td><a href="{source_url}" target="_blank" rel="nofollow noopener">公式サイトで見る</a>'
            f"<br><small>{fetched_at}時点</small></td>"
            "</tr>"
        )

    table_html = (
        '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;">'
        "<thead><tr>"
        "<th>事業者/プラン</th><th>月額料金</th><th>データ容量</th><th>円/GB単価</th>"
        "<th>お得度スコア</th><th>出典</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )
    return table_html


def build_disclaimer_html(plans: list[dict[str, Any]]) -> str:
    """料金・データ容量情報の取得日時の明記(鮮度表記) + アフィリエイト開示文(景品表示法対応)。

    Dragon/Angelは商品検索APIのリアルタイム性があるため取得日時のみの単純な文言だったが、
    Demonはキュレーション型DB(plans.json、hishoによる月1回程度の定期リサーチで更新)を
    使うためリアルタイム性が無い。developer/tasks.md記載の通り「鮮度表記の重要性が
    Dragon/Angelより高い」ため、比較対象プランそれぞれの `fetched_at` を集約して
    文言に埋め込む。
    """
    fetched_dates = sorted({p.get("fetched_at", "") for p in plans if p.get("fetched_at")})
    if len(fetched_dates) == 1:
        fetched_text = fetched_dates[0]
    elif fetched_dates:
        fetched_text = f"{fetched_dates[0]}〜{fetched_dates[-1]}"
    else:
        fetched_text = "不明"

    return (
        "<hr>"
        '<p style="font-size:0.85em;color:#666;">'
        f"※本記事の料金・データ容量等の情報は、各社公式サイトを{escape(fetched_text)}時点で"
        "確認した内容に基づきます。通信プランの料金・データ容量・割引条件等は予告なく変更される"
        "場合があるため、お申し込み前に必ず各社公式サイトで最新情報をご確認ください。"
        "また、比較表中の一部プランの表示価格は、セット割引等の適用前の基本料金です"
        "(適用可能な割引の詳細は各社公式サイトでご確認ください)。<br>"
        "本記事はA8.net等のアフィリエイトプログラムの利用を予定しており、記事内リンクを"
        "経由してお申し込みされた場合、当サイトが紹介料を受け取ることがあります"
        "(2026年7月時点、A8.net未提携)。"
        "</p>"
    )
