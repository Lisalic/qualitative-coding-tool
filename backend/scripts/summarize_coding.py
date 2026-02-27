import os
import json
from scripts.codebook_generator import get_client, MODEL_3

def summarize_coding(coding_data: str, user_prompt: str = "", api_key: str = "", model: str = "") -> str:
    """
    Summarize a coding output using qualitative coding techniques.
    """
    print(f"[summarize_coding] Function called with data length: {len(coding_data)}, model: {model}")
    if not coding_data:
        raise ValueError("Coding data is required")

    if not api_key:
        raise ValueError("API key is required")

    # Use provided model or default
    chosen_model = model or MODEL_3
    print(f"[summarize_coding] Using model: {chosen_model}")

    # System prompt for qualitative coding summarization
    system_prompt = "You are an expert qualitative researcher specializing in thematic analysis and coding techniques. Your task is to analyze and summarize coded qualitative data using established qualitative research methods. Provide a comprehensive summary that includes:\n- Key themes and patterns identified in the coding\n- Frequency and distribution of codes\n- Relationships between codes and themes\n- Representative quotes or examples from the data\n- Overall insights and implications\n- Methodological observations about the coding approach\nStructure your response clearly with headings and be thorough but concise. Return the full summary as text (no extra JSON or metadata)."

    # Combine the coding data with user instructions
    user_prompt = f"Coding Data to Summarize: {coding_data} Additional Instructions: {user_prompt} Please provide a comprehensive summary of this coded qualitative data using qualitative research techniques."

    print(f"[summarize_coding] Making API call with system prompt length: {len(system_prompt)}, user prompt length: {len(user_prompt)}")
    try:
        response = get_client(system_prompt, user_prompt, api_key, chosen_model)
        print(f"[summarize_coding] API call successful, response length: {len(response)}")
        return response
    except Exception as exc:
        print(f"[summarize_coding] API call failed: {exc}")
        raise ValueError(f"Failed to generate summary: {str(exc)}")