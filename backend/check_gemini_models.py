
import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

key = os.getenv("GEMINI_API_KEY", "").strip()

if not key:
    raise SystemExit("GEMINI_API_KEY is missing from backend/.env")

url = "https://generativelanguage.googleapis.com/v1beta/models"

request = urllib.request.Request(
    url,
    headers={"x-goog-api-key": key}
)

try:
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)

    print("Gemini models supporting generateContent:")

    for model in data.get("models", []):
        methods = model.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            print(model["name"])

except urllib.error.HTTPError as error:
    print("Gemini API HTTP status:", error.code)
    print("Check API key permissions and Gemini API access.")

except Exception as error:
    print("Request failed:", type(error).__name__)
