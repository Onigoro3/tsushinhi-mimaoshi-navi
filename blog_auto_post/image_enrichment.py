"""記事への画像挿入(アイキャッチ・渡航先テーマ画像)。

2026-07-20、`last_minute_hotel_navi/image_enrichment.py`(Dragonリポジトリ)で実装・実機検証
した設計をDemon(海外SIM・eSIM比較ガイド)へ横展開したもの。ただしDragon/Angelとは画像ソースが
異なる(重要な設計判断、developer/tasks.md参照):

- Dragon/Angel: 楽天市場APIで既に取得済みの商品画像を無料で使えるため、アイキャッチはそちら。
- **Demon: `plans.json`はキュレーション型の静的データで商品写真を一切持たない。**
  そのため、アイキャッチ・テーマ画像の両方をPexelsの渡航先(destination)検索に頼る設計にした。
  Demonは渡航先をテーマにした記事が多く、hotel_naviの観光名所検索と同じ「地名で検索すれば
  よい」パターンが使えるため相性が良い(`ArticlePipeline.translate_destination_queries()`で
  日本語の渡航先名を英語クエリへ変換してから検索する)。

実際の本番記事(https://magicaidemon.hatenablog.com/entry/2026/07/19/142747 )で確認した通り、
Demonの記事もDragon/Angelと同型のH2構成が続き、hotel_naviのような繰り返し名詞見出し
(<h3>ループ)は存在しない。そのため「イントロ段落の直後・比較の本題(最初のH2)に入る前」に
テーマ画像を1枚挿入する設計にした。

いずれの画像挿入も「取得できなければ何も挿入せず記事本文はそのまま」というフェイルセーフ設計
(既存モジュールと同じ「1箇所の失敗で全体を止めない」方針を踏襲)。

【重要・実機で得た教訓】Pexelsは日本語クエリのままだと無関係な画像がヒットしやすい
(hotel_naviで「新宿御苑」検索が無関係なケーキ写真を返した実例あり。0件でも何らかの写真を
返すフォールバック挙動があるため「ヒットしない」による自動検出もできない)。そのため
Demonでは日本語のままのフォールバック検索は行わず(アイキャッチという目立つ位置に不正確な
写真が出るリスクを避けるため)、翻訳に失敗した場合は画像挿入自体をスキップする、Dragon/Angel
より一段安全側に倒した設計にしている。
"""
from __future__ import annotations

import re
from html import escape

_H2_PATTERN = re.compile(r"<h2[^>]*>", re.IGNORECASE)


def build_pexels_image_html(photo: dict, alt_text: str) -> str:
    """Pexels由来の画像HTML(撮影者クレジット付き)を組み立てる。"""
    return (
        f'<p><img src="{escape(photo["image_url"])}" alt="{escape(alt_text)}" '
        'loading="lazy" style="max-width:100%;height:auto;border-radius:6px;">'
        f'<br><small style="color:#999;">Photo by '
        f'<a href="{escape(photo["photographer_url"])}" target="_blank" rel="nofollow noopener">'
        f'{escape(photo["photographer"])}</a> on '
        f'<a href="{escape(photo["pexels_url"])}" target="_blank" rel="nofollow noopener">Pexels</a>'
        "</small></p>"
    )


def insert_eyecatch(body_html: str, photo: dict | None, alt_text: str) -> str:
    """本文の先頭にPexels由来のアイキャッチ画像を挿入する(取得できなければ本文をそのまま返す)。

    はてなブログは「本文中の最初の画像」を自動でアイキャッチ(記事のサムネイル)に採用する
    仕様のため、本文冒頭に挿入するだけで機能する。
    """
    if photo is None:
        return body_html
    eyecatch_html = build_pexels_image_html(photo, alt_text)
    return eyecatch_html + "\n" + body_html


def insert_theme_image_before_first_h2(body_html: str, photo: dict | None, alt_text: str) -> str:
    """イントロ段落の直後・最初の<h2>見出しの直前に渡航先テーマ画像を1枚挿入する。

    <h2>が本文中に見つからない場合(想定外の出力)は何もせず本文をそのまま返す
    (フェイルセーフ)。
    """
    if photo is None:
        return body_html
    image_html = build_pexels_image_html(photo, alt_text)

    match = _H2_PATTERN.search(body_html)
    if not match:
        return body_html
    idx = match.start()
    return body_html[:idx] + image_html + "\n" + body_html[idx:]
