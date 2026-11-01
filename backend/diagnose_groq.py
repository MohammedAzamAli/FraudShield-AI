
import os

from dotenv import load_dotenv
from groq import Groq, APIStatusError, APIConnectionError

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY", "").strip()

PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]


def main():
    print("===== GROQ MODEL DIAGNOSTICS =====")

    if not API_KEY:
        print("ERROR: GROQ_API_KEY is missing")
        return

    client = Groq(
        api_key=API_KEY,
        timeout=30.0,
        max_retries=0,
    )

    try:
        models = client.models.list()

        available = sorted(
            model.id
            for model in models.data
            if getattr(model, "active", True) is not False
        )

        print(f"\nAvailable models ({len(available)}):")

        for index, name in enumerate(available, start=1):
            print(f"{index}. {name}")

        selected = next(
            (
                model
                for model in PREFERRED_MODELS
                if model in available
            ),
            None,
        )

        if not selected:
            print(
                "\nNo preferred text-generation model found. "
                "Please select one from the list."
            )
            return

        print("\nTesting model:", selected)

        result = client.chat.completions.create(
            model=selected,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with OK."
                }
            ],
            max_tokens=30,
        )

        print("HTTP status: 200")
        print("Response:", result.choices[0].message.content)
        print("\nSUCCESS: Groq text generation is working.")
        print("Set GROQ_MODEL to:", selected)

    except APIStatusError as error:
        print("\nHTTP status:", error.status_code)

        try:
            body = error.response.json()
            details = body.get("error", body)
            print("Provider error:", str(details)[:500])
        except ValueError:
            print("Provider returned a non-JSON error")

    except APIConnectionError:
        print("Unable to connect to Groq")

    except Exception as error:
        print("Error type:", type(error).__name__)


if __name__ == "__main__":
    main()
