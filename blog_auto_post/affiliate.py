"""A8.net アフィリエイトURL変換(未提携、プレースホルダー)。

現時点(2026-07-13)ではA8.netへのサイト登録・広告主(各通信キャリア・MVNO事業者)提携審査が
未着手のため、`A8_AFFILIATE_ID` は環境変数未設定(空文字)で運用する。未設定の間は
公式サイトの通常URL(`plans.json` の `source_url`)のままリンクを張り、提携完了後に
この関数の中身を実際のリンク変換ロジック(A8.netの成果報酬URL形式)へ差し替える。

Angel(`angel/app/blog_auto_post/affiliate.py`、バリューコマース版)の設計を踏襲:
未提携の間は誤ったURL形式を生成してリンク切れ・機会損失を招くより、プレースホルダーとして
通常URLをそのまま返す方が安全という判断。

**要調査(A8.net審査通過後に対応)**: A8.netの広告主ごとに発行される実際のアフィリエイト
リンク形式(A8.net管理画面の「プログラム検索」で提携 → 「広告リンク作成」で発行される
リンクタグの実物)は現時点では未確認。審査通過時に秘書へ確認を依頼し、
`to_affiliate_url()` の中身を実装する。
"""
from __future__ import annotations


def to_affiliate_url(raw_url: str, affiliate_id: str = "") -> str:
    """公式サイトURLをA8.netアフィリエイトURLへ変換する。

    `affiliate_id` が空文字の間(ASP未提携)は `raw_url` をそのまま返す。
    提携後は環境変数 `A8_AFFILIATE_ID` を設定するだけで、新規記事から自動的に
    アフィリエイトURL化される想定(過去記事の遡及更新は別途バッチが必要)。
    """
    if not affiliate_id:
        return raw_url

    # TODO(A8.net審査通過後): 実際のリンク変換ロジックに置き換える。
    # 現時点ではプレースホルダーとして raw_url をそのまま返す(誤ったURL形式を生成して
    # リンク切れ・機会損失を招くより、未実装のまま通常URLを使い続ける方が安全なため)。
    print(
        "[affiliate] 警告: A8_AFFILIATE_ID が設定されていますが、"
        "to_affiliate_url() は未実装のプレースホルダーです。通常URLのまま返却します。"
    )
    return raw_url
