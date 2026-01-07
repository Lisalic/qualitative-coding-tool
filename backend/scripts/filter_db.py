import time
import ast
import json
import re
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "google/gemini-2.0-flash-exp:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  

def get_client(system_prompt: str, user_prompt: str, api_key: str) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_URL,
            )
            response = client.chat.completions.create(
                model=FREE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.05,
                timeout=300, 
                extra_body={"transforms": ["middle-out"]}
            )
            return response.choices[0].message.content
        except KeyboardInterrupt:
            print("\nkeyboard interrupt")
            raise
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            wait_time = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
            print(f"\nAPI call failed (attempt {attempt}/{MAX_RETRIES}): {type(e).__name__}")
            print(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)

def filter_posts_with_ai(filter_prompt: str, posts_content: str, api_key: str) -> str:
    """
    Use AI to filter posts based on a given prompt and return results in Python format.

    Args:
        filter_prompt (str): The filtering criteria/prompt
        posts_content (str): The posts content to filter through
        api_key (str): OpenRouter API key

    Returns:
        str: Python string with filtered posts as an array of objects: [{id, title, selftext}, ...]
    """
    system_prompt = f"""You are an expert content analyst. Your task is to filter posts and return ONLY a Python array of post IDs.

FILTERING CRITERIA: {filter_prompt}

INSTRUCTIONS:
1. Analyze each post in the provided content.
2. Determine which posts match the filtering criteria.
3. RETURN ONLY a valid Python array of STRING IDs. Each ID must be a quoted string (e.g. 't3_abcd' or "t3_abcd").
4. LIMIT your response to AT MOST 1000 IDs unless the user specifies a different number.
5. Include ONLY the matching IDs. Do NOT return objects, dictionaries, additional fields, or any explanatory text.
6. If no posts match, return an empty array: []
7. ALWAYS ensure the Python array is syntactically valid and properly closed with ].

EXAMPLE OUTPUT FORMAT:
['id1','id2','id3']

CRITICAL: Return ONLY the raw Python array with NO markdown, NO backticks, NO code fences, and NO additional text or commentary."""

    user_prompt = f"Here are the posts to filter:\n\n{posts_content}"

    try:
        response = get_client(system_prompt, user_prompt, api_key)
        print(response[:100])
        print("...")
        print(response[-100:])
        return wrap_in_python_array(response)

    except Exception as e:
        return [{"error": f"Failed to filter posts: {str(e)}"}]


def filter_comments_with_ai(filter_prompt: str, comments_content: str, api_key: str):
    """
    Use AI to filter comments based on a given prompt and return results as a Python list.

    Returns an array of objects with ids.
    """
    system_prompt = f"""You are an expert content analyst. Your task is to filter comments and return ONLY a Python array of comment IDs.

FILTERING CRITERIA: {filter_prompt}

INSTRUCTIONS:
1. Analyze each comment in the provided content.
2. Determine which comments match the filtering criteria.
3. RETURN ONLY a valid Python array of STRING IDs. Each ID must be a quoted string (e.g. 'c1_xyz' or "c1_xyz").
4. If no comments match, return an empty array: []
5. ALWAYS ensure the Python array is syntactically valid and properly closed with ].

EXAMPLE OUTPUT FORMAT:
['id1','id2','id3']

CRITICAL: Return ONLY the raw Python array with NO markdown, NO backticks, NO code fences, and NO additional text or commentary."""

    user_prompt = f"Here are the comments to filter:\n\n{comments_content}"

    try:
        response = get_client(system_prompt, user_prompt, api_key)
        print(response[:100])
        print("...")
        print(response[-100:])
        return wrap_in_python_array(response)
        
    except Exception as e:
        return [{"error": f"Failed to filter comments: {str(e)}"}]



def wrap_in_python_array(content: str):
    matches = re.findall(r"['\"]([a-zA-Z0-9]+)['\"]", content)

    if not matches:
        print("Warning: No IDs found in content")
        return []

    return matches