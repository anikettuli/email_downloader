from setuptools import setup
import os
import glob

APP = ["src/gui.py"]
DATA_FILES = []
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
        "PIL",
        "google.auth",
        "google_auth_oauthlib",
        "googleapiclient",
        "google.auth.transport.requests",
        "requests",
        "urllib3",
        "llama_cpp",
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
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
