import time
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "arcee-ai/trinity-large-preview:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  

def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    print(f"DEBUG: About to create OpenAI client with model: {model}")
    print(f"DEBUG: API key provided: {bool(api_key)}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"DEBUG: Attempt {attempt}/{MAX_RETRIES} - Creating client...")
            client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_URL,
            )
            print(f"DEBUG: Client created, making API call...")
            print(f"DEBUG: Calling client.chat.completions.create with timeout=30...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.05,
                timeout=30, 
                extra_body={"transforms": ["middle-out"]}
            )
            print("API call successful.")
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

def classify_posts(codebook: str, posts_content: str, methodology: str, api_key: str, model: str = "") -> tuple[str, str, str]:
    
    print("Starting codebook application process...")
    
    system_prompt = f"""
    You are a highly meticulous qualitative data coder. Your task is to process the raw POSTS CONTENT by applying the codes defined in the CODEBOOK.

    Operate as a qualitative researcher: apply the codebook consistently, provide concise justifications for each applied code, include representative quotations, and follow any instructions in the provided METHODOLOGY text.

    **CRITICAL INSTRUCTION:** You MUST use the EXACT POST_ID values from the input POSTS CONTENT. Do NOT make up, modify, or invent new post IDs. Only include posts that actually exist in the provided content. The POST_ID values are alphanumeric strings like "132031", "100l8bs", etc. - use them exactly as they appear.

    **EVIDENCE REQUIREMENT:** For each code you apply to a post, you MUST provide one or more representative quotations or text snippets from the post content that demonstrate why that code applies. If multiple separate text portions support the same code, separate them with the § symbol (section sign). Each evidence snippet should be a direct quote or close paraphrase from the post's title or body text.

    **STRICT OUTPUT INSTRUCTION:** Output a single raw text report. For each post that has applicable codes, use the following format exactly:

    **REQUIRED POST FORMAT:**

    POST_ID: [exact_id_from_input]
    CODE: [code_name] - EVIDENCE: [quoted_text_snippet1]§[quoted_text_snippet2]§[quoted_text_snippet3]
    CODE: [another_code_name] - EVIDENCE: [another_quoted_text_snippet]

    Where:
    - [exact_id_from_input] is the EXACT post identifier from the POSTS CONTENT
    - [code_name] is an exact code name from the CODEBOOK
    - [quoted_text_snippet] is a representative quote from the post demonstrating the code application
    - Multiple evidence snippets for the same code are separated by § (section sign)

    Only include posts that have at least one applicable code with evidence.

    """
    
    user_prompt = f"""
    Please apply the following Codebook to the provided Posts Content and generate the Structured Classification Report in the specified format.

    CODEBOOK:
    {codebook}

    POSTS CONTENT:
    {posts_content}
    METHODOLOGY:
    {methodology}
    """
    
    print("Prompts prepared. Sending request to AI model...")
    chosen_model = model or FREE_MODEL
    result = get_client(system_prompt, user_prompt, api_key, chosen_model)
    print("Response received from AI model. Codebook application completed.")
    return result, system_prompt, user_prompt


