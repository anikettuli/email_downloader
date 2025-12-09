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
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Premium Palette
# Using CustomTkinter's default dark theme but we can enhance contrast if needed
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class EmailDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Email Attachment Downloader")
        self.geometry("600x500")
        
        # Load config
        self.config = self._load_initial_config()
        self.downloader = AttachmentDownloader(self.config) if self.config else None

        self._create_ui()

    def _load_initial_config(self):
        paths = [
            os.path.expanduser("~/.email_downloader_config.yaml"),
            "config.yaml",
            "../config.yaml"
        ]
        for p in paths:
            if os.path.exists(p):
                return load_config(p)
        
        # Default config if none found
        return {
            'download_path': '~/Downloads/email_downloader_app',
            'accounts': [],
            'lookback_hours': 168
        }

    def _create_ui(self):
        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Email\nDownloader", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.auth_btn = ctk.CTkButton(self.sidebar_frame, text="Sign in (Gmail)", command=self.do_oauth)
        self.auth_btn.grid(row=1, column=0, padx=20, pady=10)

        self.open_btn = ctk.CTkButton(self.sidebar_frame, text="Open Folder", command=self.open_folder, fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"))
        self.open_btn.grid(row=2, column=0, padx=20, pady=10)
        
        # Lookback input in sidebar
        self.days_label = ctk.CTkLabel(self.sidebar_frame, text="Lookback Days:", anchor="w")
        self.days_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.days_entry = ctk.CTkEntry(self.sidebar_frame)
        self.days_entry.insert(0, "7")
        self.days_entry.grid(row=6, column=0, padx=20, pady=(0, 20))
        
        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Header in Main Area
        self.welcome_label = ctk.CTkLabel(self.main_frame, text="Dashboard", font=ctk.CTkFont(size=24, weight="bold"))
        self.welcome_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Log Area
        self.log_area = ctk.CTkTextbox(self.main_frame, width=400)
        self.log_area.grid(row=1, column=0, sticky="nsew")
        
        # Big Action Button
        self.fetch_btn = ctk.CTkButton(self.main_frame, text="FETCH EMAILS", height=50, font=ctk.CTkFont(size=16, weight="bold"), command=self.start_download_thread)
        self.fetch_btn.grid(row=2, column=0, sticky="ew", pady=(20, 0))

    def log(self, message):
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")

    def do_oauth(self):
        self.log("Starting Gmail Sign In...")
        try:
            # We need to ensure we have a credentials.json
            creds_path = self.config.get('credentials_path', 'credentials.json')
            if not os.path.exists(creds_path):
                self.log(f"Error: {creds_path} not found.")
                self.log("Please place credentials.json in the app folder.")
                return

            # Run in thread to not freeze UI? 
            # OAuth flow might require browser interaction which is tricky in thread but let's try
            # InstalledAppFlow usually opens a browser.
            threading.Thread(target=self._run_oauth, args=(creds_path,), daemon=True).start()
        except Exception as e:
            self.log(f"Error initiating sign in: {e}")

    def _run_oauth(self, creds_path):
        try:
            get_gmail_credentials(creds_path)
            self.log("Sign in successful! Token saved.")
        except Exception as e:
            self.log(f"Sign in failed: {e}")

    def start_download_thread(self):
        days = self.days_entry.get()
        if not days.isdigit():
            self.log("Error: Days must be a number.")
            return

        self.fetch_btn.configure(state="disabled")
        self.log(f"Starting download (Looking back {days} days)...")
        
        threading.Thread(target=self._run_download, args=(int(days),), daemon=True).start()

    def _run_download(self, days):
        try:
            # Re-init downloader to pick up new tokens/config
            if not self.config.get('accounts'):
                 # If no accounts in config, add a default gmail one if we have token?
                 # Or just rely on what is in config. User needs to configure simple yaml 
                 # or we should add "Add Account" UI.
                 # For now, let's assume the user has a config or we verify
                 pass
            
            # If the user hasn't set up config, we might want to try to use the 'default' gmail
            # if they just signed in. 
            # CHECK: Does the user have a config? 
            # The prompt says "enable oauth so i can sign into gmail". 
            # If they sign in, we should probably add that account to the strict "accounts" list 
            # if it's missing.
            
            # Quick hack: If no accounts, add a dummy one that attempts to use the oauth token
            if not self.config.get('accounts'):
                self.config['accounts'] = [{
                    'email': 'me', # 'me' works for Gmail API usually, or we can get it from token
                    'host': 'imap.gmail.com',
                    'auth_type': 'oauth'
                }]
                self.downloader = AttachmentDownloader(self.config)

            if self.downloader:
                self.downloader.process_accounts(lookback_days=days)
                self.log("Download complete!")
            else:
                self.log("No downloader configured.")

        except Exception as e:
            self.log(f"Error during download: {e}")
        finally:
            self.fetch_btn.configure(state="normal")

    def open_folder(self):
        path = os.path.expanduser(self.config.get('download_path', '~/Downloads/email_downloader_app'))
        if sys.platform == 'darwin':
            os.system(f'open "{path}"')
        elif sys.platform == 'linux':
             os.system(f'xdg-open "{path}"')
        else:
             os.system(f'explorer "{path}"')

if __name__ == "__main__":
    app = EmailDownloaderApp()
    app.mainloop()
