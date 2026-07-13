"""バリューコマース アフィリエイトURL変換(海外eSIM比較「海外SIM・eSIM比較ガイド」向け)。

トリファ・airalo・Saily の3社はいずれもバリューコマース経由で**即時提携済み**(2026-07-13)。
`demon/Simmemo_valuecommerce_pid.txt` に記載の sid・サービスごとの pid を使い、
テキストリンク形式のreferral URL(`https://ck.jp.ap.valuecommerce.com/servlet/referral?
sid={sid}&pid={pid}`)をそのまま構築する(バナー画像タグは不要、テキストリンクで十分との
案内済み)。

Angel(`angel/app/blog_auto_post/affiliate.py`、バリューコマース版・審査待ちプレースホルダー)
とは異なり、Demonは既に3社とも提携済みのため即座に実リンクを返す実装になっている点が異なる。

**重要**: バリューコマースのreferralリンクは商品ページ単位のディープリンクではなく、
広告主(サービス)ごとに固定のリンクであるため、`raw_url`(公式サイトの個別ページURL)は
リンク変換には使用しない(pidが特定できないサービスの場合のみ、フォールバックとして
`raw_url` をそのまま返す)。
"""
from __future__ import annotations

VC_SID = "3775807"

# demon/Simmemo_valuecommerce_pid.txt に記載のpidをそのまま使用。
VC_PID_MAP: dict[str, str] = {
    "トリファ": "892657918",
    "airalo": "892657920",
    "Saily": "892657921",
}


def to_affiliate_url(service_name: str, raw_url: str = "") -> str:
    """サービス名からバリューコマースのreferralリンクを構築する。

    `service_name` が VC_PID_MAP に無い(=未提携)場合は `raw_url` をそのまま返す
    (誤ったURL形式を生成してリンク切れ・機会損失を招くより安全なため)。
    """
    pid = VC_PID_MAP.get(service_name)
    if not pid:
        return raw_url

    return f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid={VC_SID}&pid={pid}"
