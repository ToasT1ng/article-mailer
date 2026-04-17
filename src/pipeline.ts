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
    new RSSCollector().fetch(),
    new ArXivCollector().fetch(),
  ]).then((results) =>
    results.map((r) => (r.status === "fulfilled" ? r.value : []))
  ) as [Article[], Article[], Article[]];

  const allArticles = [...hnArticles, ...rssArticles, ...arxivArticles];

  const deduped = deduplicateArticles(allArticles);
  const unsentUrls = repo.filterUnsent(deduped.map((a) => a.url));
  const unsent = deduped.filter((a) => unsentUrls.includes(a.url));
  const sorted = unsent.sort((a, b) => b.publishedAt.getTime() - a.publishedAt.getTime());

  log.info({ event: "pipeline.collected", total: allArticles.length, unsent: unsent.length });

  if (options.dryRun) {
    log.info({ event: "pipeline.dry_run", articles: sorted.slice(0, articleCount).map((a) => a.title) });
    return;
  }

  if (sorted.length === 0) {
    log.warn({ event: "pipeline.no_articles" });
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

  await sendMail(summaries, settings);

  repo.markSent(summaries.map((s) => ({ url: s.article.url, title: s.article.title, source: s.article.source })));
  repo.addLog({
    runAt: new Date().toISOString(),
    articleCount: summaries.length,
    recipientCount: getRecipients(settings).length,
    status: "success",
  });

  log.info({ event: "pipeline.done", sent: summaries.length });
}

function deduplicateArticles(articles: Article[]): Article[] {
  const seen = new Set<string>();
  return articles.filter((a) => {
    if (!a.url || seen.has(a.url)) return false;
    seen.add(a.url);
    return true;
  });
}

async function crawlContents(articles: Article[]): Promise<Article[]> {
  const results = await Promise.allSettled(
    articles.map(async (article) => {
      const content = await crawlArticleContent(article.url);
      return { ...article, rawContent: content };
    })
  );
  return results.map((r, i) =>
    r.status === "fulfilled" ? r.value : articles[i]
  );
}
