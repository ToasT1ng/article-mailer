import { describe, it, expect, vi, beforeEach } from "vitest";
import { Summarizer } from "../src/summarizer";
import type { Article } from "../src/collector/base";

function makeArticle(i: number): Article {
  return {
    title: `Article ${i}`,
    url: `https://example.com/${i}`,
    source: "test",
    publishedAt: new Date(),
    fallbackDescription: `desc ${i}`,
  };
}

describe("Summarizer.screen", () => {
  let summarizer: Summarizer;

  beforeEach(() => {
    summarizer = new Summarizer("test-key", "gemini-2.5-flash");
  });

  it("범위 초과 인덱스를 무시한다", async () => {
    const articles = [makeArticle(0), makeArticle(1), makeArticle(2)];
    vi.spyOn(summarizer as any, "callGemini").mockResolvedValue([
      { index: 99, category: "impact" },
      { index: 0, category: "impact" },
    ]);
    const result = await summarizer.screen(articles, 1);
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Article 0");
  });

  it("중복 인덱스를 제거한다", async () => {
    const articles = [makeArticle(0), makeArticle(1)];
    vi.spyOn(summarizer as any, "callGemini").mockResolvedValue([
      { index: 0, category: "impact" },
      { index: 0, category: "trend" },
    ]);
    const result = await summarizer.screen(articles, 2);
    expect(result.filter((a) => a.url === articles[0].url)).toHaveLength(1);
  });

  it("결과가 부족하면 나머지 아티클로 채운다", async () => {
    const articles = [makeArticle(0), makeArticle(1), makeArticle(2)];
    vi.spyOn(summarizer as any, "callGemini").mockResolvedValue([
      { index: 0, category: "impact" },
    ]);
    const result = await summarizer.screen(articles, 3);
    expect(result).toHaveLength(3);
  });

  it("total보다 많은 결과는 clamp한다", async () => {
    const articles = [makeArticle(0), makeArticle(1), makeArticle(2)];
    vi.spyOn(summarizer as any, "callGemini").mockResolvedValue([
      { index: 0, category: "impact" },
      { index: 1, category: "trend" },
      { index: 2, category: "impact" },
    ]);
    const result = await summarizer.screen(articles, 2);
    expect(result).toHaveLength(2);
  });
});
