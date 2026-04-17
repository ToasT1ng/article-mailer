import { Settings, getRecipients } from "./settings.js";
import { HackerNewsCollector, crawlArticleContent } from "./collector/hackerNews.js";
import { RSSCollector } from "./collector/rss.js";
import { ArXivCollector } from "./collector/arxiv.js";
import { Article } from "./collector/base.js";
import { Summarizer } from "./summarizer.js";
import { sendMail } from "./mailer.js";
import { ArticleRepository } from "./db/repository.js";
import logger from "./logger.js";

const log = logger.child({ module: "pipeline" });

export async function runPipeline(settings: Settings, options: { dryRun?: boolean; count?: number } = {}): Promise<void> {
  const articleCount = options.count ?? settings.ARTICLE_COUNT;
  log.info({ event: "pipeline.start", dryRun: options.dryRun ?? false });

  const repo = new ArticleRepository(settings.DATA_PATH);

  const [hnArticles, rssArticles, arxivArticles] = await Promise.allSettled([
    new HackerNewsCollector().fetch(),
    new RSSCollector(settings.FEEDS_PATH).fetch(),
    new ArXivCollector().fetch(),
  ]).then((results) =>
    results.map((r) => (r.status === "fulfilled" ? r.value : []))
  ) as [Article[], Article[], Article[]];

  const allArticles = [...hnArticles, ...rssArticles, ...arxivArticles];

  const deduped = deduplicateArticles(allArticles);
  const unsentUrlSet = new Set(repo.filterUnsent(deduped.map((a) => a.url)));
  const unsent = deduped.filter((a) => unsentUrlSet.has(a.url));
  const sorted = unsent.sort((a, b) => {
    // 최신순 기본 정렬, HN score가 있으면 가중치 반영 (score 100점당 1시간 보정)
    const scoreBoostMs = ((b.score ?? 0) - (a.score ?? 0)) * 36_000;
    return (b.publishedAt.getTime() + scoreBoostMs) - a.publishedAt.getTime();
  });

  log.info({ event: "pipeline.collected", total: allArticles.length, unsent: unsent.length });

  if (options.dryRun) {
    log.info({ event: "pipeline.dry_run", articles: sorted.slice(0, articleCount).map((a) => a.title) });
    return;
  }

  if (sorted.length === 0) {
    log.warn({ event: "pipeline.no_articles" });
    repo.addLog({ runAt: new Date().toISOString(), articleCount: 0, recipientCount: 0, status: "failed", errorMessage: "수집된 아티클 없음" });
    return;
  }

  const summarizer = new Summarizer(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.ARTICLE_LANGUAGE);

  const screenCount = Math.min(sorted.length, articleCount * 3);
  const screened = await summarizer.screen(sorted.slice(0, screenCount), Math.min(screenCount, articleCount * 2));

  const crawled = await crawlContents(screened);

  const summaries = await summarizer.selectAndSummarize(crawled, Math.min(crawled.length, articleCount));

  if (summaries.length === 0) {
    log.warn({ event: "pipeline.no_summaries" });
    repo.addLog({ runAt: new Date().toISOString(), articleCount: 0, recipientCount: 0, status: "failed", errorMessage: "요약 결과 없음" });
    return;
  }

  try {
    await sendMail(summaries, settings);
    repo.markSent(summaries.map((s) => ({ url: s.article.url, title: s.article.title, source: s.article.source })));
    repo.addLog({
      runAt: new Date().toISOString(),
      articleCount: summaries.length,
      recipientCount: getRecipients(settings).length,
      status: "success",
    });
    log.info({ event: "pipeline.done", sent: summaries.length });
  } catch (err) {
    repo.addLog({
      runAt: new Date().toISOString(),
      articleCount: summaries.length,
      recipientCount: 0,
      status: "failed",
      errorMessage: String(err),
    });
    throw err;
  }
}

function deduplicateArticles(articles: Article[]): Article[] {
  const seen = new Set<string>();
  return articles.filter((a) => {
    if (!a.url || seen.has(a.url)) return false;
    seen.add(a.url);
    return true;
  });
}

const CRAWL_CONCURRENCY = 4;

async function crawlContents(articles: Article[]): Promise<Article[]> {
  const results: Article[] = new Array(articles.length);
  let idx = 0;

  async function worker() {
    while (idx < articles.length) {
      const i = idx++;
      try {
        const content = await crawlArticleContent(articles[i].url);
        results[i] = { ...articles[i], rawContent: content };
      } catch {
        results[i] = articles[i];
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(CRAWL_CONCURRENCY, articles.length) }, worker)
  );
  return results;
}
