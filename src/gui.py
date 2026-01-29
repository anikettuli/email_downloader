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
        self.geometry("1000x700")

        # macOS native feel: hidden title bar sometimes, but for this app standard is fine.
        # We'll use a consistent padding strategy.

        # Load config
        self.config = self._load_initial_config()
        self.downloader = AttachmentDownloader(self.config) if self.config else None

        self._create_ui()

        # Menu bar integration
        self._setup_menubar()

    def _setup_menubar(self):
        if sys.platform == "darwin":
            try:
                import rumps

                class MenuBarApp(rumps.App):
                    def __init__(self, parent):
                        super(MenuBarApp, self).__init__("📧", quit_button=None)
                        self.parent = parent
                        self.menu = ["Show Dashboard", "Run Scan Now", "Quit App"]

                    @rumps.clicked("Show Dashboard")
                    def show_app(self, _):
                        self.parent.after(0, self.parent.deiconify)
                        self.parent.after(0, self.parent.lift)
                        self.parent.after(0, self.parent.focus_force)

                    @rumps.clicked("Run Scan Now")
                    def run_scan(self, _):
                        self.parent.start_download_thread()

                    @rumps.clicked("Quit App")
                    def quit_app(self, _):
                        self.parent.on_closing()

                self.menubar = MenuBarApp(self)
                threading.Thread(target=self.menubar.run, daemon=True).start()
            except ImportError:
                logger.warning("rumps not installed, menu bar disabled.")

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
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(10, weight=1)  # Spacer

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Email\nDownloader",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Sources Selection
        self.sources_label = ctk.CTkLabel(
            self.sidebar_frame, text="Sources", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.sources_label.grid(row=1, column=0, padx=25, pady=(10, 5), sticky="w")

        self.gmail_var = ctk.BooleanVar(
            value="gmail" in self.config.get("enabled_sources", [])
        )
        self.gmail_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Gmail", variable=self.gmail_var
        )
        self.gmail_cb.grid(row=2, column=0, padx=30, pady=5, sticky="w")

        self.outlook_var = ctk.BooleanVar(
            value="outlook" in self.config.get("enabled_sources", [])
        )
        self.outlook_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Outlook", variable=self.outlook_var
        )
        self.outlook_cb.grid(row=3, column=0, padx=30, pady=5, sticky="w")

        self.apple_var = ctk.BooleanVar(
            value="apple_mail" in self.config.get("enabled_sources", [])
        )
        self.apple_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Apple Mail", variable=self.apple_var
        )
        self.apple_cb.grid(row=4, column=0, padx=30, pady=5, sticky="w")

        # Categories
        self.cats_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Categories",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.cats_label.grid(row=5, column=0, padx=25, pady=(20, 5), sticky="w")

        self.cat_vars = {}
        all_cats = ["Bills", "Receipts", "Payments", "Work Documents", "Home/Family"]
        for i, cat in enumerate(all_cats):
            var = ctk.BooleanVar(value=cat in self.config.get("enabled_categories", []))
            cb = ctk.CTkCheckBox(self.sidebar_frame, text=cat, variable=var)
            cb.grid(row=6 + i, column=0, padx=30, pady=2, sticky="w")
            self.cat_vars[cat] = var

        # Lookback Options
        self.lookback_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Lookback",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lookback_label.grid(row=11, column=0, padx=25, pady=(10, 5), sticky="w")

        self.lookback_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.lookback_frame.grid(row=12, column=0, padx=20, pady=5, sticky="ew")

        self.lookback_value = ctk.CTkEntry(self.lookback_frame, width=60)
        self.lookback_value.insert(0, "1")
        self.lookback_value.pack(side="left", padx=(0, 5))

        self.lookback_unit = ctk.CTkComboBox(
            self.lookback_frame, values=["Days", "Weeks", "Months", "Years"], width=100
        )
        self.lookback_unit.set("Weeks")
        self.lookback_unit.pack(side="left")

        # System Actions
        self.auth_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="Add Account",
            command=self.do_oauth,
            fg_color="transparent",
            border_width=1,
        )
        self.auth_btn.grid(row=13, column=0, padx=20, pady=(20, 5), sticky="ew")

        self.open_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="Downloads Folder",
            command=self.open_folder,
            fg_color="transparent",
            border_width=1,
        )
        self.open_btn.grid(row=14, column=0, padx=20, pady=5, sticky="ew")

        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=30, pady=30, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        self.welcome_label = ctk.CTkLabel(
            self.header_frame,
            text="Extraction Status",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.welcome_label.pack(side="left")

        # Custom themed log area
        self.log_area = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Menlo", size=12),
            corner_radius=10,
            border_width=1,
            border_color="#333333",
        )
        self.log_area.grid(row=1, column=0, sticky="nsew")

        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        self.footer_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.footer_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        self.progress_bar.set(0)

        self.fetch_btn = ctk.CTkButton(
            self.footer_frame,
            text="SCAN NOW",
            height=45,
            width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_download_thread,
            corner_radius=20,
        )
        self.fetch_btn.grid(row=0, column=1)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        # Instead of quitting, just withdraw if menubar is active
        if hasattr(self, "menubar"):
            self.withdraw()
        else:
            self.destroy()
            sys.exit(0)

    def log(self, message):
        self.log_area.insert("end", f"› {message}\n")
        self.log_area.see("end")

    def do_oauth(self):
        self.log("Opening Authentication flow...")
        # (existing logic remains)
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
            self.log("Account added successfully!")
        except Exception as e:
            self.log(f"Auth failed: {e}")

    def start_download_thread(self):
        val = self.lookback_value.get()
        unit = self.lookback_unit.get()
        if not val.isdigit():
            self.log("Error: Lookback value must be a number.")
            return

        self.fetch_btn.configure(state="disabled")
        self.progress_bar.set(0)

        # Start model check/download thread first
        threading.Thread(
            target=self._ensure_model_and_run, args=(int(val), unit), daemon=True
        ).start()

    def _ensure_model_and_run(self, value, unit):
        try:
            # Initialize downloader/classifier if not done
            if not self.downloader:
                self.downloader = AttachmentDownloader(self.config)

            # Check model
            if not os.path.exists(self.downloader.classifier.model_path):
                self.log("Model missing. Starting download (approx 180MB)...")
                self.progress_bar.configure(mode="determinate")

                def update_progress(p):
                    self.after(0, lambda: self.progress_bar.set(p))

                success = self.downloader.classifier.ensure_model_exists(
                    progress_callback=update_progress
                )
                if not success:
                    self.log("Error: Failed to download classification model.")
                    return
                self.log("Model downloaded and loaded.")

            # Update config
            enabled_sources = []
            if self.gmail_var.get():
                enabled_sources.append("gmail")
            if self.outlook_var.get():
                enabled_sources.append("outlook")
            if self.apple_var.get():
                enabled_sources.append("apple_mail")
            self.config["enabled_sources"] = enabled_sources
            self.config["enabled_categories"] = [
                cat for cat, var in self.cat_vars.items() if var.get()
            ]
            self.downloader.config = self.config

            # Run actual download
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            self.log(f"Starting Scan: {value} {unit} lookback")
            self._run_download(value, unit)

        except Exception as e:
            self.log(f"Setup Error: {e}")
            self.fetch_btn.configure(state="normal")

    def _run_download(self, value, unit):
        try:

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

            self.downloader.process_accounts(value=value, unit=unit)
            self.log("Success: Scan complete.")
        except Exception as e:
            self.log(f"Process Error: {e}")
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
