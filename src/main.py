import os
import sys
import yaml
import logging
import argparse
from pathlib import Path

# Add src to path if running directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from downloader import AttachmentDownloader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_config(config_path: str):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Email Attachment Downloader")
    parser.add_argument('--config', '-c', default='config.yaml', help='Path to config file')
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        # Look in current dir or parent dir (common if running from src)
        possible_paths = [
            Path.cwd() / args.config,
            Path.cwd().parent / args.config,
            Path(__file__).parent.parent / args.config
        ]
        
        found = False
        for p in possible_paths:
            if p.exists():
                config_path = p
                found = True
                break
        
        if not found:
            logger.error(f"Config file not found: {args.config}")
            logger.info("Please copy config.template.yaml to config.yaml and edit it.")
            sys.exit(1)

    logger.info(f"Using config: {config_path}")
    config = load_config(config_path)
    
    try:
        downloader = AttachmentDownloader(config)
        downloader.process_accounts()
        logger.info("Download cycle completed successfully.")
    except Exception as e:
        logger.exception("An error occurred during execution")
        sys.exit(1)

if __name__ == "__main__":
    main()
