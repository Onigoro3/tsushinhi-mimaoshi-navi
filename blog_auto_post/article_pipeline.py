"""Claude API(Sonnet 5)を使った段階分割の記事生成パイプライン(通信費比較「通信費見直しナビ」向け)。

①アウトライン生成 → ②本文生成 → ③タイトル/メタディスクリプション生成 → ④自己レビュー
の4段階に分けて呼び出す。`plans.json`(plans_client経由)から取得した実データ(月額料金・
データ容量・円/GB単価・お得度スコア)を各プロンプトに埋め込み、価格等の具体的数値は
LLMに創作させず、既存データの参照・言い換えに留めるよう明示的に指示する。

Dragon(`app/blog_auto_post/article_pipeline.py`)・Angel(`angel/app/blog_auto_post/article_pipeline.py`)
と同一の4段階構成・API呼び出しロジックだが、ブログ「通信費見直しナビ」向けにプロンプト文言を
格安SIM・光回線等の通信費比較前提の内容へ差し替えている(元携帯ショップ店員かつ自身も
複数回SIM・回線を乗り換えてきた実体験を持つ、という人物設定)。

**重要(ハルシネーション対策)**: plans.jsonにはレビュー件数・画像等は存在せず、料金・
データ容量・回線種別・出典等の客観データのみで構成されている。Dragon/Angelよりもさらに
「与えられた数値以外を絶対に書かない」という制約を強調したプロンプト文言にしている
(通信プランの料金誤記は読者の金銭的損失に直結するため慎重を期す)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anthropic

from .table_builder import PLAN_TABLE_PLACEHOLDER

MAX_TOKENS_OUTLINE = 1536
MAX_TOKENS_BODY = 8192
MAX_TOKENS_TITLE = 512
MAX_TOKENS_REVIEW = 8192

FINAL_BODY_MARKER = "### FINAL_BODY"


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
        price = f"¥{p['monthly_price_yen']:,}/月" if p.get("monthly_price_yen") else "料金不明"
        data_cap = (
            f"{p['data_capacity_gb']}GB" if p.get("data_capacity_gb") else "無制限/固定回線(データ容量の概念なし)"
        )
        cost_per_gb = f"¥{p['cost_per_gb_yen']:,}/GB" if p.get("cost_per_gb_yen") else "(算出不可)"
        lines.append(
            f"{i}. 事業者: {p.get('provider', '')} / プラン名: {p.get('plan_name', '')}\n"
            f"   回線: {p.get('network', '-')} / プラン種別: {p.get('plan_type', '-')}\n"
            f"   月額料金: {price} / データ容量: {data_cap} / 円あたりGB単価: {cost_per_gb}\n"
            f"   独自お得度スコア: {p.get('value_score', '-')}/100 判定: {p.get('judgment', '-')}\n"
            f"   補足事項: {p.get('notes', '')}\n"
            f"   出典URL: {p.get('source_url', '')}(取得日: {p.get('fetched_at', '')})"
        )
    return "\n".join(lines)


class ArticlePipeline:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _call(self, system: str, user_content: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()

    # ------------------------------------------------------------------
    # ① アウトライン生成
    # ------------------------------------------------------------------
    def generate_outline(self, topic_title: str, category: str, plans_text: str) -> str:
        system = (
            "あなたは通信費比較サイト「通信費見直しナビ」の専門編集者です。格安SIM・"
            "オンライン専用ブランド(ahamo/LINEMO等)・キャリアサブブランド(UQ mobile/"
            "ワイモバイル等)・光回線の料金プランを横断的に比較し、読者が『結局どれに"
            "乗り換えれば通信費が下がるのか』を判断できる記事のアウトラインを作ります。"
            "SEOを強く意識し、読者が実際に検索しそうな悩み・比較観点(料金の安さ、データ容量、"
            "セット割引、乗り換えの手間等)を見出しに反映させます。"
        )
        user = f"""以下のトピックとプランデータをもとに、記事の見出し構成(アウトライン)を
Markdownの見出しリスト形式で出力してください。各見出しに1〜2行で要点も添えてください。

トピック: {topic_title}
カテゴリ: {category}

プランデータ(plans.json、公式サイトから収集した実データ):
{plans_text}

出力要件:
- 見出しは## から始めるMarkdown形式のみ
- 「各プランの月額料金・データ容量の比較」「円/GB単価で見る実質的なお得度」
  「独自お得度スコアによる判定」「どんな人にどのプランがおすすめか」
  「乗り換え前によくある疑問・注意点(セット割引・契約期間等)」
  「実際に乗り換える際のチェックポイント」といった観点を必ず含め、記事のボリュームを確保する
- SEOタイトルで想定される検索意図(例:「{topic_title.split(' ')[0]} 比較」「格安SIM 乗り換え 損しない」)を
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
            "あなたは元携帯ショップ店員としての接客経験があり、自分自身も格安SIM・"
            "オンライン専用ブランド・光回線を何度も比較検討して乗り換えてきた実体験を持つ、"
            "「通信費見直しナビ」の専門ライターです。"
            "無機質でテンプレ的な『AIが書いたような』文章ではなく、生活者目線の具体的な言葉づかい"
            "(例: 「正直〜」「実際に乗り換えを検討すると」「筆者の感覚では」といった一人称の実感を"
            "伴う言い回し)を随所に混ぜ、血の通った読み物として仕上げてください。"
            "ただし料金・データ容量等の具体的な数値は、必ずプロンプトで与えられたデータの範囲内で"
            "のみ言及し、与えられていない数値(他のプランの価格、割引額の具体的な数字、キャンペーン"
            "詳細等)や個人の体験談の細部(具体的な日付や個人の生活描写等)を事実として創作しては"
            "いけません。通信プランの料金誤記は読者の金銭的な判断ミスに直結するため、価格に関する"
            "記述は特に慎重に、必ずプランデータに記載された数値のみを使ってください。データにない"
            "体験は「多くの方は〜と感じるようです」のように一般化した表現に留めてください。"
            "SEOも強く意識し、想定読者が検索するであろう疑問文・キーワードを自然な文章の中に"
            "繰り返し織り込んでください。"
        )
        user = f"""以下のアウトラインに沿って、記事本文をHTML形式で執筆してください。

トピック: {topic_title}
カテゴリ: {category}

プランデータ(plans.json、公式サイトから収集した実データ。この範囲内の情報のみ本文で言及すること):
{plans_text}

アウトライン:
{outline}

出力要件(文体・トーン):
- 「〜です・ます」調をベースに、時々「〜ですよね」「〜と感じる方も多いはずです」といった
  読者に語りかける表現を混ぜ、機械的な箇条書き偏重ではなく地の文の説明を厚めにする
- 冒頭は「通信費を見直したいけど、どのプランが本当にお得なのか分からず迷っている読者」の
  悩みに共感する導入文から始める(例: 「毎月のスマホ代、なんとなく高い気がするけど
  乗り換えの手間を考えると踏み切れない、という方へ」等)
- 各セクションの結論だけでなく「なぜそう言えるのか」という理由付け・背景説明を1〜2文加える
- 見出しごとに最低150〜250字程度の説明量を確保し、内容が薄くならないようにする

出力要件(SEO):
- タイトル候補になりうる主要キーワード(プラン名・「通信費」「格安SIM」「乗り換え」等)を
  本文中に自然な頻度で繰り返し登場させる(不自然な詰め込みは避ける)
- 「{topic_title.split(' ')[0]} 比較」「格安SIM 乗り換え 注意点」等、検索されやすい
  疑問形・比較形の見出し・小見出しを最低2つ含める
- 記事末尾に、読者の疑問に答えるQ&A形式のセクション(3問程度)を含める

出力要件(技術仕様):
- HTMLタグ(<h2>, <h3>, <p>, <ul><li>, <strong>等)を使い、はてなブログにそのまま貼り付けられる形式にする
- <html>や<body>などの外枠タグは不要。本文の中身のみ出力する
- アウトラインで「(ここに比較表)」と指定された箇所に、プレースホルダー文字列
  `{PLAN_TABLE_PLACEHOLDER}` を単独の行として必ず1箇所挿入する(表自体はこちらでは生成しない)
- プラン名・料金・データ容量などの具体的な数値は上記データの記載範囲に忠実にする
- 独自お得度スコア・判定(お得/標準/割高)についても触れ、その根拠(円/GB単価や月額料金の
  グループ内平均との比較から機械的に算出していること)を簡潔に説明する
- 一部プラン(UQ mobile・ワイモバイル等)の表示価格がセット割引適用前の基本料金である場合は、
  データの補足事項に記載がある範囲でその旨に触れる(割引の具体的な金額を創作しない)
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
        raw = self._call(system, user, MAX_TOKENS_TITLE)

        title = topic_title
        meta = ""
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("TITLE:"):
                title = line[len("TITLE:"):].strip()
            elif line.startswith("META:"):
                meta = line[len("META:"):].strip()
        return title, meta

    # ------------------------------------------------------------------
    # ④ 自己レビュー(誤情報・薄い内容チェック)
    # ------------------------------------------------------------------
    def self_review(
        self, topic_title: str, plans_text: str, body_html: str
    ) -> tuple[str, str]:
        system = (
            "あなたは編集責任者として、公開前の記事をレビューする校閲者です。"
            "通信プランの料金記事は読者の金銭的判断に直結するため、特に厳格にチェックします。"
            "Googleの「Scaled Content Abuse」ポリシー(独自性のない量産的低品質コンテンツへの対策)"
            "も踏まえ、以下の観点をチェックしてください。"
            "1) 与えられたプランデータにない事実(料金・データ容量・割引額・キャンペーン詳細・"
            "具体的な個人の体験談の細部)を創作していないか。特に価格・データ容量の数値が"
            "データと完全に一致しているかを最優先で確認する"
            "2) 内容が薄すぎないか(具体性のない一般論だけになっていないか、文字数目安3000〜4000字に"
            "対して極端に短くなっていないか)"
            "3) 読者にとっての実用的な結論(どのプランを選ぶべきか)が明確か"
            "4) 文体が血の通った読み物になっているか(テンプレ的・機械的な言い回しが目立つ場合は、"
            "生活者目線の自然な言葉づかいに直す。ただし内容の薄さと違って文体だけを理由に大きく"
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
    def run(self, topic_title: str, category: str, plans: list[dict[str, Any]]) -> ArticleDraft:
        plans_text = _format_plans_for_prompt(plans)

        outline = self.generate_outline(topic_title, category, plans_text)
        body = self.generate_body(topic_title, category, plans_text, outline)
        title, meta = self.generate_title_and_meta(topic_title, body)
        final_body, review_notes = self.self_review(topic_title, plans_text, body)

        return ArticleDraft(
            outline=outline,
            body_html=final_body,
            title=title,
            meta_description=meta,
            review_notes=review_notes,
        )
