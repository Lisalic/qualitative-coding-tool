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

def main(api_key: str, prompt: str | None = None):
    model = setup_gemma(api_key)
    return prompt_gemma(model, prompt)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_db.py <api_key> [prompt]")
        sys.exit(1)

    api_key_arg = sys.argv[1]
    prompt_arg = sys.argv[2] if len(sys.argv) > 2 else None

    result = main(api_key_arg, prompt_arg)