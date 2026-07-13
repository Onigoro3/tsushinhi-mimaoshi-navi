"""独自スコアリング・お得度判定ロジック(通信費比較向け)。

plans.json記載の実データ(月額料金・データ容量)のみから機械的に算出する。
LLMによる主観評価ではなく決定論的な計算式にすることで、記事ごとの再現性・
説明可能性を担保する(Dragon `blog_auto_post/scoring.py` / Angel
`angel/app/blog_auto_post/scoring.py` のスコアリング思想を踏襲。ロジックの中身は
通信プラン特有の指標に合わせて新規実装)。

通信プラン特有の考え方:
- データ容量が数値で定義されているプラン(格安SIM・オンライン専用ブランド等)は
  「円/GB」(1GBあたりの実質コスト)を軸に、比較対象グループ内での相対的な割安度を評価する。
- データ容量が無制限/固定回線(光回線、`data_capacity_gb` が null)のプランは、円/GBという
  概念が成立しないため、比較対象グループ内での月額料金そのものの相対的な安さのみで評価する。
- モバイル系プランと光回線系プランが同一トピック内に混在した場合も、本モジュールが
  自動的に2グループへ分割してそれぞれ独立にスコアリングする(異なる評価軸のプランを
  同一スコアで単純比較すると読者に誤解を与えるため。基本的にはtopics.json側で
  同一評価軸のプランのみを組み合わせる設計とする)。
"""
from __future__ import annotations

from typing import Any

# スコア = グループ内平均に対する割安度(円/GB、または光回線は月額そのもの)
# PRICE_RATIO_CAPの倍率お得な時点でスコア満点(100点)とする。
PRICE_RATIO_CAP = 1.5


def _judgment_label(score: float) -> str:
    if score >= 70:
        return "お得"
    if score >= 50:
        return "標準"
    return "割高"


def _score_group(plans: list[dict[str, Any]], use_cost_per_gb: bool) -> None:
    """1グループ(モバイル or 光回線)内のプランにスコアを付与する(破壊的更新)。"""
    if not plans:
        return

    if use_cost_per_gb:
        for p in plans:
            gb = p.get("data_capacity_gb")
            price = p.get("monthly_price_yen")
            p["cost_per_gb_yen"] = round(price / gb, 1) if gb and price else None
        basis_values = [p["cost_per_gb_yen"] for p in plans if p.get("cost_per_gb_yen")]
    else:
        for p in plans:
            p["cost_per_gb_yen"] = None
        basis_values = [p["monthly_price_yen"] for p in plans if p.get("monthly_price_yen")]

    avg_basis = sum(basis_values) / len(basis_values) if basis_values else 0

    for p in plans:
        basis = p["cost_per_gb_yen"] if use_cost_per_gb else p.get("monthly_price_yen")
        if avg_basis and basis:
            ratio = avg_basis / basis  # 1より大きいほどグループ平均より割安
            score = min(ratio, PRICE_RATIO_CAP) / PRICE_RATIO_CAP * 100
        else:
            score = 50.0  # データ不足時は中立スコア(お得/割高いずれにも倒さない)
        score = round(score, 1)
        p["value_score"] = score
        p["judgment"] = _judgment_label(score)


def compute_scores(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """各プランに value_score(0-100)・judgment(お得/標準/割高)・cost_per_gb_yen を付与して返す。

    `data_capacity_gb` の有無でグループを分け、グループごとに独立してスコアリングする
    (モバイル定額プランと光回線を同一基準で比較しないため)。
    """
    if not plans:
        return plans

    mobile_group = [p for p in plans if p.get("data_capacity_gb")]
    hikari_group = [p for p in plans if not p.get("data_capacity_gb")]

    _score_group(mobile_group, use_cost_per_gb=True)
    _score_group(hikari_group, use_cost_per_gb=False)

    return plans
