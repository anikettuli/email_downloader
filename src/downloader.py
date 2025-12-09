import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from imap_tools import MailBox, A
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

class HistoryManager:
    def __init__(self, history_file: str):
        self.history_file = Path(history_file)
        self.history = self._load_history()

    def _load_history(self) -> Dict[str, List[str]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not decode history file {self.history_file}, starting fresh.")
                return {}
        return {}

    def _save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def is_processed(self, account: str, msg_id: str) -> bool:
        return msg_id in self.history.get(account, [])

    def mark_processed(self, account: str, msg_id: str):
        if account not in self.history:
            self.history[account] = []
        # optimization: limit history size if needed, but for text IDs it's fine for a while
        if msg_id not in self.history[account]:
            self.history[account].append(msg_id)
            self._save_history()


class AttachmentDownloader:
    def __init__(self, config: dict):
        self.config = config
        self.base_download_path = Path(os.path.expanduser(config.get('download_path', '~/Downloads/email_downloader_app')))
        self.allowed_extensions = set(ext.lower() for ext in config.get('allowed_extensions', []))
        self.history = HistoryManager(os.path.join(self.base_download_path, '.history.json'))
        
        # Ensure download directory exists
        self.base_download_path.mkdir(parents=True, exist_ok=True)

    def process_accounts(self, lookback_days: int = None):
        # Allow override of lookback days
        if lookback_days is not None:
            lookback_hours = lookback_days * 24
        else:
            lookback_hours = self.config.get('lookback_hours', 24)
        
        for account in self.config.get('accounts', []):
            try:
                self.process_single_account(account, lookback_hours)
            except Exception as e:
                logger.error(f"Failed to process account {account.get('email', 'unknown')}: {e}")

    def process_single_account(self, account: dict, lookback_hours: int):
        email_addr = account['email']
        password = account['password']
        host = account['host']
        folders = account.get('folders', ['INBOX'])

        logger.info(f"Connecting to {host} as {email_addr}...")
        
        # Handle Gmail OAuth
        if account.get('auth_type') == 'oauth' or 'gmail.com' in host:
            # We assume if it is gmail, we try oauth if password is not set or if explicitly requested
            # For now, let's explicitly check for a token or credentials
            from gmail_auth import get_gmail_credentials
            try:
                creds_path = self.config.get('credentials_path', 'credentials.json')
                token_path = self.config.get('token_path', 'token.pickle')
                creds = get_gmail_credentials(creds_path, token_path)
                password = creds.token # Use access token as password
                auth_mechanism = 'XOAUTH2'
            except Exception as e:
                logger.error(f"OAuth failed for {email_addr}: {e}")
                # Fallback to password if provided, else raise
                if not password:
                    raise
                auth_mechanism = 'LOGIN'
        else:
            auth_mechanism = 'LOGIN'

        with MailBox(host).login(email_addr, password, auth_mechanism=auth_mechanism) as mailbox:
            for folder in folders:
                logger.info(f"Scanning folder: {folder}")
                mailbox.folder.set(folder)
                
                # Fetch messages
                # Criteria: Since specific date to filter periodically
                since_date = (datetime.now() - timedelta(hours=lookback_hours)).date()
                
                # Fetch unread and read messages, we filter by ID
                for msg in mailbox.fetch(A(date_gte=since_date)):
                    if self.history.is_processed(email_addr, msg.uid):
                        continue
                    
                    if not msg.attachments:
                        # No attachments, just mark as seen to avoid re-check loop if we were only checking unread?
                        # Actually we check by date, so we will re-scan, but history check prevents heavy lifting.
                        # Storing ID for non-attachment emails might bloat history, but it's "safer" to avoid re-processing.
                        # Let's only mark if we successfully processed or decided it's irrelevant.
                        pass
                    
                    has_downloaded = False
                    for att in msg.attachments:
                        ext = os.path.splitext(att.filename)[1].lower().replace('.', '')
                        if not self.allowed_extensions or ext in self.allowed_extensions:
                            self._save_attachment(email_addr, msg, att)
                            has_downloaded = True
                    
                    # Mark as processed regardless of whether we found attachments, 
                    # so we don't re-scan this specific message UID in future runs.
                    self.history.mark_processed(email_addr, msg.uid)

    def _save_attachment(self, email_addr: str, msg, att):
        # Create folder structure: base / email / YYYY-MM-DD / filename
        date_str = msg.date.strftime('%Y-%m-%d')
        safe_email = email_addr.replace('@', '_at_')
        target_dir = self.base_download_path / safe_email / date_str
        target_dir.mkdir(parents=True, exist_ok=True)

        # Handle duplicate filenames
        filename = att.filename
        # Sanitize filename
        filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).strip()
        
        filepath = target_dir / filename
        counter = 1
        while filepath.exists():
            name, ext = os.path.splitext(filename)
            filepath = target_dir / f"{name}_{counter}{ext}"
            counter += 1

        logger.info(f"Downloading {filename} from {email_addr}")
        with open(filepath, 'wb') as f:
            f.write(att.payload)
