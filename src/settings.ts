import { z } from "zod";
import dotenv from "dotenv";

dotenv.config();

export const ARTICLE_COUNT_MAX = 20;

const settingsSchema = z.object({
  SEND_HOUR: z.coerce.number().int().min(0).max(23).default(8),
  SEND_MINUTE: z.coerce.number().int().min(0).max(59).default(0),
  TIMEZONE: z.string().default("Asia/Seoul"),
  ARTICLE_COUNT: z.coerce.number().int().min(1).max(ARTICLE_COUNT_MAX).default(5),
  ARTICLE_LANGUAGE: z.string().default("ko"),
  GEMINI_API_KEY: z.string().min(1),
  GEMINI_MODEL: z.string().default("gemini-2.5-flash"),
  SMTP_HOST: z.string().default("smtp.gmail.com"),
  SMTP_PORT: z.coerce.number().int().default(587),
  SMTP_USER: z.string().min(1),
  SMTP_PASSWORD: z.string().min(1),
  RECIPIENT_EMAILS: z.string().min(1),
  DATA_PATH: z.string().default("./data/article_mailer.json"),
  FEEDS_PATH: z.string().default("./feeds.json"),
});

export type Settings = z.infer<typeof settingsSchema>;

export function loadSettings(): Settings {
  const result = settingsSchema.safeParse(process.env);
  if (!result.success) {
    const missing = result.error.errors
      .map((e) => `${e.path.join(".")}: ${e.message}`)
      .join("\n");
    throw new Error(`설정 오류:\n${missing}`);
  }
  return result.data;
}

export function getRecipients(settings: Settings): string[] {
  return settings.RECIPIENT_EMAILS.split(",")
    .map((e) => e.trim())
    .filter(Boolean);
}
