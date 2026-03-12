import time
import re
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
MODEL_1 = "arcee-ai/trinity-large-preview:free"
MODEL_2 = "stepfun/step-3.5-flash:free"
MODEL_3 = "z-ai/glm-4.5-air:free"
MODEL_4 = "deepseek/deepseek-r1-0528:free"
MODEL_5 = "nvidia/nemotron-3-nano-30b-a3b:free"
MODEL_6 = "qwen/qwen3-235b-a22b-thinking-2507"
MODEL_7 = "openai/gpt-oss-120b:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2


def get_client(system_prompt: str, user_prompt: str, api_key: str, MODEL: str) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_URL,
            )
            response = client.chat.completions.create(
                model=MODEL,
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
            raise
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            wait_time = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
            time.sleep(wait_time)

def generate_codebook(posts_content: str, api_key: str, custom_prompt: str = "", MODEL: str = MODEL_1) -> tuple[str, str, str]:
    system_prompt = """
    Act as a qualitative researcher analyzing the provided data. Your task is to develop or refine a concise and usable Codebook based on an open coding process applicable to general qualitative research topics.

    Focus on identifying meaningful themes, writing clear code definitions, specifying inclusion criteria, suggesting representative keywords, and providing example excerpts that illustrate each code. Organize the codes into 'full' code families. Instead of creating many small code families, group the codes into a few broad, overarching code families, each containing as many logically related codes as sensible.

    **STRICT OUTPUT INSTRUCTION:** Provide ONLY the codebook content below. Do not include any introductory or concluding conversational text.

    Format the output using the following structure for each code:

Code Family: [Theme Name]
Code Name: [Name]
Definition: [Concise Definition]
Inclusion Criteria: [When to use this code]
Key Words: [Words or phrases frequently found in this code]
Example: [Quote from data]
    """

    user_prompt = f"Here is the data for analysis: {posts_content} Additional Instructions: {custom_prompt}"

    result = get_client(system_prompt, user_prompt, api_key, MODEL)
    return result, system_prompt, user_prompt

def compare_agreement(codebook_a: str, codebook_b: str, api_key: str, MODEL: str = MODEL_3) -> str:
    system_prompt = (
        "You are an assistant that compares two codebooks and returns ONLY a single numeric percentage "
        "(0-100) representing how much they agree. Do NOT include any explanation, text, or punctuation beyond "
        "optional trailing percent sign. Respond with something like or '85%'."
    )

    user_prompt = f"Codebook A:\n{codebook_a}\n\nCodebook B:\n{codebook_b}\n\nReturn only a single percentage value (0-100) indicating percent agreement between the two codebooks."

    resp = get_client(system_prompt, user_prompt, api_key, MODEL)

    if not resp:
        raise ValueError("Empty response from agreement comparator")

    # Extract first number (integer or float) and normalize to an integer percent string
    m = re.search(r"(\d{1,3}(?:\.\d+)?)", resp)
    if not m:
        # fallback: return raw response stripped
        return resp.strip()

    # Convert to integer percent if possible
    try:
        val = float(m.group(1))
        if val < 0:
            val = 0.0
        if val > 100:
            val = 100.0
        # Format without decimals when it's whole
        if val.is_integer():
            return str(int(val)) + "%"
        return f"{val}%"
    except Exception:
        return m.group(1)
