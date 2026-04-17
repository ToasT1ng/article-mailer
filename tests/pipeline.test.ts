import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Article } from "../src/collector/base";
import type { Settings } from "../src/settings";

vi.mock("../src/collector/hackerNews", () => ({
  HackerNewsCollector: class { fetch() { return Promise.resolve([]); } },
  crawlArticleContent: vi.fn().mockResolvedValue(null),
}));
vi.mock("../src/collector/rss", () => ({
  RSSCollector: class { fetch() { return Promise.resolve([]); } },
}));
vi.mock("../src/collector/arxiv", () => ({
  ArXivCollector: class { fetch() { return Promise.resolve([]); } },
}));

const addLogMock = vi.fn();
vi.mock("../src/db/repository", () => {
  return {
    ArticleRepository: class {
      filterUnsent(urls: string[]) { return urls; }
      markSent() {}
      addLog(log: unknown) { addLogMock(log); }
    },
  };
});

vi.mock("../src/mailer", () => ({
  sendMail: vi.fn(),
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

describe("runPipeline", () => {
  beforeEach(() => {
    addLogMock.mockClear();
  });

  it("수집된 아티클이 없으면 failed 로그를 기록한다", async () => {
    await runPipeline(settings);
    expect(addLogMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", errorMessage: "수집된 아티클 없음" })
    );
  });
});
