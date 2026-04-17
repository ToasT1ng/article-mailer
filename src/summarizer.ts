import { GoogleGenerativeAI } from "@google/generative-ai";
import { Article } from "./collector/base.js";
import logger from "./logger.js";
import { withRetry } from "./utils/retry.js";

const log = logger.child({ module: "summarizer" });

export interface Summary {
  article: Article;
  oneLiner: string;
  body: string;
  importance: "high" | "medium" | "low";
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
  importance: "high" | "medium" | "low";
  read_time_min: number;
}


export class Summarizer {
  private client: GoogleGenerativeAI;
  private modelName: string;
  private language: string;

  constructor(apiKey: string, modelName: string, language = "English") {
    this.client = new GoogleGenerativeAI(apiKey);
    this.modelName = modelName;
    this.language = language;
  }

  async screen(articles: Article[], total: number): Promise<Article[]> {
    const industryCount = Math.round(total * 0.6);
    const llmCount = Math.round(total * 0.2);
    const impactCount = total - industryCount - llmCount;

    const prompt = `You are a professional AI/ML news editor.
From the candidate article list below, select exactly ${total} articles.

Category selection criteria (in priority order):
- trend_industry (${industryCount}): Product and service updates, launches, and business strategies from major AI companies such as OpenAI, Anthropic, Google, and Meta
- impact (${impactCount}): Real-world AI adoption cases in industries like healthcare, law, education — stories that show AI changing the world
- trend_llm (${llmCount}): Research and trends on LLM architecture, training techniques, benchmarks, and model technology itself

If fewer than ${industryCount} trend_industry articles are available, substitute with trend_llm.

Candidate list:
${articles.map((a, i) => `[${i}] ${a.title} (${a.source})\n    ${a.fallbackDescription.slice(0, 150)}`).join("\n")}

Respond with a JSON array only: [{"index": 0, "category": "trend_industry"}, ...]`;

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
    const prompt = `You are a professional AI/ML news editor.
From the ${articles.length} articles below, select the best ${finalCount} and summarize them.

Article list:
${articles
  .map(
    (a, i) => `[${i}] Title: ${a.title}
Source: ${a.source}
Content: ${(a.rawContent ?? a.fallbackDescription).slice(0, 3500)}`
  )
  .join("\n\n")}

Respond with a JSON array only (category must be one of "trend_industry", "trend_llm", "impact" / importance must be one of "high", "medium", "low"):
[{
  "index": 0,
  "category": "trend_industry",
  "one_liner": "One-line summary (under 100 characters)",
  "body": "3–5 sentence summary",
  "importance": "high",
  "read_time_min": 3
}]

Respond in ${this.language}.
Note: importance values must always be in English ("high", "medium", or "low"), regardless of the response language.`;

    const results = await withRetry(() => this.callGemini<SummarizeResult[]>(prompt));
    const seen = new Set<number>();
    const summaries: Summary[] = [];
    for (const r of results) {
      const article = articles[r.index];
      if (!article || seen.has(r.index)) continue;
      seen.add(r.index);
      const importance: Summary["importance"] =
        r.importance === "high" || r.importance === "medium" || r.importance === "low"
          ? r.importance
          : "medium";
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
