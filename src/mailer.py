import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.settings import Settings
from src.summarizer import Summary

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class Mailer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def send(self, summaries: list[Summary], send_date: datetime | None = None) -> None:
        """요약 목록을 HTML 이메일로 발송한다."""
        if not summaries:
            log.warning("mailer.skip.no_summaries")
            return

        send_date = send_date or datetime.now()
        subject = (
            f"[AI 데일리] {send_date.strftime('%Y-%m-%d')} | "
            f"오늘의 AI 아티클 {len(summaries)}선"
        )

        html_body = self._render_html(summaries, send_date)
        text_body = self._render_text(summaries, send_date)

        self._send_smtp(subject, html_body, text_body, retry=3)

    def _render_html(self, summaries: list[Summary], send_date: datetime) -> str:
        tmpl = self._jinja.get_template("email.html")
        return tmpl.render(summaries=summaries, send_date=send_date)

    def _render_text(self, summaries: list[Summary], send_date: datetime) -> str:
        tmpl = self._jinja.get_template("email.txt")
        return tmpl.render(summaries=summaries, send_date=send_date)

    def _send_smtp(
        self,
        subject: str,
        html_body: str,
        text_body: str,
        retry: int = 3,
    ) -> None:
        recipients = self._settings.recipient_emails
        if not recipients:
            log.warning("mailer.skip.no_recipients")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._settings.smtp_user
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        last_exc: Exception | None = None
        for attempt in range(retry):
            try:
                with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(self._settings.smtp_user, self._settings.smtp_password)
                    smtp.sendmail(self._settings.smtp_user, recipients, msg.as_string())
                log.info(
                    "mailer.sent",
                    recipients=recipients,
                    subject=subject,
                )
                return
            except smtplib.SMTPException as e:
                last_exc = e
                wait = 2 ** attempt
                log.warning(
                    "mailer.retry",
                    attempt=attempt + 1,
                    wait=wait,
                    error=str(e),
                )
                time.sleep(wait)

        raise RuntimeError(f"SMTP 발송 실패 (최대 재시도 초과): {last_exc}") from last_exc
