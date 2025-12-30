import time
import sqlite3
from openai import OpenAI
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "google/gemini-2.0-flash-exp:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  


def write_to_file(path: str, content: str):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        print(f"ERROR: Could not write to file {path}. Reason: {e}")

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
        cursor.execute("SELECT title, selftext FROM submissions")
        submissions = cursor.fetchall()
        cursor.execute("SELECT body FROM comments")
        comments = cursor.fetchall()
        conn.close()

        content = ""
        for title, text in submissions:
            content += f"Title: {title}\n{text}\n\n"
        for body, in comments:
            content += f"{body}\n\n"
        return content
    except Exception as e:
        return f"Error loading posts: {e}"



def generate_codebook(posts_content: str, api_key: str, previous_codebook: str = "", feedback_text: str = "", custom_prompt: str = "") -> str:
    base_system_prompt = """
    Act as a qualitative researcher analyzing the following Reddit posts. Your task is to develop or refine a **Codebook** based on an open coding process.
    
    Your analysis must maintain the focus on:
    1. **Adult Retrospection:** The lasting effects and consequences of past bullying.
    2. **Current Student Perception:** The immediate feelings, and perception of the bullying situation.
    """
    
    # Add custom prompt if provided
    if custom_prompt.strip():
        system_prompt = f"{base_system_prompt}\n\nAdditional Instructions:\n{custom_prompt.strip()}\n"
    else:
        system_prompt = base_system_prompt
    
    system_prompt += """
    **STRICT OUTPUT INSTRUCTION:** Provide ONLY the codebook content below. Do not include any introductory or concluding conversational text.

    Format the output using the following Markdown structure for each code:

### Code Family: [Theme Name]
#### Code Name: [Name]
**Definition:** [Concise Definition]  
**Inclusion Criteria:** [When to use this code]  
**Key Words:** [Words or phrases frequently found in this code]  
**Example:** [Quote from data]
    """

    user_prompt = f"""
    Here is the data for analysis:

    {posts_content}
    """

    if previous_codebook:
        user_prompt += f"""

    EXISTING CODEBOOK:

    {previous_codebook}
    """

    if feedback_text:
        user_prompt += f"""

    CODEBOOK FEEDBACK (please use these suggestions to improve the codebook):

    {feedback_text}
    """

    return get_client(system_prompt, user_prompt, api_key)


def main(db_path, api_key, prompt="", output_name=None):    
    try:
        POSTS_CONTENT = load_posts_content(db_path)
        if not POSTS_CONTENT:
            raise ValueError(f"Could not load posts from database. Please ensure the database contains valid data.")

        print("Generating codebook...")
        codebook = generate_codebook(POSTS_CONTENT, api_key, custom_prompt=prompt)
        
        # Save to data/codebooks/ with incremental naming or provided output_name
        data_dir = Path(__file__).parent.parent.parent / "data"
        codebooks_dir = data_dir / "codebooks"
        codebooks_dir.mkdir(parents=True, exist_ok=True)
        
        # If an output_name was provided, use it; otherwise use incremental naming
        if output_name:
            # ensure extension
            out_name = output_name if output_name.endswith('.txt') else f"{output_name}.txt"
            codebook_path = codebooks_dir / out_name
        else:
            existing_codebooks = list(codebooks_dir.glob("codebook*.txt"))
            numbers = []
            for cb in existing_codebooks:
                try:
                    num = int(cb.stem.replace("codebook", ""))
                    numbers.append(num)
                except ValueError:
                    pass
            next_num = max(numbers) + 1 if numbers else 1
            codebook_path = codebooks_dir / f"codebook{next_num}.txt"

        write_to_file(str(codebook_path), codebook)
        print(f"Codebook generated and saved to {codebook_path}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()