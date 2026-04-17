import nodemailer from "nodemailer";
import Handlebars from "handlebars";
import fs from "fs";
import path from "path";
import { Summary } from "./summarizer.js";
import { Settings, getRecipients } from "./settings.js";
import logger from "./logger.js";
import { withRetry } from "./utils/retry.js";

const log = logger.child({ module: "mailer" });

function loadTemplate(name: string): Handlebars.TemplateDelegate {
  const templatePath = path.join(__dirname, "templates", name);
  const src = fs.readFileSync(templatePath, "utf-8");
  return Handlebars.compile(src);
}

export async function sendMail(summaries: Summary[], settings: Settings): Promise<void> {
  const recipients = getRecipients(settings);
  if (recipients.length === 0) {
    log.warn({ event: "mailer.no_recipients" });
    return;
  }
  const htmlTemplate = loadTemplate("email.html");
  const txtTemplate = loadTemplate("email.txt");

  const now = new Date();
  const formattedDate = now.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  const templateData = {
    formattedDate,
    count: summaries.length,
    items: summaries,
  };

  const html = htmlTemplate(templateData);
  const text = txtTemplate(templateData);
  const subject = `[AI 데일리] ${formattedDate} | 오늘의 AI 아티클 ${summaries.length}선`;

  const transporter = nodemailer.createTransport({
    host: settings.SMTP_HOST,
    port: settings.SMTP_PORT,
    secure: settings.SMTP_PORT === 465,
    auth: {
      user: settings.SMTP_USER,
      pass: settings.SMTP_PASSWORD,
    },
  });

  await withRetry(async () => {
    await transporter.sendMail({
      from: `"AI 데일리" <${settings.SMTP_USER}>`,
      to: recipients.join(", "),
      subject,
      text,
      html,
    });
  }, 3);

  log.info({ event: "mailer.sent", recipients: recipients.length, articles: summaries.length });
}
