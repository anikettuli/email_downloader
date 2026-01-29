import os
import logging
import json
from llama_cpp import Llama

logger = logging.getLogger(__name__)


class AttachmentClassifier:
    def __init__(self, model_path=None):
        if model_path is None:
            # Default to models directory relative to this file
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(
                base_path, "models", "gemma-3-270m-it-Q4_K_M.gguf"
            )

        if not os.path.exists(model_path):
            logger.error(f"Model file not found at {model_path}")
            self.llm = None
        else:
            logger.info(f"Loading Gemma 3 model from {model_path}...")
            self.llm = Llama(
                model_path=model_path, n_ctx=2048, n_threads=4, verbose=False
            )
            logger.info("Model loaded successfully.")

        self.categories = [
            "Bills",
            "Receipts",
            "Payments",
            "Work Documents",
            "Home/Family",
        ]

    def classify(self, subject: str, filename: str) -> dict:
        """
        Classifies an email attachment based on subject and filename.
        Returns a dict with 'category' and 'reasoning'.
        """
        if not self.llm:
            return {"category": "Uncategorized", "reasoning": "Model not loaded."}

        # More explicit system-like prompt for better JSON compliance
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
            output = self.llm(
                prompt, max_tokens=150, stop=["<end_of_turn>", "}"], echo=False
            )

            response_text = "{" + output["choices"][0]["text"].strip() + "}"
            logger.info(f"Model raw output: {response_text}")

            # Find the first { and last }
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx : end_idx + 1]
                # Try to fix common JSON issues like trailing commas or single quotes
                import re

                json_str = re.sub(r",\s*}", "}", json_str)
                result = json.loads(json_str)
            else:
                raise ValueError(f"Could not find JSON in response: {response_text}")

            # Validate category
            cat = result.get("category", "Other")
            if cat not in self.categories and cat != "Other":
                found = False
                for c in self.categories:
                    if c.lower() in cat.lower():
                        result["category"] = c
                        found = True
                        break
                if not found:
                    result["category"] = "Other"

            return result

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {"category": "Other", "reasoning": f"Error: {str(e)}"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    classifier = AttachmentClassifier()
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
