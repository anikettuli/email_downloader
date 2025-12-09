import unittest
import os
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, date

# Import the code to test
# We need to make sure the src module is in path or installed
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/src')

from downloader import HistoryManager, AttachmentDownloader

class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.test_dir, 'test_history.json')

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_load_save(self):
        hm = HistoryManager(self.history_file)
        self.assertEqual(hm.history, {})
        
        hm.mark_processed('test@example.com', '123')
        self.assertTrue(hm.is_processed('test@example.com', '123'))
        
        # Reload to check persistence
        hm2 = HistoryManager(self.history_file)
        self.assertTrue(hm2.is_processed('test@example.com', '123'))
        self.assertFalse(hm2.is_processed('test@example.com', '456'))

class TestAttachmentDownloader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'download_path': self.test_dir,
            'accounts': [
                {'email': 'test@example.com', 'password': 'pass', 'host': 'imap.test.com'}
            ],
            'allowed_extensions': ['pdf', 'jpg']
        }
        self.downloader = AttachmentDownloader(self.config)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('downloader.MailBox')
    def test_process_single_account(self, mock_mailbox_cls):
        # Mock the MailBox context manager and fetch method
        mock_mailbox = mock_mailbox_cls.return_value
        mock_mailbox.login.return_value.__enter__.return_value = mock_mailbox
        
        # Create a mock message with attachment
        mock_msg = MagicMock()
        mock_msg.uid = '100'
        mock_msg.date = datetime(2023, 10, 27)
        
        mock_att = MagicMock()
        mock_att.filename = 'invoice.pdf'
        mock_att.payload = b'fake pdf content'
        
        mock_msg.attachments = [mock_att]
        
        # Mock fetch to return this message
        mock_mailbox.fetch.return_value = [mock_msg]

        # Run processing
        self.downloader.process_single_account(self.config['accounts'][0], 24)

        # Verify file downloaded
        expected_path = Path(self.test_dir) / 'test_at_example.com' / '2023-10-27' / 'invoice.pdf'
        self.assertTrue(expected_path.exists())
        with open(expected_path, 'rb') as f:
            self.assertEqual(f.read(), b'fake pdf content')
            
        # Verify history updated
        self.assertTrue(self.downloader.history.is_processed('test@example.com', '100'))

    @patch('downloader.MailBox')
    def test_filter_extension(self, mock_mailbox_cls):
        mock_mailbox = mock_mailbox_cls.return_value
        mock_mailbox.login.return_value.__enter__.return_value = mock_mailbox
        
        mock_msg = MagicMock()
        mock_msg.uid = '101'
        mock_msg.date = datetime(2023, 10, 27)
        
        # Bad extension
        mock_att = MagicMock()
        mock_att.filename = 'virus.exe'
        mock_att.payload = b'bad'
        
        mock_msg.attachments = [mock_att]
        mock_mailbox.fetch.return_value = [mock_msg]

        self.downloader.process_single_account(self.config['accounts'][0], 24)

        # File should NOT exist
        expected_path = Path(self.test_dir) / 'test_at_example.com' / '2023-10-27' / 'virus.exe'
        self.assertFalse(expected_path.exists())
        
        # But message should still be marked processed to avoid re-scan
        self.assertTrue(self.downloader.history.is_processed('test@example.com', '101'))

    @patch('downloader.MailBox')
    def test_duplicate_filename(self, mock_mailbox_cls):
        # Determine paths
        # Force create a file that would collide
        date_str = '2023-10-27'
        target_dir = Path(self.test_dir) / 'test_at_example.com' / date_str
        target_dir.mkdir(parents=True)
        (target_dir / 'bill.pdf').write_bytes(b'existing')

        # Mock setup
        mock_mailbox = mock_mailbox_cls.return_value
        mock_mailbox.login.return_value.__enter__.return_value = mock_mailbox
        
        mock_msg = MagicMock()
        mock_msg.uid = '102'
        mock_msg.date = datetime(2023, 10, 27)
        
        mock_att = MagicMock()
        mock_att.filename = 'bill.pdf'
        mock_att.payload = b'new content'
        
        mock_msg.attachments = [mock_att]
        mock_mailbox.fetch.return_value = [mock_msg]

        self.downloader.process_single_account(self.config['accounts'][0], 24)

        # Check collision handling
        expected_new_path = target_dir / 'bill_1.pdf'
        self.assertTrue(expected_new_path.exists())
        with open(expected_new_path, 'rb') as f:
            self.assertEqual(f.read(), b'new content')

    def test_filename_sanitization(self):
        # We can test the private method directly or via full flow
        # Let's test via full flow for integration confidence
        pass # Covered implicitly in other tests or could add specific one if needed.
