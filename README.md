# Email Attachment Downloader

A macOS-native application that automatically downloads and classifies email attachments using a local LLM (Gemma 3).

## Features
- **Auto-Classification**: Uses a local Gemma 3 model to categorize files into Bills, Receipts, Payments, etc.
- **RAG-Ready Structure**: Organizes files into `[Category]/[Year]/[Month]/[Filename]`.
- **Multi-Source**: Supports Gmail (OAuth), Outlook, and Apple Mail.
- **Privacy First**: All classification happens locally on your machine.

## How to Build (macOS Required)

To create a native `.app` bundle:

1. **Transfer** this project folder to your Mac.
2. **Open Terminal** in the project directory.
3. **Run the build script**:
   ```bash
   bash build_app.sh
   ```
4. **Find the App**: Once finished, `EmailDownloader.app` will be on your **Desktop**.
5. **Install**: Drag `EmailDownloader.app` from your Desktop to your `/Applications` folder.

## Manual Setup / Linux

If you want to run the script manually or on Linux:

1. **Install dependencies**:
   ```bash
   bash install.sh
   ```
2. **Configure**: Copy `config.template.yaml` to `config.yaml` and add your credentials.
3. **Run**:
   ```bash
   venv/bin/python src/gui.py
   ```

## Requirements
- Python 3.10+
- macOS (for Apple Mail extraction and `.app` building)
- Internet connection (first launch only, to download the 180MB classification model)
