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

def load_existing_codebook(codebook_id=None) -> str:
    current_path = Path(__file__).resolve()
    project_root = current_path.parent
    while project_root != project_root.parent:
        if (project_root / "data").exists():
            break
        project_root = project_root.parent
    else:
        project_root = Path(__file__).parent.parent.parent
    
    if codebook_id:
        codebook_path = project_root / "data" / "codebooks" / f"{codebook_id}.txt"
    else:
        codebook_path = project_root / "data" / "codebook.txt"
    
    if not codebook_path.exists():
        if codebook_id:
            raise FileNotFoundError(f"Codebook '{codebook_id}' not found. Please select a valid codebook.")
        else:
            raise FileNotFoundError(f"Codebook not found at {codebook_path}. Please generate a codebook first using the codebook generator.")
    try:
        with open(codebook_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                raise ValueError(f"Codebook file exists but is empty. Please generate a valid codebook first.")
            return content
    except FileNotFoundError:
        if codebook_id:
            raise FileNotFoundError(f"Codebook '{codebook_id}' not found. Please select a valid codebook.")
        else:
            raise FileNotFoundError(f"Codebook not found at {codebook_path}. Please generate a codebook first using the codebook generator.")

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

def classify_posts(codebook: str, posts_content: str, methodology: str, api_key: str) -> str:
    
    system_prompt = f"""
    You are a highly meticulous qualitative data coder. Your task is to process the raw POSTS CONTENT by applying the codes defined in the CODEBOOK. 
    
    Your analysis must maintain the focus on:
    1. **Adult Retrospection:** The lasting effects and consequences of past bullying.
    2. **Current Student Perception:** The immediate feelings, and perception of the bullying situation.
    3. **Methodology:** The approach and criteria used for coding and analysis should align with the provided METHODOLOGY document.
    
    **STRICT OUTPUT INSTRUCTION:** You must output a single, raw text report that iterates through **EVERY SINGLE POST** in the provided content.

    
    Then, for every post, you must use the following format. If a post is not relevant, you must still output the 'post url:' line and simply state 'No codes applied.' below it.

    **REQUIRED POST FORMAT:**
    
    Post URL: [The URL for the post]
    Code applied: [Exact Specific Code Name from the Codebook]
    Reason: [A concise, specific justification for applying the code as well as a quotation from the post]
    Code applied: [Another Exact Specific Code Name if applicable]
    Reason: [A concise, specific justification for applying the code as well as a quotation from the post]
    ...
    
    Ensure you use the exact CODE NAMES from the CODEBOOK.
    
    """
    
    user_prompt = f"""
    Please apply the following Codebook to the provided Posts Content and generate the Detailed Classification Report in the specified format, including a reason for every code applied.

    CODEBOOK:
    {codebook}

    POSTS CONTENT:
    {posts_content}
    METHODOLOGY:
    {methodology}
    """
    
    return get_client(system_prompt, user_prompt, api_key)


def main(db_path, api_key, methodology="", codebook_id=None):    
    try:
        print("Loading existing codebook...")
        codebook = load_existing_codebook(codebook_id)
        print(f"Loaded codebook ({len(codebook)} characters)")
        
        print("Loading posts content...")
        POSTS_CONTENT = load_posts_content(db_path)
        if not POSTS_CONTENT:
            raise ValueError(f"Could not load posts from database. Please ensure the database contains valid data.")
        if POSTS_CONTENT.startswith("Error loading posts:"):
            raise ValueError(f"Database error: {POSTS_CONTENT}")
        print(f"Loaded posts content ({len(POSTS_CONTENT)} characters)")
        
        METHODOLOGY = methodology.strip()
        
        print("Applying codebook to posts...")
        classification_report = classify_posts(codebook, POSTS_CONTENT, METHODOLOGY, api_key)
        
        print("Saving classification report...")
        current_path = Path(__file__).resolve()
        project_root = current_path.parent
        while project_root != project_root.parent:  
            if (project_root / "data").exists():
                break
            project_root = project_root.parent
        else:
            project_root = Path(__file__).parent.parent.parent
        
        data_dir = project_root / "data"
        coded_data_dir = data_dir / "coded_data"
        coded_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp and database name
        from datetime import datetime
        db_name = Path(db_path).stem  # e.g., 'reddit_data' or 'filtered_data'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{db_name}_coded_{timestamp}.txt"
        report_path = coded_data_dir / filename
        
        write_to_file(str(report_path), classification_report)
        print(f"Classification report saved to {report_path}")
        
        return str(report_path)  # Return the path
        
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()