// @mozilla/readability의 타입 정의가 DOM Document를 참조하므로 파일 스코프로 추가
/// <reference lib="dom" />
import * as cheerio from "cheerio";
import { Readability } from "@mozilla/readability";
import { parseHTML } from "linkedom";
import { AbstractCollector, Article } from "./base.js";
import logger from "../logger.js";
import { isHttpUrl } from "../utils/url.js";

const AI_KEYWORDS = ["ai", "llm", "gpt", "ml", "machine learning", "neural", "deep learning", "openai", "gemini", "claude", "anthropic", "mistral"];
const HN_API = "https://hacker-news.firebaseio.com/v0";
const MIN_SCORE = 100;
const MAX_AGE_HOURS = 24;

interface HNItem {
  id: number;
  title: string;
  url?: string;
  score: number;
  time: number;
  text?: string;
}

export async function crawlArticleContent(url: string): Promise<string | undefined> {
  if (!isHttpUrl(url)) return undefined;
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(10_000),
      headers: { "User-Agent": "Mozilla/5.0 (compatible; article-mailer/1.0)" },
    });
    if (!res.ok) return undefined;
    const html = await res.text();

    // Readability로 본문 추출 시도
    try {
      const { document } = parseHTML(html);
      const reader = new Readability(document as unknown as Document);
      const article = reader.parse();
      if (article?.textContent && article.textContent.trim().length > 200) {
        return article.textContent.replace(/\s+/g, " ").trim().slice(0, 8000);
      }
    } catch {
      // Readability 실패 시 cheerio fallback
    }

    // cheerio fallback
    const $ = cheerio.load(html);
    $("script, style, nav, footer, header, aside, .ad, .advertisement").remove();
    const text = $("article, main, .content, .post-body, .entry-content, body")
      .first()
      .text()
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 8000);
    return text.length > 200 ? text : undefined;
  } catch {
    return undefined;
  }
}

export class HackerNewsCollector extends AbstractCollector {
  async fetch(): Promise<Article[]> {
    const log = logger.child({ collector: "hackernews" });

    const topIds: number[] = await fetch(`${HN_API}/topstories.json`)
      .then((r) => r.json())
      .then((ids) => (ids as number[]).slice(0, 200));

    const cutoff = Date.now() / 1000 - MAX_AGE_HOURS * 3600;

    const items = await Promise.allSettled(
      topIds.map((id) =>
        fetch(`${HN_API}/item/${id}.json`).then((r) => r.json() as Promise<HNItem>)
      )
    );

    const articles: Article[] = [];
    for (const result of items) {
      if (result.status !== "fulfilled") continue;
      const item = result.value;
      if (!item.url) continue;
      if (item.score < MIN_SCORE) continue;
      if (item.time < cutoff) continue;

      const titleLower = item.title.toLowerCase();
      const isAiRelated = AI_KEYWORDS.some((kw) => titleLower.includes(kw));
      if (!isAiRelated) continue;

      articles.push({
        title: item.title,
        url: item.url,
        source: "Hacker News",
        publishedAt: new Date(item.time * 1000),
        fallbackDescription: item.text
          ? cheerio.load(item.text).text().slice(0, 300)
          : `(HN score: ${item.score}) ${item.title}`,
        score: item.score,
      });
    }

    log.info({ event: "hackernews.fetch", count: articles.length });
    return articles;
  }
}
