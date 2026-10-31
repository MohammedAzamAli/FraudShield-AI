
import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

key = os.getenv("GEMINI_API_KEY", "").strip()
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
model = model.removeprefix("models/")

if not key:
    raise SystemExit("GEMINI_API_KEY is missing")

url = (
    "https://generativelanguage.googleapis.com/v1beta/"
    f"models/{model}:generateContent"
)

payload = {
    "contents": [
        {
            "parts": [
                {"text": "Reply with: Gemini connection successful"}
            ]
        }
    ]
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    },
    method="POST",
)

print("Testing model:", model)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
        print("HTTP status:", response.status)
        print("Response:", result["candidates"][0]["content"]["parts"][0].get("text"))

except urllib.error.HTTPError as error:
    print("HTTP status:", error.code)
    try:
        details = json.loads(error.read().decode("utf-8"))
        provider_error = details.get("error", {})
        print("Provider error status:", provider_error.get("status"))
        print("Provider message:", provider_error.get("message"))
    except (ValueError, UnicodeDecodeError):
        print("Provider returned a non-JSON error.")

except Exception as error:
    print("Connection failure:", type(error).__name__)
