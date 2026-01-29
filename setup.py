from setuptools import setup
import os
import glob

APP = ["src/gui.py"]

# Include llama.cpp binaries if they exist (built by CI)
bin_files = []
if os.path.exists("bin"):
    bin_files = glob.glob("bin/llama-cli-*")

DATA_FILES = [
    ("bin", bin_files) if bin_files else ("bin", []),
]

OPTIONS = {
    "argv_emulation": True,
    "iconfile": "app_icon.icns",
    "plist": {
        "LSUIElement": True,  # Set to True for background agent
        "CFBundleName": "EmailDownloader",
        "CFBundleDisplayName": "Email Downloader",
        "CFBundleGetInfoString": "Downloads and classifies email attachments",
        "CFBundleIdentifier": "com.anike.emaildownloader",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
    },
    "packages": [
        "imap_tools",
        "yaml",
        "customtkinter",
        "rumps",
        "google_auth_oauthlib",
        "googleapiclient",
        "requests",
        "urllib3",
        "dateutil",
    ],
    "excludes": [
        "PyInstaller",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "pytest",
        "pytest_mock",
        "test",
        "tests",
        "numpy.tests",
        "setuptools._vendor",
    ],
    "includes": [
        "os",
        "sys",
        "logging",
        "threading",
        "json",
        "datetime",
        "pathlib",
        "sqlite3",
        "pickle",
        "re",
        "tempfile",
        "shutil",
        "subprocess",
        "argparse",
        "platform",
        "tarfile",
        "google.auth",
        "google.auth.transport.requests",
        "google.oauth2.credentials",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

