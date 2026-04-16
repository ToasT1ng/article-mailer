"""Mailer 테스트."""
import smtplib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.mailer import Mailer


class TestMailer:
    def test_send_calls_smtp(self, test_settings, sample_summary):
        """SMTP 발송이 올바르게 호출되는지 확인."""
        mock_smtp_instance = MagicMock()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(
                return_value=mock_smtp_instance
            )
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            mailer = Mailer(test_settings)
            mailer.send([sample_summary], send_date=datetime(2026, 4, 14, tzinfo=timezone.utc))

        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            test_settings.smtp_user, test_settings.smtp_password
        )
        mock_smtp_instance.sendmail.assert_called_once()

        # 발송 인자 확인
        args = mock_smtp_instance.sendmail.call_args[0]
        assert test_settings.smtp_user == args[0]
        assert test_settings.recipient_list == args[1]

    def test_send_subject_format(self, test_settings, sample_summary):
        """이메일 제목 형식 확인."""
        captured_msg = {}

        def capture_sendmail(from_addr, to_addrs, msg_string):
            captured_msg["msg"] = msg_string

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.sendmail.side_effect = capture_sendmail

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(
                return_value=mock_smtp_instance
            )
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            mailer = Mailer(test_settings)
            mailer.send(
                [sample_summary],
                send_date=datetime(2026, 4, 14, tzinfo=timezone.utc),
            )

        assert "[AI 데일리] 2026-04-14" in captured_msg["msg"]
        assert "1선" in captured_msg["msg"]

    def test_send_skips_when_no_summaries(self, test_settings):
        """요약 없을 때 발송 스킵."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mailer = Mailer(test_settings)
            mailer.send([])
        mock_smtp_cls.assert_not_called()

    def test_send_retries_on_smtp_error(self, test_settings, sample_summary):
        """SMTP 오류 시 재시도."""
        call_count = 0

        def fail_twice(host, port):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=m)
            m.__exit__ = MagicMock(return_value=False)
            if call_count < 3:
                m.sendmail.side_effect = smtplib.SMTPException("Temporary error")
            return m

        with patch("smtplib.SMTP", side_effect=fail_twice):
            with patch("time.sleep"):  # sleep은 스킵
                mailer = Mailer(test_settings)
                mailer.send([sample_summary])

        assert call_count == 3  # 1회 실패 + 2회 재시도 = 3회

    def test_html_template_renders_importance(self, test_settings, sample_summary):
        """HTML 템플릿에 중요도가 렌더링되는지 확인."""
        mailer = Mailer(test_settings)
        html = mailer._render_html(
            [sample_summary], datetime(2026, 4, 14, tzinfo=timezone.utc)
        )
        assert "중요도 상" in html
        assert sample_summary.article.title in html
        assert sample_summary.one_liner in html
