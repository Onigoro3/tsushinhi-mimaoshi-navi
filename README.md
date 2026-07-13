# Demon部門 完全自動投稿ブログ(通信費見直しナビ)

投稿先ブログ: `https://magicaidemon.hatenablog.com/`(はてなアカウント`MagicaiDemon`は
作成済み。ドメインはサブドメイン名のまま変更せず、ブログの**タイトルだけ**「通信費見直しナビ」に
設定する方針。Dragon「型落ち家電ラボ」もURLは`magicaidrop.hatenablog.com`とブランド名が
一致していない前例を踏襲)

トピック選択 → `plans.json`(キュレーション型プランDB)から該当プランの実データを取得
→ 独自スコアリング(お得度判定) → Claude API(Sonnet 5)で記事生成
(アウトライン → 本文 → タイトル/メタ → 自己レビュー) → はてなブログへ**公開状態で**
自動投稿、までを1回の実行で行うパイプラインです。

Dragon部門(`../../app/`、型落ち家電ラボ・楽天API版)/Angel部門(`../../angel/app/`、
型落ちガジェット比較所・Yahoo API版)の実装を土台にした構成ですが、**データソースが
「商品検索API」ではなくローカルの`plans.json`(キュレーション型DB)である点が最大の違い**です。
通信キャリアの料金プランを横断検索できる公開APIが一般的に存在しないための設計判断です。
経緯は `../developer/tasks.md`「## データソース設計検討 [2026-07-13]」を参照してください。

## 現在のステータス(2026-07-13時点)

**初回本番投稿・GitHubリポジトリ化まで完了。**

- 公開記事(1本目): https://magicaidemon.hatenablog.com/entry/2026/07/13/112529
  (「mineo vs IIJmio徹底比較|料金・容量・お得度で判定」)
- GitHubリポジトリ: https://github.com/Onigoro3/tsushinhi-mimaoshi-navi (public)
- GitHub Actions: 毎日 JST 11:00 自動実行(Dragon JST 9:00・Angel JST 10:00とずらし済み)
- **ブログタイトルの設定は未完了(社長の手動作業が必要)**。理由は下記チェックリスト参照。

詳細は`../developer/tasks.md`「## 初回本番投稿・リポジトリ化 [2026-07-13]」参照。

## 構成

```
demon/app/
├── main.py                     # メイン実行スクリプト(1回分のパイプライン)
├── requirements.txt
├── .env.example                 # ローカル用の環境変数サンプル(値は空)
├── .env                          # 実際の認証情報(Git管理対象外)
├── .gitignore
├── blog_auto_post/
│   ├── config.py                # 環境変数読み込み
│   ├── topics.py                 # トピックキュー管理(Dragon/Angelと無改修で共通ロジック)
│   ├── plans_client.py           # plans.json読み込み + トピックのplan_idsに対応するプラン取得(新規)
│   ├── scoring.py                # 独自スコアリング・お得度判定ロジック(通信プラン向けに新規実装)
│   ├── table_builder.py          # 比較表HTML・免責文言(鮮度表記強化)の組み立て(通信プラン向けに新規実装)
│   ├── article_pipeline.py       # Claude APIによる段階分割の記事生成(通信費比較向け文言)
│   ├── hatena_client.py          # はてなブログAtomPub API連携(Dragon/Angelと無改修で共通)
│   └── affiliate.py              # A8.net アフィリエイトURL変換(現状プレースホルダー)
└── data/
    ├── topics.json               # トピック候補(通信費比較、初期10件、各plans.jsonの実IDを参照)
    └── plans.json                # `demon/developer/plans.json`(マスターデータ)のデプロイ用コピー
```

## データソースについて(Dragon/Angelとの違い)

| 工程 | Dragon(楽天API)/ Angel(Yahoo API) | Demon(本パイプライン) |
|---|---|---|
| データ取得 | 記事生成の都度、外部APIをリアルタイム呼び出し | `plans_client.get_plans_by_ids()` が**ローカルの`data/plans.json`を読み込むだけ**(API呼び出し無し) |
| データ更新 | APIが常に最新値を返すため自動反映 | hishoが月1回程度の頻度で`demon/developer/plans.json`(マスター)を更新し、developerが`demon/app/data/plans.json`(デプロイ用コピー)へ同期する運用 |
| 価格推移履歴 | `price_history.py`で日次スナップショットを蓄積 | 実装なし(plans.jsonは月次更新のため、日次実行で同じ値のスナップショットを蓄積しても価値が薄いため見送り) |

`data/plans.json`はマスターデータ(`demon/developer/plans.json`)のコピーです。マスター更新時は
developer側で本ファイルへの同期作業が必要です(自動同期の仕組みは未実装、今後の拡張ポイント)。

## 必要な環境変数

| 変数名 | 説明 | 現状 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude APIキー | Dragon/Angelと共通のキーを流用済み |
| `CLAUDE_MODEL` | 記事生成モデル(省略時デフォルト `claude-sonnet-5`) | 設定不要 |
| `HATENA_ID` | はてなID | `MagicaiDemon`(作成済み) |
| `HATENA_BLOG_DOMAIN` | ブログドメイン | `magicaidemon.hatenablog.com`(既存のまま) |
| `HATENA_API_KEY` | はてなブログのAtomPub APIキー | `tpwopuucte`(`demon/MagicaiDemon.txt`参照、設定済み) |
| `A8_AFFILIATE_ID` | A8.netのアフィリエイトID(サイトID等) | **未提携**、空文字運用でOK |
| `DEMON_DRY_RUN` | `true`にすると投稿直前で止めて内容を標準出力するのみ | 動作確認時のみ設定(本番は未設定) |

**注意: 実際のAPIキーはコード・READMEに直接書かず、必ず環境変数(`.env`またはGitHub Secrets)経由で渡してください。**

## 社長への依頼事項チェックリスト

以下はコード実装では対応できず、社長ご自身の手作業が必要です。完了/確認出来次第、
developer(私)またはこのリポジトリのGitHub Secretsへ共有してください。

- [ ] **ブログタイトルの設定(手動作業が必要)**: はてなブログAtomPub APIには
      ブログタイトル(デザイン設定)を変更するエンドポイントが存在しないことを
      サービス文書(`GET /atom`)の実機確認で確認済み(Angel部門と同じ制約)。
      はてなブログ管理画面(`magicaidemon.hatenablog.com`)の
      「設定」→「基本設定」→「ブログ名」を、現在のデフォルト値
      「MagicaiDemonのブログ」から「**通信費見直しナビ**」に手動で変更してください
      (ドメイン変更は不要)。
- [ ] **A8.netへのサイト（メディア）登録申請**: 記事が一定本数(目安10本前後、他部署の
      マイルストーンに準ずる)蓄積した時点で申請。通過後、格安SIM・光回線各社の
      アフィリエイトプログラムへ個別申請し、承認された広告主のアフィリエイトID/リンク形式を
      `A8_AFFILIATE_ID`として設定(`affiliate.py`の実装は審査通過後に着手)
- [x] **GitHubリポジトリの新規作成**: 完了。
      https://github.com/Onigoro3/tsushinhi-mimaoshi-navi (public)。
      Secrets(`ANTHROPIC_API_KEY`/`HATENA_ID`/`HATENA_BLOG_DOMAIN`/`HATENA_API_KEY`/
      `A8_AFFILIATE_ID`)登録済み、毎日JST 11:00の自動実行ワークフローも有効化済み。
- [ ] **(参考)plans.jsonの月次更新**: `demon/developer/tasks.md`記載の通り、hishoが
      月1回程度`demon/developer/plans.json`記載9社の公式ページを再訪し、価格改定の
      有無を確認する運用(次回巡回目安2026年8月中旬)。更新があれば
      developerが`demon/app/data/plans.json`へ同期する

## ローカルでのテスト実行方法

1. Python 3.11以上をインストール(依存パッケージは`anthropic`/`requests`/`python-dotenv`。
   本環境ではグローバルにインストール済みのため`pip install`不要だったが、通常は下記手順で導入)
   ```
   cd demon/app
   python -m venv venv
   venv\Scripts\activate        (Windowsの場合)
   pip install -r requirements.txt
   ```
2. `.env.example` を `.env` にコピーし、実際のAPIキーを入力する(既に設定済み)
   ```
   copy .env.example .env
   ```
3. 動作確認(ドライラン、実際には投稿しない)
   ```
   set DEMON_DRY_RUN=true
   python main.py
   ```
   標準出力に選定トピック・取得プラン数・生成タイトル・比較表HTMLの一部・投稿予定URL(推定)が
   表示されます。実際のはてな投稿(`post_entry()`)は行われません。
4. 本番投稿する場合(社長確認後)
   ```
   set DEMON_DRY_RUN=
   python main.py
   ```
   本パイプラインは「完全自動公開」(下書きを経由しない)で実装されているため、
   実行すると即座に本番ブログへ公開される点に注意してください。

   実行のたびに `data/topics.json`(使用済みマーク)が更新されます。

## 既知の制約・注意点(PoCスコープ)

- **A8.net提携未着手**: `affiliate.py`の`to_affiliate_url()`はA8.net提携前提の
  プレースホルダーです。ASP審査通過後、実際のリンク変換ロジックを実装する必要があります。
- **plans.jsonの網羅性**: 現状9社(格安SIM7・光回線2)のみ。楽天モバイルはマーケ方針
  (楽天不使用)により対象外。今後hisho/developerで拡充予定(目標20〜30件、
  `demon/developer/tasks.md`「次のアクション」参照)。
- **GitHub Actions未設定**: Dragon/Angelにある`.github/workflows/daily-post.yml`に相当する
  自動実行ワークフローは本タスクのスコープ外のため未作成。ローカル実行での動作確認まで完了。
- **画像・レビュー無し**: plans.jsonには商品画像・レビュー件数に相当する情報がないため、
  比較表はテキスト中心(料金・データ容量・円/GB単価・お得度スコア・出典)で構成しています。

## コスト目安

Claude Sonnet 5使用、1記事あたり4回のAPI呼び出し(アウトライン/本文/タイトル/自己レビュー)で
約$0.04程度(概算、Dragon/Angelと同水準)。plans.jsonはローカル参照のためAPI利用料は発生しません。
