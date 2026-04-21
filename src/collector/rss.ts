import Parser from "rss-parser";
import { readFileSync, existsSync } from "fs";
import { AbstractCollector, Article } from "./base.js";
import logger from "../logger.js";
import { isHttpUrl } from "../utils/url.js";

const USER_AGENT =
  "Mozilla/5.0 (compatible; article-mailer/1.0; +https://github.com/toasting/article-mailer)";

const DEFAULT_FEEDS: Array<{ url: string; source: string }> = [
  { url: "https://huggingface.co/blog/feed.xml", source: "Hugging Face Blog" },
  { url: "https://www.technologyreview.com/topic/artificial-intelligence/feed/", source: "MIT Tech Review" },
  { url: "https://venturebeat.com/category/ai/feed/", source: "VentureBeat AI" },
];

interface FeedEntry {
  url: string;
  source: string;
}

function loadExtraFeeds(feedsPath: string): Array<{ url: string; source: string }> {
  if (!existsSync(feedsPath)) return [];
  try {
    const raw = readFileSync(feedsPath, "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      logger.warn({ event: "rss.feeds_invalid", path: feedsPath, reason: "배열이 아님" });
      return [];
    }
    return (parsed as FeedEntry[]).filter((f) => {
      if (typeof f.url !== "string" || typeof f.source !== "string") return false;
      if (!isHttpUrl(f.url)) {
        logger.warn({ event: "rss.feed_url_invalid", url: f.url, source: f.source });
        return false;
      }
      return true;
    });
  } catch (err) {
    logger.warn({ event: "rss.feeds_load_failed", path: feedsPath, error: String(err) });
    return [];
  }
}

export class RSSCollector extends AbstractCollector {
  private parser = new Parser({ timeout: 10_000 });
  private feedsPath: string;

  constructor(feedsPath = "./feeds.json") {
    super();
    this.feedsPath = feedsPath;
  }

  async fetch(): Promise<Article[]> {
    const log = logger.child({ collector: "rss" });

    const extraFeeds = loadExtraFeeds(this.feedsPath);
    const allFeeds = [...DEFAULT_FEEDS, ...extraFeeds];

    if (extraFeeds.length > 0) {
      log.info({ event: "rss.extra_feeds_loaded", count: extraFeeds.length, sources: extraFeeds.map((f) => f.source) });
    }

    const results = await Promise.allSettled(
      allFeeds.map((feed) => this.fetchFeed(feed.url, feed.source))
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

