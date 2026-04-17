export interface Article {
  title: string;
  url: string;
  source: string;
  publishedAt: Date;
  rawContent?: string;
  fallbackDescription: string;
  category?: "impact" | "trend_llm" | "trend_industry";
  score?: number;
}

export abstract class AbstractCollector {
  abstract fetch(): Promise<Article[]>;
}
