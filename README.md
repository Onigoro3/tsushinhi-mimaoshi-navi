# Demon部門 完全自動投稿ブログ(海外SIM・eSIM比較ガイド)

投稿先ブログ: `https://magicaidemon.hatenablog.com/`(はてなアカウント`MagicaiDemon`は
作成済み。ドメインはサブドメイン名のまま変更せず、ブログの**タイトルだけ**「海外SIM・eSIM比較
ガイド」に設定する方針。Dragon「型落ち家電ラボ」もURLは`magicaidrop.hatenablog.com`と
ブランド名が一致していない前例を踏襲)

トピック選択 → `plans.json`(キュレーション型プランDB)から該当プランの実データを取得
→ 独自スコアリング(お得度判定) → Claude API(Sonnet 5)で記事生成
(アウトライン → 本文 → タイトル/メタ → 自己レビュー) → はてなブログへ**公開状態で**
自動投稿、までを1回の実行で行うパイプラインです。

Dragon部門(`../../app/`、型落ち家電ラボ・楽天API版)/Angel部門(`../../angel/app/`、
型落ちガジェット比較所・Yahoo API版)の実装を土台にした構成ですが、**データソースが
「商品検索API」ではなくローカルの`plans.json`(キュレーション型DB)である点が最大の違い**です。
海外eSIM各社(トリファ・airalo・Saily)を横断検索できる公開APIが一般的に存在しないための
設計判断です。経緯は `../developer/tasks.md`「## データソース設計検討 [2026-07-13]」
「## 海外eSIM版へ全面リニューアル [2026-07-13]」を参照してください。

**2026-07-13、社長判断で「通信費比較(格安SIM・光回線)」から「海外旅行用eSIM比較」へ
全面ピボットした。** 既存ブログ・GitHubリポジトリはリブランドして流用し、新規作成は
していない(ブランド名変更は完了、リポジトリ名`tsushinhi-mimaoshi-navi`は歴史的経緯として
そのまま)。

## 現在のステータス(2026-07-13時点、海外eSIM版リニューアル後)

**ブログタイトル・説明文のリブランド完了、パイプライン作り直し完了、ドライラン検証完了。
本番投稿はまだ実施していない。**

- ブログタイトル: 「海外SIM・eSIM比較ガイド」に設定済み(社長により手動変更済み。
  AtomPub `GET /atom` で実機確認、`<atom:title>海外SIM・eSIM比較ガイド</atom:title>`)
- ブログ説明文: 「海外旅行前に、どのeSIMが一番お得か迷ったら。トリファ・airalo・Sailyなど
  主要サービスの料金を渡航先別に比較する、海外SIM・eSIM選びの実践ガイド。」に設定済み
  (同上、AtomPub `GET /atom/entry` のフィード`<subtitle>`で実機確認)
- 旧ジャンル記事(「mineo vs IIJmio徹底比較」)は**削除済み**(AtomPub `DELETE`、
  `../developer/tasks.md`「## 海外eSIM版へ全面リニューアル」参照)
- GitHubリポジトリ: https://github.com/Onigoro3/tsushinhi-mimaoshi-navi (public、名称は歴史的経緯によりそのまま)
- GitHub Actions: 毎日 JST 11:00 自動実行(Dragon JST 9:00・Angel JST 10:00とずらし済み)。
  ワークフロー名は「Daily Auto Post (Demon - 海外SIM・eSIM比較ガイド)」に更新済み

詳細は`../developer/tasks.md`「## 海外eSIM版へ全面リニューアル [2026-07-13]」参照。

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
│   ├── plans_client.py           # plans.json読み込み + トピックのplan_idsに対応するプラン取得
│   ├── scoring.py                # 独自スコアリング・お得度判定ロジック(海外eSIM向けに全面書き直し)
│   ├── table_builder.py          # 比較表HTML・免責文言(鮮度表記+信頼度低サービスの注意書き)の組み立て
│   ├── article_pipeline.py       # Claude APIによる段階分割の記事生成(海外eSIM比較向け文言)
│   ├── hatena_client.py          # はてなブログAtomPub API連携(Dragon/Angelと無改修で共通)
│   └── affiliate.py              # バリューコマース アフィリエイトURL変換(トリファ・airalo・Saily、提携済み)
└── data/
    ├── topics.json               # トピック候補(海外eSIM比較、初期10件、各plans.jsonの実IDを参照)
    └── plans.json                # `demon/developer/esim_plans.json`(秘書調査の生データ)を正規化したもの
```

## データソースについて(Dragon/Angelとの違い)

| 工程 | Dragon(楽天API)/ Angel(Yahoo API) | Demon(本パイプライン) |
|---|---|---|
| データ取得 | 記事生成の都度、外部APIをリアルタイム呼び出し | `plans_client.get_plans_by_ids()` が**ローカルの`data/plans.json`を読み込むだけ**(API呼び出し無し) |
| データ更新 | APIが常に最新値を返すため自動反映 | hishoが定期的に`demon/developer/esim_plans.json`(秘書調査の生データ)を更新し、developerが正規化して`demon/app/data/plans.json`へ反映する運用 |
| 価格推移履歴 | `price_history.py`で日次スナップショットを蓄積 | 実装なし(plans.jsonは低頻度更新のため、日次実行で同じ値のスナップショットを蓄積しても価値が薄いため見送り) |
| データ信頼度 | APIレスポンスは一律で信頼できる | **airalo(30件)は公式サイト直接取得(信頼度high)。トリファ(8件)・Saily(24件)は
二次情報源経由での収集(信頼度low)**。信頼度lowのプランを含む比較表には`table_builder.py`が
自動で価格変動リスクの注意書きを挿入する |

`data/plans.json`は`demon/developer/esim_plans.json`(秘書調査の生データ)を正規化したものです。
マスター更新時はdeveloper側で本ファイルへの反映作業が必要です(自動同期の仕組みは未実装、
今後の拡張ポイント)。

## 必要な環境変数

| 変数名 | 説明 | 現状 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude APIキー | Dragon/Angelと共通のキーを流用済み |
| `CLAUDE_MODEL` | 記事生成モデル(省略時デフォルト `claude-sonnet-5`) | 設定不要 |
| `HATENA_ID` | はてなID | `MagicaiDemon`(作成済み) |
| `HATENA_BLOG_DOMAIN` | ブログドメイン | `magicaidemon.hatenablog.com`(既存のまま) |
| `HATENA_API_KEY` | はてなブログのAtomPub APIキー | `tpwopuucte`(`demon/MagicaiDemon.txt`参照、設定済み) |
| `DEMON_DRY_RUN` | `true`にすると投稿直前で止めて内容を標準出力するのみ | 動作確認時のみ設定(本番は未設定) |

バリューコマースのsid・pid(トリファ/airalo/Saily)は`blog_auto_post/affiliate.py`に
ハードコードしているため、環境変数は不要です(秘密情報ではなく固定のreferralリンク
識別子のため)。旧版(通信費比較)で使っていた`A8_AFFILIATE_ID`は本リニューアルで廃止しました。

**注意: 実際のAPIキーはコード・READMEに直接書かず、必ず環境変数(`.env`またはGitHub Secrets)経由で渡してください。**

## 社長への依頼事項チェックリスト

- [x] **ブログタイトル・説明文の設定(手動作業)**: 完了確認済み。はてなブログAtomPub APIには
      ブログタイトル・説明文を変更するエンドポイントが存在しない(Angel部門と同じ制約)ため
      社長ご自身の手動作業が必要だったが、AtomPub `GET /atom` および `GET /atom/entry` の
      実機確認により、タイトル「海外SIM・eSIM比較ガイド」・説明文
      「海外旅行前に、どのeSIMが一番お得か迷ったら。トリファ・airalo・Sailyなど主要サービスの
      料金を渡航先別に比較する、海外SIM・eSIM選びの実践ガイド。」が既に設定済みであることを
      確認した(2026-07-13)。追加の手動作業は不要。
- [x] **バリューコマース提携**: 完了。トリファ(pid=892657918)・airalo(pid=892657920)・
      Saily(pid=892657921)の3社と即時提携済み(`demon/Simmemo_valuecommerce_pid.txt`)。
      `affiliate.py`に実装済みで、ドライラン検証でも実際のreferralリンクが生成されることを確認した。
- [x] **GitHubリポジトリの新規作成**: 完了。
      https://github.com/Onigoro3/tsushinhi-mimaoshi-navi (public、リポジトリ名は
      通信費比較時代の歴史的経緯によりそのまま)。
      Secrets(`ANTHROPIC_API_KEY`/`HATENA_ID`/`HATENA_BLOG_DOMAIN`/`HATENA_API_KEY`)登録済み、
      毎日JST 11:00の自動実行ワークフローも有効化済み(`A8_AFFILIATE_ID`はリニューアルに伴い
      不要になったため、次回GitHub Secrets更新時に削除して構わない)。
- [ ] **(参考)plans.jsonの更新**: `demon/developer/tasks.md`記載の通り、トリファ・Saily
      (信頼度low)は公式サイトへの直接アクセスができず二次情報源経由での収集のため、
      hishoによる継続的な再確認・更新が望ましい(次回巡回時期は`demon/marketing/tasks.md`の
      申し送り事項を参照)。更新があればdeveloperが`demon/app/data/plans.json`へ反映する。

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

## 既知の制約・注意点

- **トリファ・Sailyのデータ信頼度**: 公式サイトへの直接アクセスができず二次情報源経由での
  収集のため信頼度lowとして扱っている。比較表に含まれる場合は自動で注意書きを挿入する設計
  (`table_builder.py`)だが、根本的な解決にはhishoによる継続的な再確認が必要。
- **plans.jsonの網羅性**: 現状トリファ8件・airalo30件・Saily24件の計62件、渡航先は
  アメリカ/韓国/台湾/ヨーロッパ/タイ(airaloのみ)/グローバル共通(トリファのみ)。
  今後hisho/developerで拡充予定。
- **Saily(USD建て)の円換算**: 参考レート(1USD=155円)で換算した推定値。実際の請求額は
  購入時の為替レート・カード会社手数料により変動する旨を記事内に明記している。
- **画像・レビュー無し**: plans.jsonには商品画像・レビュー件数に相当する情報がないため、
  比較表はテキスト中心(価格・データ容量・利用可能日数・円/日・円/GB・お得度スコア・出典)で
  構成しています。

## コスト目安

Claude Sonnet 5使用、1記事あたり4回のAPI呼び出し(アウトライン/本文/タイトル/自己レビュー)で
約$0.04程度(概算、Dragon/Angelと同水準)。plans.jsonはローカル参照のためAPI利用料は発生しません。
