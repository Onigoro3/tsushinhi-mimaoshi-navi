"""ローカルの `data/plans.json`(通信プラン キュレーション型DB)からプラン情報を取得する。

Dragon(`rakuten_client.py`)/Angel(`yahoo_client.py`)が担っていた「商品検索APIをリアルタイム
呼び出しする」役割を、Demonでは外部APIではなく**ローカルJSON参照**に置き換えたモジュール。
通信キャリアの料金プランを横断検索できる公開APIが一般的に存在しないため(developer/tasks.md
「## データソース設計検討」参照)、hishoが月1回程度の頻度で公式サイトを再訪して更新する
`plans.json` を、Dragon/Angelにおける「商品検索APIのレスポンス」の代わりとして扱う。

記事生成のたびに外部へ問い合わせるわけではなく、既に構造化済みの静的データをそのまま
読み込むだけであるため、レートリミット・ネットワークエラーハンドリングは不要。
LLMには本モジュールが返す値をそのまま渡し、価格・データ容量等の数値をLLMに生成させる
余地を作らない設計を貫く。

`plans.json` は本来 `demon/developer/plans.json` がマスターデータであり、hishoの定期リサーチ
結果をdeveloperが反映して更新する。本ディレクトリの `data/plans.json` は、Dragon/Angelの
`data/topics.json` 等と同様に「アプリが実行時に参照するデプロイ用コピー」という位置づけ。
マスター更新時は developer が `data/plans.json` へ同期する運用とする(README参照)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PLANS_PATH = Path(__file__).resolve().parent.parent / "data" / "plans.json"


class PlanRepositoryError(RuntimeError):
    pass


def load_plans(path: Path = DEFAULT_PLANS_PATH) -> dict[str, Any]:
    """plans.json全体を読み込む。トップレベルに `plans` 配列があることを検証する。"""
    if not path.exists():
        raise PlanRepositoryError(f"プランデータファイルが見つかりません: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "plans" not in data or not isinstance(data["plans"], list):
        raise PlanRepositoryError(
            "plans.json の形式が不正です(トップレベルに 'plans' 配列が必要です)"
        )
    return data


def get_plans_by_ids(
    plan_ids: list[str], path: Path = DEFAULT_PLANS_PATH
) -> list[dict[str, Any]]:
    """指定された plan_id のリストに対応するプラン情報を、`plan_ids` の順序通りに取得する。

    見つからないIDがあれば例外を送出する(記事内容と実データの不整合を黙って見逃さず、
    明示的にエラーにして早期に気づけるようにするため)。

    返却する各dictは plans.json のレコードをそのままコピーしたもの(呼び出し側で
    スコアリング用フィールド等を追記しても元データを汚さないよう、浅いコピーを返す)。
    """
    data = load_plans(path)
    by_id = {p["id"]: p for p in data["plans"]}

    missing = [pid for pid in plan_ids if pid not in by_id]
    if missing:
        raise PlanRepositoryError(
            f"plans.json に見つからないプランIDがあります: {missing} "
            f"(topics.json の plan_ids と plans.json の id が一致しているか確認してください)"
        )

    return [dict(by_id[pid]) for pid in plan_ids]


def list_all_plans(path: Path = DEFAULT_PLANS_PATH) -> list[dict[str, Any]]:
    """plans.json内の全プランを返す(topics.json作成時の一覧確認等に利用)。"""
    data = load_plans(path)
    return [dict(p) for p in data["plans"]]
