import { GoogleGenerativeAI } from "@google/generative-ai";
import { Article } from "./collector/base.js";
import logger from "./logger.js";
import { withRetry } from "./utils/retry.js";

const log = logger.child({ module: "summarizer" });

export interface Summary {
  article: Article;
  oneLiner: string;
  body: string;
  importance: "상" | "중" | "하";
  readTimeMin: number;
}

interface ScreenResult {
  index: number;
  category: "impact" | "trend_llm" | "trend_industry";
}

interface SummarizeResult {
  index: number;
  category: "impact" | "trend_llm" | "trend_industry";
  one_liner: string;
  body: string;
  importance: "상" | "중" | "하";
  read_time_min: number;
}


export class Summarizer {
  private client: GoogleGenerativeAI;
  private modelName: string;
  private language: string;

  constructor(apiKey: string, modelName: string, language = "ko") {
    this.client = new GoogleGenerativeAI(apiKey);
    this.modelName = modelName;
    this.language = language;
  }

  async screen(articles: Article[], total: number): Promise<Article[]> {
    const industryCount = Math.round(total * 0.6);
    const llmCount = Math.round(total * 0.2);
    const impactCount = total - industryCount - llmCount;

    const prompt = `당신은 AI/ML 전문 뉴스 편집장입니다.
아래 아티클 후보 목록에서 정확히 ${total}개를 선별하세요.

카테고리별 선별 기준 (우선순위 순):
- trend_industry (${industryCount}개): OpenAI, Anthropic, Google, Meta 등 주요 기업의 LLM 제품·서비스 동향, 출시 소식, 비즈니스 전략
- impact (${impactCount}개): AI가 의료·법률·교육 등 실제 산업에 적용되어 세상을 바꾸는 사례
- trend_llm (${llmCount}개): LLM 아키텍처, 학습 기법, 벤치마크 등 모델 기술 자체에 관한 연구·동향

trend_industry 아티클이 ${industryCount}개 미만이면 trend_llm으로 대체하세요.

후보 목록:
${articles.map((a, i) => `[${i}] ${a.title} (${a.source})`).join("\n")}

JSON 배열로만 응답: [{"index": 0, "category": "trend_industry"}, ...]`;

    const result = await withRetry(() => this.callGemini<ScreenResult[]>(prompt));
    const seen = new Set<number>();
    const selected: Article[] = [];
    for (const r of result) {
      if (r.index < 0 || r.index >= articles.length || seen.has(r.index)) continue;
      seen.add(r.index);
      selected.push({ ...articles[r.index], category: r.category });
      if (selected.length >= total) break;
    }
    if (selected.length < total) {
      for (let i = 0; i < articles.length && selected.length < total; i++) {
        if (!seen.has(i)) selected.push(articles[i]);
      }
    }
    log.info({ event: "summarizer.screen", selected: selected.length });
    return selected;
  }

  async selectAndSummarize(articles: Article[], finalCount: number): Promise<Summary[]> {
    const prompt = `당신은 AI/ML 전문 뉴스 편집자입니다.
아래 ${articles.length}개 아티클에서 최종 ${finalCount}개를 선택하여 ${this.language === "ko" ? "한국어로" : "영어로"} 요약하세요.

아티클 목록:
${articles
  .map(
    (a, i) => `[${i}] 제목: ${a.title}
출처: ${a.source}
내용: ${(a.rawContent ?? a.fallbackDescription).slice(0, 3500)}`
  )
  .join("\n\n")}

JSON 배열로만 응답:
[{
  "index": 0,
  "category": "trend_industry | trend_llm | impact",
  "one_liner": "한 줄 요약 (50자 이내)",
  "body": "3~5문장 요약",
  "importance": "상 | 중 | 하",
  "read_time_min": 3
}]`;

    const results = await withRetry(() => this.callGemini<SummarizeResult[]>(prompt));
    const seen = new Set<number>();
    const summaries: Summary[] = [];
    for (const r of results) {
      const article = articles[r.index];
      if (!article || seen.has(r.index)) continue;
      seen.add(r.index);
      const importance: Summary["importance"] =
        r.importance === "상" || r.importance === "중" || r.importance === "하"
          ? r.importance
          : "중";
      summaries.push({
        article: { ...article, category: r.category },
        oneLiner: r.one_liner,
        body: r.body,
        importance,
        readTimeMin: r.read_time_min,
      });
    }
    log.info({ event: "summarizer.summarize", count: summaries.length });
    return summaries;
  }

  private async callGemini<T>(prompt: string): Promise<T> {
    const model = this.client.getGenerativeModel({
      model: this.modelName,
      generationConfig: { responseMimeType: "application/json" },
    });
    const result = await model.generateContent(prompt);
    const text = result.response.text();
    return JSON.parse(text) as T;
  }
}
