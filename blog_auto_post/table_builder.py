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

import re
import zlib
from html import escape
from typing import Any

from .affiliate import to_affiliate_url

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


# ---------------------------------------------------------------------------
# 【2026-10-17】社長「1A 2A 3A 4A。URLも最後だけでなく最初と中当たりにも」
# - 1A: 提携リンクを冒頭(公式ページの案内箱)・本文の中ほど・末尾の3か所に置く
# - 4A: 比較表にグローバルWiFi(レンタルWiFi)の行を足す/airaloは「WEB(ブラウザ)から購入」を明記
#       (airaloはアプリ経由の注文だと紹介料の対象外のため。読者向けには「アプリ不要」として案内する)
# - 3A: 手順系(ガイド)記事の末尾に、購入前の比較・選び方の記事への「次に読む」を置く(同ブログ内のみ)
# 料金・容量などの数値はここには一切書かない(数値は plans.json 由来の比較表だけ)。
# 既存記事の一括修正(ai-company/scheduled/demon_links/convert.py)も同じ関数を使う。
# 各ブロックはコメントの目印で二重挿入を防ぐ。
# ---------------------------------------------------------------------------
CTA_TOP_MARK = "<!-- demon-cta:top -->"
CTA_MID_MARK = "<!-- demon-cta:mid -->"
CTA_END_MARK = "<!-- demon-cta:end -->"
NEXT_READ_MARK = "<!-- demon-next-read -->"
WIFI_ROW_MARK = "<!-- demon-wifi-row -->"

AIRALO_WEB_NOTE = "アプリを入れなくても、公式のWEBサイト(ブラウザ)から購入できます"


def _aff_link(service_name: str, label: str | None = None) -> str:
    url = to_affiliate_url(service_name)
    return (
        f'<a href="{escape(url)}" target="_blank" rel="nofollow noopener sponsored">'
        f"{escape(label or service_name)}</a>"
    )


def build_top_cta_html() -> str:
    """冒頭(最初の見出しの前)に置く、公式ページの案内箱。"""
    return (
        f"{CTA_TOP_MARK}"
        '<div style="margin:1.2em 0;padding:0.8em 1em;border:1px solid #cfd8dc;border-radius:4px;background:#f7fafc;">'
        '<p style="font-weight:bold;margin:0 0 0.4em;">先に公式ページを見ておきたい方へ</p>'
        '<p style="margin:0;font-size:0.95em;">このブログで比べている海外eSIMは次の2つです。'
        "料金や対応国は変わることがあるので、決める前に公式ページで今の内容を確かめてください。</p>"
        '<ul style="margin:0.4em 0 0;padding-left:1.2em;font-size:0.95em;">'
        f'<li>{_aff_link("airalo")}: {AIRALO_WEB_NOTE}</li>'
        f'<li>{_aff_link("Saily")}: アプリで購入から管理まで行うeSIM</li>'
        "</ul></div>"
    )


def build_mid_cta_html() -> str:
    """本文の中ほど(見出しの区切り)に置く一文。押し売りにならない短さにする。"""
    return (
        f"{CTA_MID_MARK}"
        '<p style="margin:1.5em 0;padding:0.6em 1em;border-left:4px solid #90a4ae;background:#f7fafc;font-size:0.95em;">'
        f"行き先のプランがあるかは、{_aff_link('airalo')}(WEBサイトから購入可)か"
        f"{_aff_link('Saily')}で国名を選ぶと確かめられます。</p>"
    )


def insert_top_cta(html: str) -> str:
    """最初の<h2>の直前に冒頭の案内箱を入れる(見出しが無ければ何もしない)。"""
    if CTA_TOP_MARK in html:
        return html
    i = html.find("<h2")
    if i < 0:
        return html
    return html[:i] + build_top_cta_html() + "\n" + html[i:]


def insert_mid_cta(html: str) -> str:
    """本文の中ほどの<h2>の直前に一文を入れる。

    すでに中ほど(全体の35〜70%)に提携リンク(比較表など)があれば入れない(連打を避ける)。
    候補の見出しは2本目以降で、「よくある質問」「まとめ」の見出しは避ける。
    """
    if CTA_MID_MARK in html:
        return html
    n = len(html)
    if n == 0:
        return html
    for m in re.finditer(r"valuecommerce\.com", html):
        if 0.35 <= m.start() / n <= 0.70:
            return html
    cands = []
    for m in list(re.finditer(r"<h2[\s>]", html))[1:]:
        end = html.find("</h2>", m.start())
        head = re.sub(r"<[^>]+>", "", html[m.start():end if end > 0 else m.start() + 200])
        if any(w in head for w in ("よくある質問", "まとめ", "Q&amp;A", "Q&A")):
            continue
        cands.append(m.start())
    if not cands:
        return html
    pos = min(cands, key=lambda p: abs(p - n / 2))
    return html[:pos] + build_mid_cta_html() + "\n" + html[pos:]


def build_wifi_table_row_html() -> str:
    """比較表に足すグローバルWiFi(レンタルWiFi)の行。料金データを持たないので数値は書かない。"""
    return (
        f"{WIFI_ROW_MARK}<tr>"
        "<td>グローバルWiFi<br><small>海外WiFiレンタル(eSIMではありません)</small></td>"
        "<td>渡航日数に合わせて借りる</td>"
        "<td>プランにより異なる</td>"
        "<td>公式サイトで確認</td>"
        "<td>-</td><td>-</td>"
        "<td>対象外<br><small>端末を借りる方式のため</small></td>"
        f'<td>{_aff_link("グローバルWiFi", "公式サイトで見る")}'
        "<br><small>複数人で使う・eSIM非対応の端末向け</small></td>"
        "</tr>"
    )


def add_wifi_row_to_table(html: str) -> str:
    """比較表(tbody)の最後にグローバルWiFiの行を足す。表が無い・入っていれば何もしない。"""
    if WIFI_ROW_MARK in html:
        return html
    i = html.find("</tbody>")
    if i < 0:
        return html
    return html[:i] + build_wifi_table_row_html() + html[i:]


# 末尾の紹介(収益導線)。比較記事・ガイド記事の両方で使う。
END_SERVICES: list[dict[str, str]] = [
    {"service_name": "airalo", "description": "世界の幅広い国・地域に対応する大手eSIMストア。" + AIRALO_WEB_NOTE},
    {"service_name": "Saily", "description": "Nord Security(NordVPN)系列のeSIMサービス。アプリで購入から管理まで完結する"},
    {"service_name": "グローバルWiFi", "description": "eSIMではなく海外WiFiレンタル。2人以上で通信を分け合う・eSIM非対応の端末を使う場合の選択肢(空港などで受け取り・返却)"},
]


def build_end_services_html(exclude: tuple[str, ...] = ()) -> str:
    """末尾の「主なサービス」箱(eSIM 2社+レンタルWiFi)。exclude に挙げたサービスは並べない。"""
    items_html = "".join(
        '<li style="margin:0.4em 0;">'
        f'{_aff_link(s["service_name"])}: {escape(s["description"])}'
        "</li>"
        for s in END_SERVICES
        if s["service_name"] not in exclude
    )
    return (
        f"{CTA_END_MARK}"
        '<div style="margin:2em 0;padding:1em 1.2em;border:1px solid #ddd;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 0.5em;">この記事に関係する主なサービス(eSIM・レンタルWiFi)</p>'
        '<p style="font-size:0.9em;margin:0 0 0.5em;">実際に申し込む前に、各社の公式サイトで'
        "渡航先のプラン・最新料金をご確認ください。</p>"
        f'<ul style="margin:0;padding-left:1.2em;">{items_html}</ul>'
        "</div>"
    )


def build_next_read_html(links: list[dict[str, str]]) -> str:
    """手順系の記事の末尾に置く「次に読む」(同ブログ内の比較・選び方の記事)。"""
    items_html = "".join(
        f'<li><a href="{escape(link["url"])}">{escape(link["title"])}</a></li>'
        for link in links
        if link.get("url")
    )
    if not items_html:
        return ""
    return (
        f"{NEXT_READ_MARK}"
        '<div style="margin:2em 0;padding:1em 1.2em;border:1px solid #ddd;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 0.5em;">次に読む:これから買う方へ(国別の比較・選び方)</p>'
        f'<ul style="margin:0;padding-left:1.2em;">{items_html}</ul>'
        "</div>"
    )


_COUNTRY_WORDS: dict[str, tuple[str, ...]] = {
    "韓国": ("韓国",),
    "台湾": ("台湾",),
    "アメリカ": ("アメリカ", "米国", "ハワイ"),
    "タイ": ("タイ",),
    "ヨーロッパ": ("ヨーロッパ", "欧州"),
}


def is_buying_guide_title(title: str) -> bool:
    """購入前の読者向け(国別の比較・選び方)の記事か(タイトルで判定)。"""
    return any(w in title for w in ("比較", "選び方", "どっち", "どれが安い"))


def pick_buying_guides(
    entries: list[dict[str, Any]], own_title: str, own_text: str, k: int = 2
) -> list[dict[str, str]]:
    """手順系の記事から誘導する、購入前向けの記事を最大k本選ぶ(同ブログ内のみ)。

    1本目: 本文に国名が2回以上出てくれば、その国の比較記事(新しい順)。無ければ一般的な選び方の記事。
    2本目以降: 比較記事。毎回同じ記事に偏らないよう、自分のタイトルから決まる順番でずらして選ぶ。
    entries は hatena_client.list_entries() の戻り値(新しい順)。
    """
    pool = [
        e for e in entries
        if not e.get("draft") and e.get("url") and e.get("title")
        and e["title"] != own_title and is_buying_guide_title(e["title"])
        and "トリファ" not in e["title"]  # 提携終了のトリファを比べている古い記事へは誘導しない
    ]
    all_country_words = [w for ws in _COUNTRY_WORDS.values() for w in ws]
    general = [e for e in pool if "選び方" in e["title"] and not any(w in e["title"] for w in all_country_words)]
    compare = [e for e in pool if "比較" in e["title"]]
    seed = zlib.crc32(own_title.encode("utf-8"))

    def rotated(lst: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not lst:
            return []
        r = seed % len(lst)
        return lst[r:] + lst[:r]

    counts = {c: sum(own_text.count(w) for w in ws) for c, ws in _COUNTRY_WORDS.items()}
    # 「タイ」は「タイミング」「タイプ」等に含まれるので数え直す
    counts["タイ"] = len(re.findall(r"タイ(?!ミング|プ|ム|トル|ヤ|ル|ト)", own_text))
    best = max(counts, key=lambda c: counts[c])
    picked: list[dict[str, Any]] = []
    if counts[best] >= 2:
        picked += [e for e in compare if any(w in e["title"] for w in _COUNTRY_WORDS[best])][:1]
    picked += rotated(general)[:1]
    for e in rotated(compare):
        if len(picked) >= k:
            break
        if e not in picked:
            picked.append(e)
    return [{"title": e["title"], "url": e["url"]} for e in picked[:k]]
