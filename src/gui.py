import os
import sys
import threading
import logging
import customtkinter as ctk
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from downloader import AttachmentDownloader
from gmail_auth import get_gmail_credentials
from main import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Premium Palette
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class EmailDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Email Attachment Downloader")
        self.geometry("900x600")

        # Load config
        self.config = self._load_initial_config()
        self.downloader = AttachmentDownloader(self.config) if self.config else None

        self._create_ui()

    def _load_initial_config(self):
        paths = [
            os.path.expanduser("~/.email_downloader_config.yaml"),
            "config.yaml",
            "../config.yaml",
        ]
        for p in paths:
            if os.path.exists(p):
                return load_config(p)

        return {
            "download_path": "~/Downloads/email_downloader_app",
            "accounts": [],
            "lookback_hours": 168,
            "enabled_sources": ["gmail", "outlook", "apple_mail"],
            "enabled_categories": [
                "Bills",
                "Receipts",
                "Payments",
                "Work Documents",
                "Home/Family",
            ],
        }

    def _create_ui(self):
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Email\nDownloader",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Sources Selection
        self.sources_label = ctk.CTkLabel(
            self.sidebar_frame, text="Mail Sources:", font=ctk.CTkFont(weight="bold")
        )
        self.sources_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")

        self.gmail_var = ctk.BooleanVar(
            value="gmail" in self.config.get("enabled_sources", [])
        )
        self.gmail_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Gmail", variable=self.gmail_var
        )
        self.gmail_cb.grid(row=2, column=0, padx=20, pady=5, sticky="w")

        self.outlook_var = ctk.BooleanVar(
            value="outlook" in self.config.get("enabled_sources", [])
        )
        self.outlook_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Outlook", variable=self.outlook_var
        )
        self.outlook_cb.grid(row=3, column=0, padx=20, pady=5, sticky="w")

        self.apple_var = ctk.BooleanVar(
            value="apple_mail" in self.config.get("enabled_sources", [])
        )
        self.apple_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Apple Mail", variable=self.apple_var
        )
        self.apple_cb.grid(row=4, column=0, padx=20, pady=5, sticky="w")

        # Categories Checklist
        self.cats_label = ctk.CTkLabel(
            self.sidebar_frame, text="Categories:", font=ctk.CTkFont(weight="bold")
        )
        self.cats_label.grid(row=5, column=0, padx=20, pady=(20, 0), sticky="w")

        self.cat_vars = {}
        all_cats = ["Bills", "Receipts", "Payments", "Work Documents", "Home/Family"]
        for i, cat in enumerate(all_cats):
            var = ctk.BooleanVar(value=cat in self.config.get("enabled_categories", []))
            cb = ctk.CTkCheckBox(self.sidebar_frame, text=cat, variable=var)
            cb.grid(row=6 + i, column=0, padx=20, pady=2, sticky="w")
            self.cat_vars[cat] = var

        # Actions
        self.auth_btn = ctk.CTkButton(
            self.sidebar_frame, text="Sign in (Gmail)", command=self.do_oauth
        )
        self.auth_btn.grid(row=12, column=0, padx=20, pady=10)

        self.open_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="Open Folder",
            command=self.open_folder,
            fg_color="transparent",
            border_width=2,
        )
        self.open_btn.grid(row=13, column=0, padx=20, pady=10)

        self.days_label = ctk.CTkLabel(
            self.sidebar_frame, text="Lookback Days:", anchor="w"
        )
        self.days_label.grid(row=14, column=0, padx=20, pady=(10, 0))
        self.days_entry = ctk.CTkEntry(self.sidebar_frame)
        self.days_entry.insert(0, "7")
        self.days_entry.grid(row=15, column=0, padx=20, pady=(0, 20))

        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.welcome_label = ctk.CTkLabel(
            self.main_frame,
            text="Classification Log",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.welcome_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        self.log_area = ctk.CTkTextbox(self.main_frame, width=500)
        self.log_area.grid(row=1, column=0, sticky="nsew")

        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        self.progress_bar.set(0)

        self.fetch_btn = ctk.CTkButton(
            self.main_frame,
            text="START PROCESSING",
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.start_download_thread,
        )
        self.fetch_btn.grid(row=3, column=0, sticky="ew", pady=(20, 0))

    def log(self, message):
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")

    def do_oauth(self):
        self.log("Starting Gmail Sign In...")
        try:
            creds_path = self.config.get("credentials_path", "credentials.json")
            if not os.path.exists(creds_path):
                self.log(f"Error: {creds_path} not found.")
                return
            threading.Thread(
                target=self._run_oauth, args=(creds_path,), daemon=True
            ).start()
        except Exception as e:
            self.log(f"Error: {e}")

    def _run_oauth(self, creds_path):
        try:
            get_gmail_credentials(creds_path)
            self.log("Sign in successful!")
        except Exception as e:
            self.log(f"Sign in failed: {e}")

    def start_download_thread(self):
        days = self.days_entry.get()
        if not days.isdigit():
            self.log("Error: Days must be a number.")
            return

        # Update config from UI
        enabled_sources = []
        if self.gmail_var.get():
            enabled_sources.append("gmail")
        if self.outlook_var.get():
            enabled_sources.append("outlook")
        if self.apple_var.get():
            enabled_sources.append("apple_mail")
        self.config["enabled_sources"] = enabled_sources

        enabled_cats = [cat for cat, var in self.cat_vars.items() if var.get()]
        self.config["enabled_categories"] = enabled_cats

        self.fetch_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        self.log(f"Scanning sources: {', '.join(enabled_sources)}")
        self.log(f"Target categories: {', '.join(enabled_cats)}")

        threading.Thread(
            target=self._run_download, args=(int(days),), daemon=True
        ).start()

    def _run_download(self, days):
        try:
            # Re-init downloader with fresh UI settings
            self.downloader = AttachmentDownloader(self.config)

            # Setup logging redirect to UI
            class UIHandler(logging.Handler):
                def __init__(self, log_func):
                    super().__init__()
                    self.log_func = log_func

                def emit(self, record):
                    msg = self.format(record)
                    self.log_func(msg)

            ui_handler = UIHandler(self.log)
            ui_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger("downloader").addHandler(ui_handler)
            logging.getLogger("classifier").addHandler(ui_handler)

            self.downloader.process_accounts(lookback_days=days)
            self.log("Processing complete!")

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.progress_bar.stop()
            self.progress_bar.set(1)
            self.fetch_btn.configure(state="normal")

    def open_folder(self):
        path = os.path.expanduser(
            self.config.get("download_path", "~/Downloads/email_downloader_app")
        )
        if sys.platform == "darwin":
            os.system(f'open "{path}"')
        elif sys.platform == "linux":
            os.system(f'xdg-open "{path}"')
        else:
            os.system(f'explorer "{path}"')


if __name__ == "__main__":
    app = EmailDownloaderApp()
    app.mainloop()
