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

def classify_posts(codebook: str, posts_content: str, methodology: str, api_key: str) -> str:
    
    system_prompt = f"""
    You are a highly meticulous qualitative data coder. Your task is to process the raw POSTS CONTENT by applying the codes defined in the CODEBOOK.

    Operate in a general qualitative research mode: apply the codebook consistently, provide concise justifications for each applied code, include representative quotations where helpful, and follow any instructions in the provided METHODOLOGY text.

    **STRICT OUTPUT INSTRUCTION:** Output a single raw text report that iterates through EVERY post in the provided content. If a post is not relevant, still include the post URL line and state 'No codes applied.' beneath it.

    Then, for every post, use the following format exactly.

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


