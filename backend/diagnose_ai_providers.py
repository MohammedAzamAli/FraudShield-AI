
import json
import os
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()


def check_provider(name, url, model, key):
    print(f"\n===== {name.upper()} =====")
    print("Model:", model)

    if not key:
        print("ERROR: API key not configured")
        return

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with the word OK."
            }
        ],
        "max_tokens": 20
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            print("HTTP status:", response.status)
            print("SUCCESS: Provider responded")

    except urllib.error.HTTPError as error:
        print("HTTP status:", error.code)

        try:
            body = json.loads(
                error.read().decode("utf-8")
            )

            details = body.get("error", {})

            if isinstance(details, dict):
                print("Error type:", details.get("type"))
                print("Error code:", details.get("code"))
                print("Message:", details.get("message"))
            else:
                print("Error:", str(details))

        except (ValueError, UnicodeDecodeError):
            print("Provider returned a non-JSON error")

    except urllib.error.URLError as error:
        print("Connection error:", type(error.reason).__name__)


check_provider(
    name="OpenAI",
    url="https://api.openai.com/v1/chat/completions",
    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    key=os.getenv("OPENAI_API_KEY")
)

check_provider(
    name="Groq",
    url="https://api.groq.com/openai/v1/chat/completions",
    model=os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile"
    ),
    key=os.getenv("GROQ_API_KEY")
)
