import os
import json
import time
import logging
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path
from imap_tools import MailBox, A
from typing import List, Dict, Set, Optional
from dateutil.relativedelta import relativedelta

from classifier import AttachmentClassifier

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, history_file: str):
        self.history_file = Path(history_file)
        self.history = self._load_history()

    def _load_history(self) -> Dict[str, List[str]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(
                    f"Could not decode history file {self.history_file}, starting fresh."
                )
                return {}
        return {}

    def _save_history(self):
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def is_processed(self, account: str, msg_id: str) -> bool:
        return msg_id in self.history.get(account, [])

    def mark_processed(self, account: str, msg_id: str):
        if account not in self.history:
            self.history[account] = []
        if msg_id not in self.history[account]:
            self.history[account].append(msg_id)
            self._save_history()


class AttachmentDownloader:
    def __init__(self, config: dict):
        self.config = config
        self.base_download_path = Path(
            os.path.expanduser(
                config.get("download_path", "~/Downloads/email_downloader_app")
            )
        )
        self.allowed_extensions = set(
            ext.lower() for ext in config.get("allowed_extensions", [])
        )
        self.history = HistoryManager(
            os.path.join(self.base_download_path, ".history.json")
        )

        # Initialize Classifier
        self.classifier = AttachmentClassifier()
        self.enabled_categories = set(
            config.get(
                "enabled_categories",
                ["Bills", "Receipts", "Payments", "Work Documents", "Home/Family"],
            )
        )

        # Ensure download directory exists
        self.base_download_path.mkdir(parents=True, exist_ok=True)

    def calculate_since_date(self, value: int, unit: str) -> date:
        now = datetime.now()
        if unit == "Days":
            return (now - timedelta(days=value)).date()
        elif unit == "Weeks":
            return (now - timedelta(weeks=value)).date()
        elif unit == "Months":
            return (now - relativedelta(months=value)).date()
        elif unit == "Years":
            return (now - relativedelta(years=value)).date()
        else:
            return (now - timedelta(days=value)).date()

    def process_accounts(self, value: int = None, unit: str = "Days"):
        if value is not None:
            since_date = self.calculate_since_date(value, unit)
        else:
            lookback_hours = self.config.get("lookback_hours", 24)
            since_date = (datetime.now() - timedelta(hours=lookback_hours)).date()

        sources = self.config.get("enabled_sources", ["gmail", "outlook", "apple_mail"])

        for account in self.config.get("accounts", []):
            source_type = account.get("source_type", "imap")  # default to imap
            if source_type not in sources:
                continue

            try:
                self.process_single_account(account, since_date)
            except Exception as e:
                logger.error(
                    f"Failed to process account {account.get('email', 'unknown')}: {e}"
                )

        if "apple_mail" in sources:
            try:
                # Calculate hours for applescript if needed, or just pass date
                lookback_hours = (
                    datetime.now() - datetime.combine(since_date, datetime.min.time())
                ).total_seconds() / 3600
                self.process_apple_mail(int(lookback_hours))
            except Exception as e:
                logger.error(f"Failed to process Apple Mail: {e}")

    def process_single_account(self, account: dict, since_date: date):
        email_addr = account["email"]
        password = account.get("password")
        host = account["host"]
        folders = account.get("folders", ["INBOX"])

        logger.info(f"Connecting to {host} as {email_addr}...")

        auth_mechanism = "LOGIN"
        if account.get("auth_type") == "oauth" or "gmail.com" in host:
            from gmail_auth import get_gmail_credentials

            try:
                creds_path = self.config.get("credentials_path", "credentials.json")
                token_path = self.config.get("token_path", "token.pickle")
                creds = get_gmail_credentials(creds_path, token_path)
                password = creds.token
                auth_mechanism = "XOAUTH2"
            except Exception as e:
                logger.error(f"OAuth failed for {email_addr}: {e}")
                if not password:
                    raise

        with MailBox(host).login(
            email_addr, password, auth_mechanism=auth_mechanism
        ) as mailbox:
            for folder in folders:
                logger.info(f"Scanning folder: {folder}")
                mailbox.folder.set(folder)

                for msg in mailbox.fetch(A(date_gte=since_date)):
                    if self.history.is_processed(email_addr, msg.uid):
                        continue

                    for att in msg.attachments:
                        ext = os.path.splitext(att.filename)[1].lower().replace(".", "")
                        if (
                            not self.allowed_extensions
                            or ext in self.allowed_extensions
                        ):
                            # Classification
                            classification = self.classifier.classify(
                                msg.subject, att.filename
                            )
                            category = classification.get("category", "Other")
                            reasoning = classification.get("reasoning", "")

                            logger.info(
                                f"File: {att.filename} | Category: {category} | Reasoning: {reasoning}"
                            )

                            if category in self.enabled_categories:
                                self._save_attachment(
                                    email_addr,
                                    msg.date,
                                    category,
                                    att.filename,
                                    att.payload,
                                )

                    self.history.mark_processed(email_addr, msg.uid)

    def process_apple_mail(self, lookback_hours: int):
        """
        Extracts attachments from Apple Mail via AppleScript.
        Saves attachments to the same RAG-ready structure.
        """
        if os.name != "posix" or "darwin" not in os.uname().sysname.lower():
            logger.warning("Apple Mail processing is only supported on macOS.")
            return

        logger.info(f"Scanning Apple Mail (last {lookback_hours} hours)...")

        # This AppleScript finds messages with attachments and saves them to a temporary location
        # Then we process them like IMAP attachments.
        temp_dir = Path(tempfile.gettempdir()) / "email_downloader_apple_mail"
        temp_dir.mkdir(parents=True, exist_ok=True)

        apple_script = f'''
        set lookbackDate to (current date) - ({lookback_hours} * hours)
        set tempPath to "{temp_dir.as_posix()}"
        
        tell application "Mail"
            set resultList to {{}}
            set theMessages to (messages of inbox whose date received is greater than lookbackDate)
            
            repeat with aMessage in theMessages
                set msgID to id of aMessage as string
                set msgSubject to subject of aMessage
                set msgDate to date received of aMessage
                
                -- Format date as YYYY-MM-DD HH:MM:SS
                set y to year of msgDate as integer
                set m to month of msgDate as integer
                set d to day of msgDate as integer
                set t to time string of msgDate
                set dateStr to (y as string) & "-" & (m as string) & "-" & (d as string) & " " & t
                
                repeat with anAttachment in mail attachments of aMessage
                    set attName to name of anAttachment
                    try
                        set savePath to tempPath & "/" & msgID & "_" & attName
                        save anAttachment in savePath
                        set end of resultList to (msgID & "||" & msgSubject & "||" & dateStr & "||" & attName & "||" & savePath)
                    end try
                repeat
            end repeat
            return resultList
        end tell
        '''

        try:
            # Run AppleScript
            proc = subprocess.run(
                ["osascript", "-e", apple_script], capture_output=True, text=True
            )
            if proc.returncode != 0:
                logger.error(f"AppleScript error: {proc.stderr}")
                return

            # osascript returns a comma-separated list of strings
            output = proc.stdout.strip()
            if not output:
                return

            items = output.split(", ")
            for item in items:
                parts = item.split("||")
                if len(parts) < 5:
                    continue

                msg_id, subject, date_str, filename, file_path = parts

                if self.history.is_processed("apple_mail", msg_id):
                    # Clean up temp file if we already processed this message
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue

                # Parse date
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    dt = datetime.now()

                # Classification
                classification = self.classifier.classify(subject, filename)
                category = classification.get("category", "Other")

                if category in self.enabled_categories:
                    with open(file_path, "rb") as f:
                        payload = f.read()

                    self._save_attachment("apple_mail", dt, category, filename, payload)

                # Clean up and mark history
                if os.path.exists(file_path):
                    os.remove(file_path)
                self.history.mark_processed("apple_mail", msg_id)

        except Exception as e:
            logger.error(f"Apple Mail processing error: {e}")
        finally:
            if temp_dir.exists():
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    def _save_attachment(
        self,
        account_name: str,
        date_obj: datetime,
        category: str,
        filename: str,
        payload: bytes,
    ):
        # RAG-Ready Structure: [download_path]/[Category]/[Year]/[Month]/[Filename]
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%m")

        target_dir = self.base_download_path / category / year / month
        target_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        clean_filename = "".join(
            [
                c
                for c in filename
                if c.isalpha() or c.isdigit() or c in (" ", ".", "_", "-")
            ]
        ).strip()

        filepath = target_dir / clean_filename
        counter = 1
        while filepath.exists():
            name, ext = os.path.splitext(clean_filename)
            filepath = target_dir / f"{name}_{counter}{ext}"
            counter += 1

        logger.info(f"Saving {clean_filename} to {target_dir}")
        with open(filepath, "wb") as f:
            f.write(payload)
