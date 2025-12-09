from setuptools import setup
import os
import glob

APP = ['src/gui.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'app_icon.icns', 
    'plist': {
        'LSUIElement': False, # Standard app window
        'CFBundleName': 'EmailDownloader',
        'CFBundleDisplayName': 'Email Downloader',
        'CFBundleGetInfoString': "Downloads email attachments",
        'CFBundleIdentifier': "com.anike.emaildownloader",
        'CFBundleVersion': "0.1.0",
        'CFBundleShortVersionString': "0.1.0",
        'NSHighResolutionCapable': True,
    },
    'packages': [
        'imap_tools', 'yaml', 'customtkinter', 'PIL', 
        'google.auth', 'google_auth_oauthlib', 'googleapiclient',
        'google.auth.transport.requests', 'requests', 'urllib3'
    ],
    'includes': ['os', 'sys', 'logging', 'threading', 'json', 'datetime', 'pathlib'],
    'excludes': ['tkinter'], # customtkinter uses its own or system tk, usually we include needed parts, but excludes minimalizes.
    # Actually for ctk we might need to be careful with excludes.
    # We will rely on packages.
}

# Add CustomTkinter Data Files manually if py2app misses them (it often does)
# We can't easily access the valid path here in the agent logic without hardcoding what we found,
# but on the user's mac, it will be different.
# We will use a dynamic trick in setup.py or just trust 'packages' works for ctk >= 5.
# Recent Use: ctk usually needs its JSON files.

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
