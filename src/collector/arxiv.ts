import Parser from "rss-parser";
import { AbstractCollector, Article } from "./base.js";
import logger from "../logger.js";

const ARXIV_FEED = "https://rss.arxiv.org/rss/cs.AI";

export class ArXivCollector extends AbstractCollector {
  private parser = new Parser({ timeout: 10_000 });

  async fetch(): Promise<Article[]> {
    const log = logger.child({ collector: "arxiv" });
    try {
      const feed = await this.parser.parseURL(ARXIV_FEED);
      const articles: Article[] = (feed.items ?? []).slice(0, 20).map((item) => ({
        title: item.title ?? "(제목 없음)",
        url: item.link ?? "",
        source: "ArXiv cs.AI",
        publishedAt: item.pubDate ? new Date(item.pubDate) : new Date(),
        fallbackDescription: item.contentSnippet ?? item.summary ?? item.title ?? "",
      }));
      log.info({ event: "arxiv.fetch", count: articles.length });
      return articles;
    } catch (err) {
      log.warn({ event: "arxiv.fetch_failed", error: String(err) });
      return [];
    }
  }
}
