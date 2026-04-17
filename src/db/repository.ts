import fs from "fs";
import path from "path";

export interface SentArticle {
  url: string;
  title: string;
  source: string;
  sentAt: string;
}

export interface SendLog {
  runAt: string;
  articleCount: number;
  recipientCount: number;
  status: "success" | "partial" | "failed";
  errorMessage?: string;
  createdAt: string;
}

interface StoreData {
  sentArticles: SentArticle[];
  sendLogs: SendLog[];
}

export class ArticleRepository {
  private dataPath: string;
  private data: StoreData;

  constructor(dataPath: string) {
    this.dataPath = dataPath;
    this.data = this.load();
  }

  private load(): StoreData {
    const dir = path.dirname(this.dataPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    if (!fs.existsSync(this.dataPath)) {
      return { sentArticles: [], sendLogs: [] };
    }
    try {
      return JSON.parse(fs.readFileSync(this.dataPath, "utf-8")) as StoreData;
    } catch {
      return { sentArticles: [], sendLogs: [] };
    }
  }

  private save(): void {
    fs.writeFileSync(this.dataPath, JSON.stringify(this.data, null, 2), "utf-8");
  }

  filterUnsent(urls: string[]): string[] {
    const sentSet = new Set(this.data.sentArticles.map((a) => a.url));
    return urls.filter((url) => !sentSet.has(url));
  }

  markSent(articles: Array<{ url: string; title: string; source: string }>): void {
    const now = new Date().toISOString();
    for (const article of articles) {
      this.data.sentArticles.push({ ...article, sentAt: now });
    }
    this.save();
  }

  addLog(log: Omit<SendLog, "createdAt">): void {
    this.data.sendLogs.push({ ...log, createdAt: new Date().toISOString() });
    this.save();
  }
}
