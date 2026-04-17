import { describe, it, expect, vi } from "vitest";

const sendMailMock = vi.fn();
vi.mock("nodemailer", () => ({
  default: {
    createTransport: vi.fn(() => ({ sendMail: sendMailMock })),
  },
}));

import { sendMail } from "../src/mailer";
import type { Settings } from "../src/settings";

const baseSettings: Settings = {
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
  RECIPIENT_EMAILS: ",  ,",
  DATA_PATH: "/tmp/test.json",
};

describe("sendMail", () => {
  it("수신자가 없으면 SMTP 전송을 호출하지 않는다", async () => {
    await sendMail([], baseSettings);
    expect(sendMailMock).not.toHaveBeenCalled();
  });
});
