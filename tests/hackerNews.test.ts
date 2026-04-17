import { describe, it, expect, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => ({
  readabilityParse: vi.fn(),
}));

vi.mock("linkedom", () => ({
  parseHTML: vi.fn().mockReturnValue({ document: {} }),
}));

vi.mock("@mozilla/readability", () => ({
  Readability: vi.fn().mockImplementation(function () {
    return { parse: mocks.readabilityParse };
  }),
}));

import { crawlArticleContent } from "../src/collector/hackerNews.js";

function mockFetch(ok: boolean, html = "") {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, text: () => Promise.resolve(html) })
  );
}

describe("crawlArticleContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Readability가 200자 이상 텍스트를 반환하면 해당 텍스트를 반환한다", async () => {
    const body = "본문 내용 ".repeat(50);
    mocks.readabilityParse.mockReturnValue({ textContent: body });
    mockFetch(true, "<html><body><p>content</p></body></html>");

    const result = await crawlArticleContent("https://example.com");
    expect(result).toBe(body.replace(/\s+/g, " ").trim());
  });

  it("Readability 결과가 200자 미만이면 cheerio fallback을 사용한다", async () => {
    mocks.readabilityParse.mockReturnValue({ textContent: "짧음" });
    const longContent = "fallback content ".repeat(20);
    mockFetch(true, `<html><body><article>${longContent}</article></body></html>`);

    const result = await crawlArticleContent("https://example.com");
    expect(result).toContain("fallback content");
  });

  it("Readability가 예외를 던지면 cheerio fallback을 사용한다", async () => {
    mocks.readabilityParse.mockImplementation(() => {
      throw new Error("parse failed");
    });
    const longContent = "cheerio fallback ".repeat(20);
    mockFetch(true, `<html><body><article>${longContent}</article></body></html>`);

    const result = await crawlArticleContent("https://example.com");
    expect(result).toContain("cheerio fallback");
  });

  it("HTTP 응답이 ok가 아니면 undefined를 반환한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    const result = await crawlArticleContent("https://example.com");
    expect(result).toBeUndefined();
  });

  it("fetch 자체가 실패하면 undefined를 반환한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));

    const result = await crawlArticleContent("https://example.com");
    expect(result).toBeUndefined();
  });

  it("cheerio fallback도 200자 미만이면 undefined를 반환한다", async () => {
    mocks.readabilityParse.mockReturnValue({ textContent: "짧음" });
    mockFetch(true, "<html><body><article>짧은 내용</article></body></html>");

    const result = await crawlArticleContent("https://example.com");
    expect(result).toBeUndefined();
  });
});
