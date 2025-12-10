import json
import sys
import sqlite3
from pathlib import Path
import google.generativeai as genai

## FILTER NOT IMPLEMENTED


def setup_gemma(api_key: str):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemma-3-27b-it")
    return model


def prompt_gemma(model, prompt: str):
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=512,
            ),
        )

        text = ""
        if hasattr(response, "text") and response.text:
            text = response.text
        elif getattr(response, "candidates", None):
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                if content and getattr(content, "parts", None):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text

        print(f"Gemma Response: {text}")

        return text

    except Exception as exc: 
        error_msg = f"Error prompting Gemma: {str(exc)}"
        print(error_msg)
        return error_msg

def main(api_key: str, prompt: str | None = None, database: str = "original"):
    # Determine database path
    from pathlib import Path
    from app.config import settings
    db_path = Path(settings.reddit_db_path)
    if database == "filtered":
        db_path = db_path.parent / "filtereddata.db"

    # Sample data from database
    sample_data = ""
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT title, selftext FROM submissions LIMIT 5")
            submissions = cursor.fetchall()
            cursor.execute("SELECT body FROM comments LIMIT 10")
            comments = cursor.fetchall()
            conn.close()

            sample_data = "Sample submissions:\n"
            for title, text in submissions:
                sample_data += f"Title: {title}\nText: {text[:200]}...\n\n"
            sample_data += "Sample comments:\n"
            for body, in comments:
                sample_data += f"{body[:200]}...\n\n"
        except Exception as e:
            sample_data = f"Error sampling data: {e}\n"

    # Create full prompt
    full_prompt = f"{sample_data}\n{prompt or 'Generate a comprehensive codebook for analyzing this Reddit data'}"

    model = setup_gemma(api_key)
    return prompt_gemma(model, full_prompt)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_db.py <api_key> [prompt]")
        sys.exit(1)

    api_key_arg = sys.argv[1]
    prompt_arg = sys.argv[2] if len(sys.argv) > 2 else None

    result = main(api_key_arg, prompt_arg)