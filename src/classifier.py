import os
import logging
import json
import subprocess
import platform
import requests
import sys

logger = logging.getLogger(__name__)


class AttachmentClassifier:
    """Classifies email attachments using llama.cpp CLI with a local GGUF model."""

    # llama.cpp release version to download
    LLAMA_VERSION = "b7870"
    
    def __init__(self, model_path=None):
        # Determine base paths
        if getattr(sys, 'frozen', False):
            # Running as bundled app
            self.app_dir = os.path.dirname(sys.executable)
            self.resources_dir = os.path.join(self.app_dir, "..", "Resources")
        else:
            # Running from source
            self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.resources_dir = self.app_dir

        self.bin_dir = os.path.join(self.resources_dir, "bin")
        self.models_dir = os.path.join(self.resources_dir, "models")

        if model_path is None:
            self.model_path = os.path.join(
                self.models_dir, "gemma-3-270m-it-Q4_K_M.gguf"
            )
        else:
            self.model_path = model_path

        self.model_url = "https://huggingface.co/google/gemma-3-270m-it-GGUF/resolve/main/gemma-3-270m-it-Q4_K_M.gguf"
        
        self.categories = [
            "Bills",
            "Receipts",
            "Payments",
            "Work Documents",
            "Home/Family",
        ]

        self._llama_binary = None

    def _get_arch(self) -> str:
        """Get current CPU architecture."""
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "arm64"
        else:
            return "x64"

    def _get_llama_binary_name(self) -> str:
        """Get the llama-cli binary name for current architecture."""
        arch = self._get_arch()
        if platform.system() == "Darwin":
            return f"llama-cli-{arch}"
        elif platform.system() == "Linux":
            return "llama-cli-linux"
        else:
            return "llama-cli"

    def _get_llama_binary_path(self) -> str:
        """Get path to llama-cli binary."""
        binary_name = self._get_llama_binary_name()
        return os.path.join(self.bin_dir, binary_name)

    def _download_llama_binary(self, progress_callback=None) -> bool:
        """Download the appropriate llama-cli binary for current platform."""
        os.makedirs(self.bin_dir, exist_ok=True)
        
        arch = self._get_arch()
        system = platform.system()
        
        if system == "Darwin":
            archive_name = f"llama-{self.LLAMA_VERSION}-bin-macos-{arch}.tar.gz"
        elif system == "Linux":
            archive_name = f"llama-{self.LLAMA_VERSION}-bin-ubuntu-x64.tar.gz"
        else:
            logger.error(f"Unsupported platform: {system}")
            return False
        
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{self.LLAMA_VERSION}/{archive_name}"
        binary_path = self._get_llama_binary_path()
        
        logger.info(f"Downloading llama.cpp binary from {url}...")
        
        try:
            # Download to temp file
            import tarfile
            import tempfile
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp_file:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded / total_size * 0.8)  # 80% for download
                tmp_path = tmp_file.name
            
            # Extract llama-cli from archive
            logger.info("Extracting llama-cli binary...")
            with tarfile.open(tmp_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("llama-cli") or member.name.endswith("llama-cli.exe"):
                        member.name = os.path.basename(binary_path)
                        tar.extract(member, self.bin_dir)
                        break
            
            os.unlink(tmp_path)
            os.chmod(binary_path, 0o755)
            
            if progress_callback:
                progress_callback(1.0)
            
            logger.info(f"llama-cli installed to {binary_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download llama.cpp binary: {e}")
            return False

    def ensure_binary_exists(self, progress_callback=None) -> bool:
        """Ensure llama-cli binary is available."""
        binary_path = self._get_llama_binary_path()
        if os.path.exists(binary_path):
            return True
        return self._download_llama_binary(progress_callback)

    def ensure_model_exists(self, progress_callback=None) -> bool:
        """Downloads the model if it doesn't exist."""
        if os.path.exists(self.model_path):
            return True

        os.makedirs(self.models_dir, exist_ok=True)
        logger.info(f"Downloading model from {self.model_url}...")

        try:
            response = requests.get(self.model_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            with open(self.model_path, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded / total_size)

            logger.info("Model download complete.")
            return True
        except Exception as e:
            logger.error(f"Model download failed: {e}")
            if os.path.exists(self.model_path):
                os.remove(self.model_path)
            return False

    def is_ready(self) -> bool:
        """Check if both binary and model are available."""
        binary_path = self._get_llama_binary_path()
        return os.path.exists(binary_path) and os.path.exists(self.model_path)

    def classify(self, subject: str, filename: str) -> dict:
        """
        Classifies an email attachment based on subject and filename.
        Returns a dict with 'category' and 'reasoning'.
        """
        if not self.is_ready():
            return {"category": "Uncategorized", "reasoning": "Model or binary not available."}

        binary_path = self._get_llama_binary_path()

        # Build prompt using Gemma chat template
        prompt = f"""<start_of_turn>user
You are a helpful assistant that classifies email attachments.
Categories: {", ".join(self.categories)} or "Other".

Email Subject: {subject}
Attachment Filename: {filename}

TASK: Return ONLY a JSON object. No preamble, no markdown.
FORMAT: {{"category": "string", "reasoning": "string"}}
JSON:<end_of_turn>
<start_of_turn>model
{{"""

        try:
            # Run llama-cli
            result = subprocess.run(
                [
                    binary_path,
                    "-m", self.model_path,
                    "-p", prompt,
                    "-n", "150",  # max tokens
                    "--no-display-prompt",
                    "-c", "2048",  # context size
                    "--temp", "0.7",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.error(f"llama-cli error: {result.stderr}")
                return {"category": "Other", "reasoning": f"Inference error: {result.stderr[:100]}"}

            # Parse output - we pre-filled '{' in prompt
            response_text = "{" + result.stdout.strip()
            
            # Ensure it ends with }
            if not response_text.endswith("}"):
                response_text += "}"

            logger.info(f"Model raw output: {response_text}")

            # Find JSON in response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx : end_idx + 1]
                
                # Fix common JSON issues
                import re
                json_str = re.sub(r",\s*}", "}", json_str)

                try:
                    parsed = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try regex fallback
                    category_match = re.search(r'"category":\s*"([^"]+)"', json_str)
                    reasoning_match = re.search(r'"reasoning":\s*"([^"]+)"', json_str)
                    if category_match:
                        parsed = {
                            "category": category_match.group(1),
                            "reasoning": reasoning_match.group(1) if reasoning_match else "Parsed via regex",
                        }
                    else:
                        raise ValueError(f"Could not parse JSON: {json_str}")
            else:
                raise ValueError(f"Could not find JSON in response: {response_text}")

            # Validate category
            cat = parsed.get("category", "Other")
            if cat not in self.categories and cat != "Other":
                found = False
                for c in self.categories:
                    if c.lower() in cat.lower():
                        parsed["category"] = c
                        found = True
                        break
                if not found:
                    parsed["category"] = "Other"

            return parsed

        except subprocess.TimeoutExpired:
            logger.error("llama-cli timed out")
            return {"category": "Other", "reasoning": "Inference timed out"}
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {"category": "Other", "reasoning": f"Error: {str(e)}"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    classifier = AttachmentClassifier()
    
    # Ensure we have the binary and model
    print("Checking for llama-cli binary...")
    if not classifier.ensure_binary_exists(lambda p: print(f"Binary download: {p*100:.1f}%")):
        print("Failed to get llama-cli binary")
        exit(1)
        
    print("Checking for model...")
    if not classifier.ensure_model_exists(lambda p: print(f"Model download: {p*100:.1f}%")):
        print("Failed to get model")
        exit(1)
    
    test_cases = [
        ("Invoice for your recent purchase", "INV-123.pdf"),
        ("Flight reservation", "e-ticket.pdf"),
        ("Project update", "status_report.docx"),
        ("Gas bill", "bill_jan.pdf"),
        ("Family photos", "IMG_001.jpg"),
    ]
    for subj, fname in test_cases:
        res = classifier.classify(subj, fname)
        print(f"Subj: {subj} | File: {fname} -> {res}")
