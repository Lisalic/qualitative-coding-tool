import time
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
    system_prompt = f"""You are an expert content analyst. Your task is to filter posts based on the given criteria.

FILTERING CRITERIA: {filter_prompt}

INSTRUCTIONS:
1. Analyze each post in the provided content
2. Determine which posts match the filtering criteria
3. Return ONLY a valid Python array where each object is a dictionary that contains "id", "title", and "selftext" fields
4. LIMIT your response to MAXIMUM 1000posts that best match the criteria (unless user prompt specifies different number)
5. Only include posts that clearly match the filtering criteria
6. If no posts match, return an empty Python array []
7. ALWAYS ensure the Python array is complete and properly closed with ]

EXAMPLE OUTPUT FORMAT:
[
  {{"id": "post_id_1", "title": "Post Title 1", "selftext": "Post content 1"}},
  {{"id": "post_id_2", "title": "Post Title 2", "selftext": "Post content 2"}}
]

CRITICAL: Return ONLY the raw Python array with NO markdown code blocks, NO backticks, NO wrappers around the array, and NO additional text or explanation."""

    user_prompt = f"Here are the posts to filter:\n\n{posts_content}"

    try:
        response = get_client(system_prompt, user_prompt, api_key)

        response = response.strip()
        print(response)
        if not response.startswith('['):
            return '[]'
        if not response.endswith(']'):
            last_comma = response.rfind(',')
            if last_comma > 0:
                response = response[:last_comma] + ']'
            else:
                response = response.rstrip() + ']'

        try:
            import json
            json.loads(response)
            return response
        except json.JSONDecodeError:
            return '[]'

    except Exception as e:
        return f'[{{"error": "Failed to filter posts: {str(e)}"}}]'

def filter_comments_with_ai(filter_prompt: str, comments_content: str, api_key: str) -> str:
    """
    Use AI to filter comments based on a given prompt and return results in Python format.

    Args:
        filter_prompt (str): The filtering criteria/prompt
        comments_content (str): The comments content to filter through
        api_key (str): OpenRouter API key

    Returns:
        str: Python string with filtered comments as an array of objects: [{id, body}, ...]
    """
    system_prompt = f"""You are an expert content analyst. Your task is to filter comments based on the given criteria.

FILTERING CRITERIA: {filter_prompt}

INSTRUCTIONS:
1. Analyze each comment in the provided content
2. Determine which comments match the filtering criteria
3. Return ONLY a valid Python array where each object contains "id" and "body" fields
4. LIMIT your response to MAXIMUM 1000 comments that best match the criteria (unless user prompt specifies different number)
5. Only include comments that clearly match the filtering criteria
6. If no comments match, return an empty Python array []
7. ALWAYS ensure the Python array is complete and properly closed with ]

EXAMPLE OUTPUT FORMAT:
[
  {{"id": "comment_id_1", "body": "Comment text 1"}},
  {{"id": "comment_id_2", "body": "Comment text 2"}}
]

CRITICAL: Return ONLY the raw Python array with NO markdown code blocks, NO backticks, NO wrappers around the array, and NO additional text or explanation."""

    user_prompt = f"Here are the comments to filter:\n\n{comments_content}"

    try:
        response = get_client(system_prompt, user_prompt, api_key)

        response = response.strip()
        print(response)
        if not response.startswith('['):
            return '[]'
        if not response.endswith(']'):
            last_comma = response.rfind(',')
            if last_comma > 0:
                response = response[:last_comma] + ']'
            else:
                response = response.rstrip() + ']'

        try:
            import json
            json.loads(response)
            return response
        except json.JSONDecodeError:
            return '[]'

    except Exception as e:
        return f'[{{"error": "Failed to filter comments: {str(e)}"}}]'
