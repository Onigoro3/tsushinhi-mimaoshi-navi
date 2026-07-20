"""Claude API(Sonnet 5)を使った段階分割の記事生成パイプライン(海外eSIM比較「海外SIM・eSIM比較ガイド」向け)。

①アウトライン生成 → ②本文生成 → ③タイトル/メタディスクリプション生成 → ④自己レビュー
の4段階に分けて呼び出す。`plans.json`(plans_client経由)から取得した実データ(価格・
データ容量・利用可能日数・円/日単価・円/GB単価・お得度スコア)を各プロンプトに埋め込み、
価格等の具体的数値はLLMに創作させず、既存データの参照・言い換えに留めるよう明示的に指示する。

Dragon(`app/blog_auto_post/article_pipeline.py`)・Angel(`angel/app/blog_auto_post/article_pipeline.py`)
と同一の4段階構成・API呼び出しロジックだが、ブログ「海外SIM・eSIM比較ガイド」向けにプロンプト
文言を海外旅行用eSIM比較前提の内容へ差し替えている(海外旅行が好きで、渡航のたびに現地の
通信手段を比較検討してきた実体験を持つ、という人物設定)。

**重要(ハルシネーション対策)**: plans.jsonには価格・データ容量・利用可能日数・回線種別・
出典・信頼度等の客観データのみで構成されている。旧版(通信費比較)と同様に「与えられた数値
以外を絶対に書かない」という制約を強調したプロンプト文言にしている。特にトリファ・Sailyの
プランは信頼度lowとして扱われており、本文中でも断定的な言い切りを避け「公式サイト/アプリで
最新価格をご確認ください」という注意喚起を促すよう指示する。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any

import anthropic

from .table_builder import PLAN_TABLE_PLACEHOLDER

MAX_TOKENS_OUTLINE = 1536
MAX_TOKENS_BODY = 8192
MAX_TOKENS_TITLE = 512
MAX_TOKENS_REVIEW = 8192
MAX_TOKENS_TRANSLATE = 256

FINAL_BODY_MARKER = "### FINAL_BODY"


class TruncatedResponseError(RuntimeError):
    """Claude APIの応答がmax_tokens上限で打ち切られた場合に送出する。"""


@dataclass
class ArticleDraft:
    outline: str
    body_html: str
    title: str
    meta_description: str
    review_notes: str


def _format_plans_for_prompt(plans: list[dict[str, Any]]) -> str:
    lines = []
    for i, p in enumerate(plans, start=1):
        price = f"¥{p['price_yen']:,}" if p.get("price_yen") else "料金不明"
        if p.get("currency") == "JPY" and p.get("price_usd"):
            price += f"(参考: ${p['price_usd']})"
        if p.get("is_unlimited"):
            data_cap = "無制限" + (f"({p['unlimited_note']})" if p.get("unlimited_note") else "")
        else:
            data_cap = f"{p['data_capacity_gb']}GB" if p.get("data_capacity_gb") else "データ容量不明"
        cost_per_day = f"¥{p['cost_per_day_yen']:,}/日" if p.get("cost_per_day_yen") else "(算出不可)"
        cost_per_gb = f"¥{p['cost_per_gb_yen']:,}/GB" if p.get("cost_per_gb_yen") else "(算出不可)"
        reliability_note = (
            "【信頼度: 低(二次情報源経由での収集、要最新確認)】"
            if p.get("reliability") == "low"
            else "【信頼度: 高(公式サイト直接取得)】"
        )
        lines.append(
            f"{i}. サービス: {p.get('service_name', '')} / 渡航先: {p.get('destination', '')}\n"
            f"   利用可能日数: {p.get('days', '-')}日間 / データ容量: {data_cap}\n"
            f"   価格: {price} / 円あたり日数単価: {cost_per_day} / 円あたりGB単価: {cost_per_gb}\n"
            f"   独自お得度スコア: {p.get('value_score', '-')}/100 判定: {p.get('judgment', '-')}\n"
            f"   {reliability_note}\n"
            f"   出典URL: {p.get('source_url', '')}(取得日: {p.get('fetched_at', '')})"
        )
    return "\n".join(lines)


class ArticlePipeline:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _call(
        self,
        system: str,
        user_content: str,
        max_tokens: int,
        raise_on_truncation: bool = False,
    ) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
        if resp.stop_reason == "max_tokens":
            if raise_on_truncation:
                # タイトル生成のように短く構造化された出力を期待する箇所でのみ送出する。
                # 呼び出し側でmax_tokensを引き上げて再試行 or フォールバックする。
                raise TruncatedResponseError(
                    f"応答がmax_tokens={max_tokens}で打ち切られました: {text!r}"
                )
            # 本文・アウトライン・自己レビューのような長文生成では、打ち切られても
            # 例外にしてパイプライン全体を落とす(=その日の投稿がゼロになる)より、
            # 多少短い記事を出す方が安全なため、警告のみ出して打ち切られたテキストを返す。
            print(
                f"::warning::応答がmax_tokens={max_tokens}で打ち切られました(処理は継続)",
                file=sys.stderr,
            )
        return text

    # ------------------------------------------------------------------
    # ① アウトライン生成
    # ------------------------------------------------------------------
    def generate_outline(self, topic_title: str, category: str, plans_text: str) -> str:
        system = (
            "あなたは海外eSIM比較サイト「海外SIM・eSIM比較ガイド」の専門編集者です。"
            "トリファ・airalo・Sailyといった主要eSIMサービスの料金・データ容量・利用可能日数を"
            "渡航先/日数別に横断比較し、読者が『結局どのeSIMを買えば海外旅行で困らず、"
            "かつ損をしないのか』を判断できる記事のアウトラインを作ります。"
            "SEOを強く意識し、読者が実際に検索しそうな悩み・比較観点(料金の安さ、データ容量、"
            "無制限プランの実態、購入・設定のしやすさ等)を見出しに反映させます。"
        )
        user = f"""以下のトピックとプランデータをもとに、記事の見出し構成(アウトライン)を
Markdownの見出しリスト形式で出力してください。各見出しに1〜2行で要点も添えてください。

トピック: {topic_title}
カテゴリ: {category}

プランデータ(plans.json、各社公式サイト/情報源から収集した実データ):
{plans_text}

出力要件:
- 見出しは## から始めるMarkdown形式のみ
- 「各サービスの価格・データ容量・利用可能日数の比較」「円/日で見る実質的なお得度」
  「独自お得度スコアによる判定」「どんな旅行スタイルの人にどのサービスがおすすめか」
  「eSIM購入前によくある疑問・注意点(対応端末、アクティベート方法、無制限プランの実態等)」
  「実際に購入・設定する際のチェックポイント」といった観点を必ず含め、記事のボリュームを確保する
- SEOタイトルで想定される検索意図(例:「{topic_title.split(' ')[0]} eSIM 比較」「海外 eSIM おすすめ」)を
  意識した見出しを2つ以上含める
- プラン比較表を挿入するべき見出しの直後に「(ここに比較表)」と明記する
- 見出しは8〜10個程度(本文を2800字以上に伸ばせるボリューム感にする)
"""
        return self._call(system, user, MAX_TOKENS_OUTLINE)

    # ------------------------------------------------------------------
    # ② 本文生成
    # ------------------------------------------------------------------
    def generate_body(
        self, topic_title: str, category: str, plans_text: str, outline: str
    ) -> str:
        system = (
            "あなたは海外旅行が好きで、渡航のたびに現地の通信手段(eSIM各社)を実際に比較検討して"
            "使い分けてきた実体験を持つ、「海外SIM・eSIM比較ガイド」の専門ライターです。"
            "無機質でテンプレ的な『AIが書いたような』文章ではなく、旅行者目線の具体的な言葉づかい"
            "(例: 「正直〜」「実際に現地で使ってみると」「筆者の感覚では」といった一人称の実感を"
            "伴う言い回し)を随所に混ぜ、血の通った読み物として仕上げてください。"
            "ただし価格・データ容量・利用可能日数等の具体的な数値は、必ずプロンプトで与えられた"
            "データの範囲内でのみ言及し、与えられていない数値(他のプランの価格、通信速度の実測値、"
            "個人の体験談の細部等)や事実を創作してはいけません。海外eSIMの料金誤記は読者の"
            "金銭的な判断ミスや現地での通信トラブルに直結するため、価格に関する記述は特に慎重に、"
            "必ずプランデータに記載された数値のみを使ってください。データにない体験は"
            "「多くの方は〜と感じるようです」のように一般化した表現に留めてください。"
            "また、プランデータの『信頼度: 低』と明記されたサービス(トリファ・Saily)について"
            "言及する際は、断定的な言い切り(例:「必ず○○円です」)を避け、"
            "「執筆時点の情報のため購入前に公式サイト/アプリで最新価格を確認してほしい」という"
            "旨に自然に触れてください。"
            "SEOも強く意識し、想定読者が検索するであろう疑問文・キーワードを自然な文章の中に"
            "繰り返し織り込んでください。"
        )
        user = f"""以下のアウトラインに沿って、記事本文をHTML形式で執筆してください。

トピック: {topic_title}
カテゴリ: {category}

プランデータ(plans.json、各社公式サイト/情報源から収集した実データ。この範囲内の情報のみ本文で言及すること):
{plans_text}

アウトライン:
{outline}

出力要件(文体・トーン):
- 「〜です・ます」調をベースに、時々「〜ですよね」「〜と感じる方も多いはずです」といった
  読者に語りかける表現を混ぜ、機械的な箇条書き偏重ではなく地の文の説明を厚めにする
- 冒頭は「海外旅行前にeSIMを比較したいが、どのサービスが自分の旅程・予算に合うのか分からず
  迷っている読者」の悩みに共感する導入文から始める(例: 「せっかくの海外旅行、現地でのネット環境で
  失敗したくないけど、eSIMの種類が多すぎてどれを選べばいいか分からない、という方へ」等)
- 各セクションの結論だけでなく「なぜそう言えるのか」という理由付け・背景説明を1〜2文加える
- 見出しごとに最低150〜250字程度の説明量を確保し、内容が薄くならないようにする

出力要件(SEO):
- タイトル候補になりうる主要キーワード(渡航先名・「eSIM」「海外 Wi-Fi」「乗り換え」等)を
  本文中に自然な頻度で繰り返し登場させる(不自然な詰め込みは避ける)
- 「{topic_title.split(' ')[0]} eSIM 比較」「海外 eSIM 選び方」等、検索されやすい
  疑問形・比較形の見出し・小見出しを最低2つ含める
- 記事末尾に、読者の疑問に答えるQ&A形式のセクション(3問程度、例: 対応端末の確認方法、
  現地到着後すぐ使えるか、通信量を使い切った場合どうなるか等)を含める

出力要件(技術仕様):
- HTMLタグ(<h2>, <h3>, <p>, <ul><li>, <strong>等)を使い、はてなブログにそのまま貼り付けられる形式にする
- <html>や<body>などの外枠タグは不要。本文の中身のみ出力する
- アウトラインで「(ここに比較表)」と指定された箇所に、プレースホルダー文字列
  `{PLAN_TABLE_PLACEHOLDER}` を単独の行として必ず1箇所挿入する(表自体はこちらでは生成しない)
- サービス名・価格・データ容量・利用可能日数などの具体的な数値は上記データの記載範囲に忠実にする
- 独自お得度スコア・判定(お得/標準/割高)についても触れ、その根拠(円/日単価や円/GB単価の
  グループ内平均との比較から機械的に算出していること)を簡潔に説明する
- 「無制限」表記のプランの一部は実際には1日あたりのデータ量に上限がある(補足事項に記載がある
  範囲で)フェアユース制であることに触れ、誤解を招かないようにする
- 文字数目安は本文全体で3000〜4000字程度(Q&A・まとめ含む)。薄くなるくらいなら具体例を足して伸ばす
- 冒頭に導入文、末尾に「まとめ」の見出しとQ&Aセクションを含める
"""
        body = self._call(system, user, MAX_TOKENS_BODY)
        if PLAN_TABLE_PLACEHOLDER not in body:
            # プレースホルダーが挿入されなかった場合のフォールバック:
            # 本文末尾に追加する
            body = body + f"\n{PLAN_TABLE_PLACEHOLDER}\n"
        return body

    # ------------------------------------------------------------------
    # ③ タイトル/メタディスクリプション生成
    # ------------------------------------------------------------------
    def generate_title_and_meta(self, topic_title: str, body_html: str) -> tuple[str, str]:
        system = (
            "あなたはSEOに強いタイトル・メタディスクリプションの専門家です。"
            "クリックされやすく、かつ内容を誇張しない(実際にない割引額や順位を書かない)"
            "タイトルを作ります。"
        )
        user = f"""以下は記事本文(HTML)です。この記事にふさわしいSEOタイトルと
メタディスクリプションを考えてください。

トピック: {topic_title}

本文:
{body_html[:3000]}

出力形式は厳密に以下の2行のみ(他の説明文は一切出力しないこと):
TITLE: (32文字前後のタイトル)
META: (110〜120文字程度のメタディスクリプション)
"""
        try:
            raw = self._call(system, user, MAX_TOKENS_TITLE, raise_on_truncation=True)
        except TruncatedResponseError:
            # 前置きの説明文等で出力が長くなりmax_tokensで打ち切られたケース。
            # 上限を上げて1回だけ再試行し、それでも打ち切られたらフォールバックへ委ねる。
            try:
                raw = self._call(
                    system, user, MAX_TOKENS_TITLE * 2, raise_on_truncation=True
                )
            except TruncatedResponseError:
                raw = ""

        title = topic_title
        meta = ""
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("TITLE:"):
                title = line[len("TITLE:"):].strip()
            elif line.startswith("META:"):
                meta = line[len("META:"):].strip()

        # タイトル途中切れバグ対策: 極端に短い(=生成途中で切れた)場合はtopic_titleへフォールバック
        if len(title) < 10:
            title = topic_title
        return title, meta

    # ------------------------------------------------------------------
    # ④ 自己レビュー(誤情報・薄い内容チェック)
    # ------------------------------------------------------------------
    def self_review(
        self, topic_title: str, plans_text: str, body_html: str
    ) -> tuple[str, str]:
        system = (
            "あなたは編集責任者として、公開前の記事をレビューする校閲者です。"
            "海外eSIMの料金記事は読者の金銭的判断・現地での通信トラブルに直結するため、"
            "特に厳格にチェックします。"
            "Googleの「Scaled Content Abuse」ポリシー(独自性のない量産的低品質コンテンツへの対策)"
            "も踏まえ、以下の観点をチェックしてください。"
            "1) 与えられたプランデータにない事実(価格・データ容量・利用可能日数・通信速度の実測値・"
            "具体的な個人の体験談の細部)を創作していないか。特に価格・データ容量・日数の数値が"
            "データと完全に一致しているかを最優先で確認する"
            "2) 信頼度lowと明記されたサービス(トリファ・Saily)について、断定的すぎる言い切りに"
            "なっていないか(『必ず○○円』等)。最新確認を促す注意喚起が自然に含まれているか"
            "3) 内容が薄すぎないか(具体性のない一般論だけになっていないか、文字数目安3000〜4000字に"
            "対して極端に短くなっていないか)"
            "4) 読者にとっての実用的な結論(どのサービス・プランを選ぶべきか)が明確か"
            "5) 文体が血の通った読み物になっているか(テンプレ的・機械的な言い回しが目立つ場合は、"
            "旅行者目線の自然な言葉づかいに直す。ただし内容の薄さと違って文体だけを理由に大きく"
            "文字数を削らないこと)"
        )
        user = f"""トピック: {topic_title}

プランデータ(事実確認用):
{plans_text}

レビュー対象の記事本文(HTML):
{body_html}

上記の観点でレビューし、必要なら本文を改善（誤情報の削除・薄い部分の補強・結論の明確化）した上で、
以下の形式で厳密に出力してください(他の文言を前後に含めないこと)。
問題がなければ本文をそのまま「{FINAL_BODY_MARKER}」以降にコピーしてください。

### REVIEW_NOTES
(チェック結果を2〜4行程度の箇条書きで。指摘がなければ「問題なし」とだけ書く)

{FINAL_BODY_MARKER}
(最終版の本文HTML。{PLAN_TABLE_PLACEHOLDER} のプレースホルダー行は必ずそのまま残すこと)
"""
        raw = self._call(system, user, MAX_TOKENS_REVIEW)

        if FINAL_BODY_MARKER in raw:
            notes_part, body_part = raw.split(FINAL_BODY_MARKER, 1)
            notes = notes_part.replace("### REVIEW_NOTES", "").strip()
            final_body = body_part.strip()
        else:
            # マーカーが見つからない場合は安全側に倒し、レビュー前の本文をそのまま使う
            notes = "(レビュー出力のパースに失敗したため、レビュー前の本文をそのまま採用)"
            final_body = body_html

        if PLAN_TABLE_PLACEHOLDER not in final_body:
            final_body = final_body + f"\n{PLAN_TABLE_PLACEHOLDER}\n"

        return final_body, notes

    # ------------------------------------------------------------------
    # 渡航先テーマ画像(Pexels)検索クエリの英語変換
    # ------------------------------------------------------------------
    def translate_destination_queries(self, destinations: list[str]) -> list[str]:
        """渡航先名(日本語、重複除く・最大2件を想定)を、Pexels検索用の英語クエリへ
        最大2つ変換する。

        2026-07-20実機確認(last_minute_hotel_navi/article_pipeline.py.translate_spot_names()と
        同じ教訓): Pexelsは日本語クエリのままだと無関係な画像がヒットしやすい
        (「新宿御苑」検索が無関係なケーキ写真を返した実例あり)一方、英語の正式名称
        ("Taiwan"等)ではほぼ正確にヒットする。

        渡航先が1件しかない場合でも、記事に2枚の異なる写真を挿入できるよう、その国・地域を
        象徴する異なる被写体(都市風景/ランドマーク/食文化等)の英語クエリを2つ生成させる。
        渡航先が2件ある場合は、それぞれ1つずつのクエリを返す。
        「グローバル共通」のような特定の地域を指さない値は呼び出し側でフィルタしてから
        渡すこと(本メソッドでは行わない)。
        """
        if not destinations:
            return []

        system = (
            "あなたは海外旅行系メディアの写真選定担当です。渡航先に関連する実写を"
            "ストックフォト検索サービスで探す際、最もヒットしやすい英語の検索クエリを"
            "考える専門家です。"
        )
        dest_list = "\n".join(f"- {d}" for d in destinations)
        user = f"""以下は海外SIM・eSIM比較記事に関連する渡航先です。

{dest_list}

この記事に挿入する実写(ストックフォト)を検索するための英語クエリを、最大2つ考えて
ください。各クエリは異なる被写体(例: 都市の風景、ランドマーク、食文化、街並みなど)を
表すようにし、Pexelsのようなストックフォトサービスでヒットしやすい一般的な英語表現に
してください(渡航先が1つしかない場合も、必ず異なる視点の2つのクエリを作ること)。

出力形式は厳密に1行1クエリ・最大2行のみ(他の説明文は一切出力しないこと):
(英語クエリ1)
(英語クエリ2)
"""
        try:
            raw = self._call(system, user, MAX_TOKENS_TRANSLATE)
        except Exception:
            # 翻訳に失敗しても記事生成全体は止めない(呼び出し側で画像挿入自体を
            # スキップするだけで継続できる)
            return []

        queries: list[str] = []
        for line in raw.splitlines():
            line = line.strip().strip("`").strip('"').strip()
            line = re.sub(r"^[-\d.、\s]+", "", line).strip()
            if line:
                queries.append(line)
            if len(queries) >= 2:
                break
        return queries

    # ------------------------------------------------------------------
    def run(self, topic_title: str, category: str, plans: list[dict[str, Any]]) -> ArticleDraft:
        plans_text = _format_plans_for_prompt(plans)

        outline = self.generate_outline(topic_title, category, plans_text)
        body = self.generate_body(topic_title, category, plans_text, outline)
        final_body, review_notes = self.self_review(topic_title, plans_text, body)
        # タイトルは自己レビュー後の最終本文を見て決定する(2026-07-15修正: 従来は
        # レビュー前のbodyでタイトルを決めていたため、自己レビューが本文中の誇大表現・
        # データ不整合を修正しても、既に確定したタイトルには反映されず、タイトルと
        # 本文の内容が食い違う実例をドライラン検証(Angelの実際のClaude API呼び出し)
        # で確認したため、呼び出し順序を入れ替えた(3部署共通のロジック修正))
        title, meta = self.generate_title_and_meta(topic_title, final_body)

        return ArticleDraft(
            outline=outline,
            body_html=final_body,
            title=title,
            meta_description=meta,
            review_notes=review_notes,
        )
