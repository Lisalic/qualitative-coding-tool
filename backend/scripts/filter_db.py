import os
import time
import sqlite3
import ast
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "google/gemini-2.0-flash-exp:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  


def write_to_file(filename: str, content: str):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        print(f"ERROR: Could not write to file {filename}. Reason: {e}")


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


def load_posts_content(db_path: str) -> str:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, selftext FROM submissions")
        posts = cursor.fetchall()
        conn.close()

        content = ""
        for post_id, title, selftext in posts:
            content += f"ID: {post_id}\nTitle: {title}\nText: {selftext}\n\n"
        return content
    except Exception as e:
        return f"Error loading posts: {e}"


def filter_posts_with_ai(filter_prompt: str, posts_content: str, api_key: str) -> str:
    """
    Use AI to filter posts based on a given prompt and return results in JSON format.

    Args:
        filter_prompt (str): The filtering criteria/prompt
        posts_content (str): The posts content to filter through
        api_key (str): OpenRouter API key

    Returns:
        str: JSON string with filtered posts as an array of objects: [{id, title, selftext}, ...]
    """
    system_prompt = f"""You are an expert content analyst. Your task is to filter posts based on the given criteria.

FILTERING CRITERIA: {filter_prompt}

INSTRUCTIONS:
1. Analyze each post in the provided content
2. Determine which posts match the filtering criteria
3. Return ONLY a valid JSON array where each object contains "id", "title", and "selftext" fields
4. LIMIT your response to MAXIMUM 10 posts that best match the criteria
5. Only include posts that clearly match the filtering criteria
6. If no posts match, return an empty JSON array []
7. ALWAYS ensure the JSON array is complete and properly closed with ]

EXAMPLE OUTPUT FORMAT:
[
  {{"id": "post_id_1", "title": "Post Title 1", "selftext": "Post content 1"}},
  {{"id": "post_id_2", "title": "Post Title 2", "selftext": "Post content 2"}}
]

CRITICAL: Return ONLY the raw JSON array with NO markdown code blocks, NO backticks, NO "```json" wrappers, and NO additional text or explanation."""

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


def save_filtered_posts_to_db(posts_list) -> bool:
    """
    Save filtered posts to database.

    Args:
        posts_list: A string which contains a list of post dictionaries, each containing 'id', 'title', and 'selftext' keys

    Returns:
        bool: True if successful, False if failed
    """
    try:
        posts = ast.literal_eval(posts_list)
        
        if not isinstance(posts, list):
            print(f"Error: Expected list after parsing, got {type(posts)}")
            return False

        print(f"Processing {len(posts)} posts")

        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        
        filtered_db_path = os.path.join(data_dir, "filtered_data.db")

        conn = sqlite3.connect(filtered_db_path)
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        title TEXT,
        selftext TEXT
        )
        ''')

        for post in posts:
            if isinstance(post, dict) and 'id' in post and 'title' in post and 'selftext' in post:
                cursor.execute('''
                INSERT OR REPLACE INTO submissions (id, title, selftext)
                VALUES (?, ?, ?)
                ''', (
                    post['id'],
                    post['title'],
                    post['selftext']
                ))
            else:
                print(f"Warning: Skipping invalid post: {post}")

        conn.commit()
        conn.close()

        print(f"Successfully saved {len(posts)} filtered posts to {filtered_db_path}")
        return True

    except (ValueError, SyntaxError) as e:
        print(f"Error parsing string to list: {e}")
        return False
    except Exception as e:
        print(f"Error saving filtered posts to database: {e}")
        return False


def main(api_key: str, prompt: str):
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reddit_data.db")
    if not os.path.exists(db_path):
        print("Error: reddit_data.db not found. Please import data first.")
        return

    posts_content = load_posts_content(db_path)
    if not posts_content or posts_content.startswith("Error"):
        print(posts_content)
        return

    filtered_list = filter_posts_with_ai(prompt, posts_content, api_key)
    if filtered_list.startswith('[{{"error":'):
        print(f"Filtering failed: {filtered_list}")
        return

    save_success = save_filtered_posts_to_db(filtered_list)
    if save_success:
        print("Filtering completed successfully!")
    else:
        print("Failed to save filtered data.")