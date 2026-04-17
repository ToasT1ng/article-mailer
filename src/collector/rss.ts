import Parser from "rss-parser";
import { AbstractCollector, Article } from "./base.js";
import logger from "../logger.js";

const USER_AGENT =
  "Mozilla/5.0 (compatible; article-mailer/1.0; +https://github.com/toasting/article-mailer)";

const RSS_FEEDS: Array<{ url: string; source: string }> = [
  { url: "https://huggingface.co/blog/feed.xml", source: "Hugging Face Blog" },
  { url: "https://www.technologyreview.com/topic/artificial-intelligence/feed/", source: "MIT Tech Review" },
  { url: "https://venturebeat.com/category/ai/feed/", source: "VentureBeat AI" },
];

export class RSSCollector extends AbstractCollector {
  private parser = new Parser({ timeout: 10_000 });

  async fetch(): Promise<Article[]> {
    const log = logger.child({ collector: "rss" });
    const results = await Promise.allSettled(
      RSS_FEEDS.map((feed) => this.fetchFeed(feed.url, feed.source))
    );

    const articles: Article[] = [];
    for (const result of results) {
      if (result.status === "fulfilled") {
        articles.push(...result.value);
      } else {
        log.warn({ event: "rss.fetch_failed", error: String(result.reason) });
      }
    }

    log.info({ event: "rss.fetch", count: articles.length });
    return articles;
  }

  private async fetchFeed(url: string, source: string): Promise<Article[]> {
    const res = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) throw new Error(`Status code ${res.status}`);
    const xml = await res.text();
    const feed = await this.parser.parseString(xml);
    return (feed.items ?? []).slice(0, 20).map((item) => ({
      title: item.title ?? "(제목 없음)",
      url: item.link ?? "",
      source,
      publishedAt: item.pubDate ? new Date(item.pubDate) : new Date(),
      fallbackDescription: item.contentSnippet ?? item.summary ?? item.title ?? "",
    }));
  }
}
