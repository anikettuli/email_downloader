import pytest
import os
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

import sys

sys.path.append(os.path.join(os.getcwd(), "src"))

from downloader import HistoryManager, AttachmentDownloader


class TestHistoryManager:
    @pytest.fixture
    def test_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d)

    def test_load_save(self, test_dir):
        history_file = os.path.join(test_dir, "history.json")
        hm = HistoryManager(history_file)
        assert hm.history == {}

        hm.mark_processed("test@me.com", "id1")
        assert hm.is_processed("test@me.com", "id1")

        hm2 = HistoryManager(history_file)
        assert hm2.is_processed("test@me.com", "id1")


class TestAttachmentDownloader:
    @pytest.fixture
    def config(self):
        d = tempfile.mkdtemp()
        c = {
            "download_path": d,
            "accounts": [
                {
                    "email": "test@me.com",
                    "password": "pass",
                    "host": "imap.test.com",
                    "source_type": "imap",
                }
            ],
            "allowed_extensions": ["pdf"],
            "enabled_sources": ["imap"],
            "enabled_categories": ["Bills"],
        }
        yield c
        shutil.rmtree(d)

    @pytest.fixture
    def downloader(self, config):
        with patch("downloader.AttachmentClassifier"):
            return AttachmentDownloader(config)

    def test_calculate_since_date(self, downloader):
        now = datetime.now()
        assert (
            downloader.calculate_since_date(1, "Days")
            == (now - relativedelta(days=1)).date()
        )
        assert (
            downloader.calculate_since_date(2, "Weeks")
            == (now - relativedelta(weeks=2)).date()
        )
        assert (
            downloader.calculate_since_date(3, "Months")
            == (now - relativedelta(months=3)).date()
        )
        assert (
            downloader.calculate_since_date(1, "Years")
            == (now - relativedelta(years=1)).date()
        )

    @patch("downloader.MailBox")
    def test_process_single_account(self, mock_mailbox_cls, downloader, config):
        mock_mailbox = mock_mailbox_cls.return_value
        mock_mailbox.login.return_value.__enter__.return_value = mock_mailbox

        msg = MagicMock()
        msg.uid = "100"
        msg.subject = "Electric Bill"
        msg.date = datetime(2024, 1, 1)

        att = MagicMock()
        att.filename = "bill.pdf"
        att.payload = b"content"
        msg.attachments = [att]

        mock_mailbox.fetch.return_value = [msg]

        downloader.classifier.classify.return_value = {
            "category": "Bills",
            "reasoning": "Matches subject",
        }

        downloader.process_single_account(config["accounts"][0], date(2023, 12, 1))

        expected_path = (
            Path(config["download_path"]) / "Bills" / "2024" / "01" / "bill.pdf"
        )
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"content"

    @patch("downloader.MailBox")
    def test_category_filtering(self, mock_mailbox_cls, downloader, config):
        mock_mailbox = mock_mailbox_cls.return_value
        mock_mailbox.login.return_value.__enter__.return_value = mock_mailbox

        msg = MagicMock()
        msg.uid = "101"
        msg.subject = "Spam"
        msg.date = datetime(2024, 1, 1)

        att = MagicMock()
        att.filename = "spam.pdf"
        att.payload = b"junk"
        msg.attachments = [att]

        mock_mailbox.fetch.return_value = [msg]

        # Classify as something NOT in enabled_categories
        downloader.classifier.classify.return_value = {
            "category": "Other",
            "reasoning": "Unknown",
        }

        downloader.process_single_account(config["accounts"][0], date(2023, 12, 1))

        # Should NOT save
        save_path = Path(config["download_path"]) / "Other" / "2024" / "01" / "spam.pdf"
        assert not save_path.exists()


class TestClassifier:
    @patch("classifier.Llama")
    def test_classification_logic(self, mock_llama_cls):
        from classifier import AttachmentClassifier

        # Mock model file existence
        with patch("os.path.exists", return_value=True):
            classifier = AttachmentClassifier(model_path="fake.gguf")

            mock_llm = mock_llama_cls.return_value
            mock_llm.return_value = {
                "choices": [
                    {"text": '"category": "Bills", "reasoning": "Invoice found"}'}
                ]
            }

            result = classifier.classify("Your Bill", "invoice.pdf")
            assert result["category"] == "Bills"
            assert "Invoice" in result["reasoning"]

    @patch("classifier.Llama")
    def test_malformed_json_recovery(self, mock_llama_cls):
        from classifier import AttachmentClassifier

        with patch("os.path.exists", return_value=True):
            classifier = AttachmentClassifier(model_path="fake.gguf")
            mock_llm = mock_llama_cls.return_value
            # Missing braces but we add them in code
            mock_llm.return_value = {
                "choices": [
                    {"text": '"category": "Receipts", "reasoning": "Bought stuff"'}
                ]
            }

            result = classifier.classify("Store", "receipt.jpg")
            assert result["category"] == "Receipts"
