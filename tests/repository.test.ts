import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { ArticleRepository } from "../src/db/repository";

let tmpPath: string;

beforeEach(() => {
  tmpPath = path.join(os.tmpdir(), `repo-test-${Date.now()}.json`);
});

afterEach(() => {
  if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
});

describe("ArticleRepository", () => {
  it("파일이 없으면 빈 상태로 초기화된다", () => {
    const repo = new ArticleRepository(tmpPath);
    const result = repo.filterUnsent(["https://a.com"]);
    expect(result).toEqual(["https://a.com"]);
  });

  it("filterUnsent: 이미 발송된 URL을 제외한다", () => {
    const repo = new ArticleRepository(tmpPath);
    repo.markSent([{ url: "https://sent.com", title: "T", source: "S" }]);

    const repo2 = new ArticleRepository(tmpPath);
    const unsent = repo2.filterUnsent(["https://sent.com", "https://new.com"]);
    expect(unsent).toEqual(["https://new.com"]);
  });

  it("markSent: 발송 이력을 파일에 저장한다", () => {
    const repo = new ArticleRepository(tmpPath);
    repo.markSent([{ url: "https://a.com", title: "A", source: "src" }]);

    const data = JSON.parse(fs.readFileSync(tmpPath, "utf-8"));
    expect(data.sentArticles).toHaveLength(1);
    expect(data.sentArticles[0].url).toBe("https://a.com");
  });

  it("addLog: 실행 이력을 파일에 저장한다", () => {
    const repo = new ArticleRepository(tmpPath);
    repo.addLog({ runAt: "2026-01-01T00:00:00Z", articleCount: 3, recipientCount: 1, status: "success" });

    const data = JSON.parse(fs.readFileSync(tmpPath, "utf-8"));
    expect(data.sendLogs).toHaveLength(1);
    expect(data.sendLogs[0].status).toBe("success");
  });

  it("손상된 JSON 파일이면 빈 상태로 폴백한다", () => {
    fs.mkdirSync(path.dirname(tmpPath), { recursive: true });
    fs.writeFileSync(tmpPath, "{ invalid json", "utf-8");

    const repo = new ArticleRepository(tmpPath);
    const result = repo.filterUnsent(["https://a.com"]);
    expect(result).toEqual(["https://a.com"]);
  });
});
