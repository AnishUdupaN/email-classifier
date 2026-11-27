import json
import os
import re
import subprocess
import urllib.request
import urllib.error
from typing import Tuple


def load_dotenv():
    """Reads .env file from application directory and populates os.environ if present."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    os.environ.setdefault(key, val)


def get_secret_service_ollama_key() -> str:
    """Retrieves Ollama API key from SecretService via secret-tool lookup service ollama username default."""
    cmd = ["secret-tool", "lookup", "service", "ollama", "username", "default"]
    try:
        key = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        return key
    except Exception:
        return ""


def get_ollama_config():
    """Returns (is_cloud, api_key, url, default_model)."""
    load_dotenv()
    is_cloud = os.getenv("IS_OLLAMA_CLOUD", "false").lower() in ("true", "1", "yes")

    # Priority 1: SecretService lookup via secret-tool
    api_key = get_secret_service_ollama_key()
    # Priority 2: Fallback to .env variable
    if not api_key:
        api_key = os.getenv("OLLAMA_API_KEY", "").strip()

    if is_cloud:
        url = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/api/chat")
        default_model = os.getenv("OLLAMA_MODEL_CLOUD", "gpt-oss:20b")
    else:
        url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/api/chat")
        default_model = os.getenv("OLLAMA_MODEL_LOCAL", "qwen3:0.6b")

    return is_cloud, api_key, url, default_model


def get_max_parallel() -> int:
    """Returns the maximum parallel classification request limit configured in .env."""
    load_dotenv()
    try:
        val = int(os.getenv("OLLAMA_MAX_PARALLEL", "3"))
        return max(1, val)
    except ValueError:
        return 3


SYSTEM_PROMPT = """You are a highly precise email classifier.
You must classify the provided email into EXACTLY ONE of the following 4 categories:
1. "placement"
2. "promotional"
3. "informational"
4. "important"

CRITICAL CLASSIFICATION RULES:
- "placement": ONLY for genuine college campus recruitment drives, placement cell / T&P officer updates, interview shortlists, test links, placement registration announcements, or direct updates/calls regarding a specific job application/interview.
- "promotional": Generic promotional marketing blasts, hackathon promotions, paid course ads, event advertisements, Naukri job alert summaries/digests, Unstop marketing emails/ads/quizzes, sales, or generic marketing newsletters. Note: Unstop or Naukri emails promoting courses, hackathons, or generic job digests MUST be classified as "promotional", NOT "placement".
- "informational": General college/department announcements from principal/HOD unrelated to placement drives, general news, routine alerts, system updates.
- "important": Urgent 1-on-1 personal emails, academic fee/exam deadlines, official personal action items requiring direct response.

You MUST respond strictly with a valid JSON object in the following format:
{
  "category": "<one of: placement, promotional, informational, important>",
  "reasoning": "<1-2 sentence justification for the classification>"
}
Do NOT include any extra markdown code blocks, preambles, or postscripts. Just the raw JSON object.
"""


def classify_email_with_ollama(
    sender_name: str,
    sender_email: str,
    subject: str,
    body: str,
    model: str = None,
) -> Tuple[str, str]:
    """Classifies email using Ollama Cloud (https://ollama.com/api/chat) or Local Ollama based on .env config."""
    is_cloud, api_key, url, default_model = get_ollama_config()
    target_model = model or default_model

    truncated_body = body[:2500] + ("..." if len(body) > 2500 else "")

    user_prompt = f"""EMAIL TO CLASSIFY:
From: {sender_name} <{sender_email}>
Subject: {subject}
Body Content:
{truncated_body}
"""

    headers = {"Content-Type": "application/json"}
    if is_cloud or api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }

    if not is_cloud:
        payload["format"] = "json"
        payload["options"] = {"temperature": 0.1}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "").strip()

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            json_str = json_match.group(0) if json_match else content

            parsed = json.loads(json_str)
            cat = str(parsed.get("category", "")).lower().strip()
            reasoning = parsed.get("reasoning", "No explanation provided.")

            valid_categories = ["placement", "promotional", "informational", "important"]
            if cat not in valid_categories:
                cat = "informational"

            return cat, reasoning
    except urllib.error.URLError as e:
        target_name = "Ollama Cloud" if is_cloud else "Local Ollama"
        return "informational", f"Could not connect to {target_name} at {url}: {e}"
    except Exception as e:
        return "informational", f"Error parsing Ollama classification response: {e}"

