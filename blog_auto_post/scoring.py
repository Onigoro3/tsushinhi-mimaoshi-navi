"""独自スコアリング・お得度判定ロジック(海外eSIM比較向け)。

`plans.json`記載の実データ(価格・データ容量・利用可能日数)のみから機械的に算出する。
LLMによる主観評価ではなく決定論的な計算式にすることで、記事ごとの再現性・
説明可能性を担保する(Dragon `app/blog_auto_post/scoring.py` / Angel
`angel/app/blog_auto_post/scoring.py` / 旧Demon(通信費比較版)のスコアリング思想を踏襲。
ロジックの中身は海外eSIM特有の指標に合わせて新規実装)。

海外eSIM特有の考え方:
- データ容量が数値で定義されているプラン(1GB/3GB/5GB等の固定容量プラン)は
  「円/GB」(1GBあたりの実質コスト)を軸に、比較対象グループ内での相対的な割安度を評価する。
- 「無制限」(または実質無制限のフェアユース制、例: Saily の「5GB/日高速+以降低速」)プランは
  円/GBという概念が成立しないため、比較対象グループ内での「円/日」(1日あたりの実質コスト)の
  相対的な安さで評価する。
- 固定容量プランと無制限プランが同一トピック内に混在した場合も、本モジュールが自動的に
  2グループへ分割してそれぞれ独立にスコアリングする(異なる評価軸のプランを同一スコアで
  単純比較すると読者に誤解を与えるため)。
- `cost_per_day_yen`(円/日)はスコアリングの主軸に使わないグループ(固定容量プラン)でも
  参考値として全プランに付与する(渡航日数が異なるプラン同士を比較表で見比べる際の目安になるため)。
"""
from __future__ import annotations

from typing import Any

# スコア = グループ内平均に対する割安度(円/GB、または円/日)
# PRICE_RATIO_CAPの倍率お得な時点でスコア満点(100点)とする。
PRICE_RATIO_CAP = 1.5


def _judgment_label(score: float) -> str:
    if score >= 70:
        return "お得"
    if score >= 50:
        return "標準"
    return "割高"


def _score_group(plans: list[dict[str, Any]], use_cost_per_gb: bool) -> None:
    """1グループ(固定容量 or 無制限)内のプランにスコアを付与する(破壊的更新)。"""
    if not plans:
        return

    basis_field = "cost_per_gb_yen" if use_cost_per_gb else "cost_per_day_yen"
    basis_values = [p[basis_field] for p in plans if p.get(basis_field)]
    avg_basis = sum(basis_values) / len(basis_values) if basis_values else 0

    for p in plans:
        basis = p.get(basis_field)
        if avg_basis and basis:
            ratio = avg_basis / basis  # 1より大きいほどグループ平均より割安
            score = min(ratio, PRICE_RATIO_CAP) / PRICE_RATIO_CAP * 100
        else:
            score = 50.0  # データ不足時は中立スコア(お得/割高いずれにも倒さない)
        score = round(score, 1)
        p["value_score"] = score
        p["judgment"] = _judgment_label(score)


def compute_scores(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """各プランに value_score(0-100)・judgment(お得/標準/割高)を付与して返す。

    `cost_per_gb_yen`/`cost_per_day_yen` は plans.json 生成時(demon/developer側の変換処理)に
    既に計算済みの値をそのまま使う(ここで新たに数値を計算し直すことはしない)。
    `data_capacity_gb` の有無(=固定容量プランか無制限プランか)でグループを分け、
    グループごとに独立してスコアリングする。
    """
    if not plans:
        return plans

    fixed_gb_group = [p for p in plans if p.get("data_capacity_gb")]
    unlimited_group = [p for p in plans if not p.get("data_capacity_gb")]

    _score_group(fixed_gb_group, use_cost_per_gb=True)
    _score_group(unlimited_group, use_cost_per_gb=False)

    return plans
