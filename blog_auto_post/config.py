"""環境変数からの設定読み込み。

認証情報・秘密情報はすべてここを経由して環境変数から取得する。
コード中にAPIキー等を直接書き込むことは禁止(README参照)。

Dragon(app/blog_auto_post/config.py)・Angel(angel/app/blog_auto_post/config.py)とほぼ
同一構造だが、データソースAPI(楽天/Yahoo)のクライアントIDが不要な点(plans.jsonをローカル
参照するだけのため)が異なる。

アフィリエイト(バリューコマース)のsid・pidは`blog_auto_post/affiliate.py`にハードコードして
いる(トリファ・airalo・Saily 3社と即時提携済みで、pidは秘密情報ではなく固定のreferralリンク
識別子のため、環境変数化はせず他部署のAPIキー等と区別している)。旧版(通信費比較)で使っていた
A8_AFFILIATE_ID(未提携プレースホルダー)は本リニューアルで廃止した。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# ローカル実行時は .env を読み込む(GitHub Actionsではリポジトリ Secrets が
# 環境変数として直接注入されるため python-dotenv は無くても動作する)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv未インストールでも動作継続
    pass


class ConfigError(RuntimeError):
    """必須環境変数が不足している場合に送出する例外。"""


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    claude_model: str

    hatena_id: str
    hatena_blog_domain: str
    hatena_api_key: str


REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "HATENA_ID",
    "HATENA_BLOG_DOMAIN",
    "HATENA_API_KEY",
]


def load_settings() -> Settings:
    """環境変数からSettingsを組み立てる。不足があればConfigErrorを送出する。"""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise ConfigError(
            "以下の環境変数が設定されていません: "
            + ", ".join(missing)
            + " (.env または GitHub Secrets を確認してください。詳細は app/README.md 参照)"
        )

    return Settings(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
        hatena_id=os.environ["HATENA_ID"],
        hatena_blog_domain=os.environ["HATENA_BLOG_DOMAIN"],
        hatena_api_key=os.environ["HATENA_API_KEY"],
    )
