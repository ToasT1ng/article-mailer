import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Settings } from "../src/settings";
import type { Article } from "../src/collector/base";
import type { Summary } from "../src/summarizer";

const mocks = vi.hoisted(() => ({
  addLog: vi.fn(),
  markSent: vi.fn(),
  filterUnsent: vi.fn((urls: string[]) => urls),
  sendMail: vi.fn<[Summary[], Settings], Promise<void>>().mockResolvedValue(undefined),
  hnFetch: vi.fn<[], Promise<Article[]>>().mockResolvedValue([]),
  rssFetch: vi.fn<[], Promise<Article[]>>().mockResolvedValue([]),
  screen: vi.fn(),
  selectAndSummarize: vi.fn(),
}));

vi.mock("../src/collector/hackerNews", () => ({
  HackerNewsCollector: class { fetch() { return mocks.hnFetch(); } },
  crawlArticleContent: vi.fn().mockResolvedValue(null),
}));
vi.mock("../src/collector/rss", () => ({
  RSSCollector: class { fetch() { return mocks.rssFetch(); } },
}));
vi.mock("../src/collector/arxiv", () => ({
  ArXivCollector: class { fetch() { return Promise.resolve([]); } },
}));
vi.mock("../src/db/repository", () => ({
  ArticleRepository: class {
    filterUnsent(urls: string[]) { return mocks.filterUnsent(urls); }
    markSent(...args: unknown[]) { mocks.markSent(...args); }
    addLog(entry: unknown) { mocks.addLog(entry); }
  },
}));
vi.mock("../src/mailer", () => ({
  sendMail: (...args: unknown[]) => mocks.sendMail(...(args as [Summary[], Settings])),
}));
vi.mock("../src/summarizer", () => ({
  Summarizer: class {
    screen(...args: unknown[]) { return mocks.screen(...args); }
    selectAndSummarize(...args: unknown[]) { return mocks.selectAndSummarize(...args); }
  },
}));

import { runPipeline } from "../src/pipeline";

const settings: Settings = {
  SEND_HOUR: 8,
  SEND_MINUTE: 0,
  TIMEZONE: "Asia/Seoul",
  ARTICLE_COUNT: 5,
  ARTICLE_LANGUAGE: "ko",
  GEMINI_API_KEY: "test",
  GEMINI_MODEL: "gemini-2.5-flash",
  SMTP_HOST: "smtp.gmail.com",
  SMTP_PORT: 587,
  SMTP_USER: "test@example.com",
  SMTP_PASSWORD: "pw",
  RECIPIENT_EMAILS: "a@example.com",
  DATA_PATH: "/tmp/test-pipeline.json",
};

function makeArticle(i: number): Article {
  return {
    title: `Article ${i}`,
    url: `https://example.com/${i}`,
    source: "test",
    publishedAt: new Date(),
    fallbackDescription: `desc ${i}`,
  };
}

function makeSummary(article: Article): Summary {
  return {
    article: { ...article, category: "impact" },
    oneLiner: "",
    body: "",
    importance: "medium",
    readTimeMin: 1,
  };
}

describe("runPipeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hnFetch.mockResolvedValue([]);
    mocks.rssFetch.mockResolvedValue([]);
    mocks.filterUnsent.mockImplementation((urls: string[]) => urls);
    mocks.sendMail.mockResolvedValue(undefined);
    mocks.screen.mockImplementation((articles: Article[]) => Promise.resolve(articles));
    mocks.selectAndSummarize.mockImplementation((articles: Article[]) =>
      Promise.resolve(articles.map(makeSummary))
    );
  });

  it("수집된 아티클이 없으면 failed 로그를 기록한다", async () => {
    await runPipeline(settings);
    expect(mocks.addLog).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", errorMessage: "수집된 아티클 없음" })
    );
    expect(mocks.sendMail).not.toHaveBeenCalled();
  });

  it("정상 흐름에서 sendMail, markSent, success 로그를 호출한다", async () => {
    const articles = [makeArticle(1), makeArticle(2)];
    mocks.hnFetch.mockResolvedValue(articles);

    await runPipeline(settings);

    expect(mocks.sendMail).toHaveBeenCalledOnce();
    expect(mocks.markSent).toHaveBeenCalledOnce();
    expect(mocks.addLog).toHaveBeenCalledWith(
      expect.objectContaining({ status: "success", articleCount: articles.length })
    );
  });

  it("selectAndSummarize가 빈 배열을 반환하면 failed 로그를 기록하고 sendMail을 호출하지 않는다", async () => {
    mocks.hnFetch.mockResolvedValue([makeArticle(1)]);
    mocks.selectAndSummarize.mockResolvedValue([]);

    await runPipeline(settings);

    expect(mocks.sendMail).not.toHaveBeenCalled();
    expect(mocks.addLog).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", errorMessage: "요약 결과 없음" })
    );
  });

  it("sendMail 실패 시 failed 로그를 기록하고 markSent를 건너뛴 뒤 에러를 rethrow한다", async () => {
    mocks.hnFetch.mockResolvedValue([makeArticle(1)]);
    mocks.sendMail.mockRejectedValue(new Error("SMTP 오류"));

    await expect(runPipeline(settings)).rejects.toThrow("SMTP 오류");
    expect(mocks.addLog).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", errorMessage: expect.stringContaining("SMTP 오류") })
    );
    expect(mocks.markSent).not.toHaveBeenCalled();
  });

  it("dry-run 모드에서는 sendMail과 addLog를 호출하지 않는다", async () => {
    mocks.hnFetch.mockResolvedValue([makeArticle(1)]);

    await runPipeline(settings, { dryRun: true });

    expect(mocks.sendMail).not.toHaveBeenCalled();
    expect(mocks.addLog).not.toHaveBeenCalled();
    expect(mocks.markSent).not.toHaveBeenCalled();
  });

  it("중복 URL을 가진 아티클은 하나만 처리한다", async () => {
    const article = makeArticle(1);
    mocks.hnFetch.mockResolvedValue([article, article]);

    await runPipeline(settings);

    const [passedArticles] = mocks.screen.mock.calls[0] as [Article[]];
    expect(passedArticles).toHaveLength(1);
  });

  it("이미 발송된 아티클은 제외한다", async () => {
    mocks.hnFetch.mockResolvedValue([makeArticle(1), makeArticle(2)]);
    mocks.filterUnsent.mockImplementation((urls: string[]) => urls.slice(0, 1));

    await runPipeline(settings);

    const [passedArticles] = mocks.screen.mock.calls[0] as [Article[]];
    expect(passedArticles).toHaveLength(1);
  });

  it("수집기 하나가 실패해도 나머지 아티클로 파이프라인을 계속 실행한다", async () => {
    mocks.hnFetch.mockRejectedValue(new Error("HN 수집 실패"));
    mocks.rssFetch.mockResolvedValue([makeArticle(1)]);

    await runPipeline(settings);

    expect(mocks.sendMail).toHaveBeenCalledOnce();
  });
});
