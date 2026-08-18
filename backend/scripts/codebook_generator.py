from backend.app.ai_models import model_slug_at
from backend.app.external.openrouter_client import chat_completion

MODEL_1 = model_slug_at(0)
MODEL_2 = model_slug_at(1)
MODEL_3 = model_slug_at(2)
MODEL_4 = model_slug_at(3)
MODEL_5 = model_slug_at(4)
MODEL_6 = model_slug_at(5)
MODEL_7 = model_slug_at(6)
MAX_RETRIES = 3


async def get_client(system_prompt: str, user_prompt: str, api_key: str, MODEL: str) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    return await chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=MODEL,
        timeout=300.0,
        use_middle_out=True,
        max_retries=MAX_RETRIES,
    )

async def generate_codebook(posts_content: str, api_key: str, custom_prompt: str = "", MODEL: str = MODEL_1) -> tuple[str, str, str]:
    system_prompt = """
    Act as a qualitative researcher analyzing the provided data. Your task is to develop or refine a concise and usable Codebook based on an open coding process applicable to general qualitative research topics.

    Focus on identifying meaningful themes, writing clear code definitions, specifying inclusion criteria, suggesting representative keywords, and providing example excerpts that illustrate each code. Organize the codes into 'full' code families. Instead of creating many small code families, group the codes into a few broad, overarching code families, each containing as many logically related codes as sensible.

    **STRICT OUTPUT INSTRUCTION:** Provide ONLY the codebook content below. Do not include any introductory or concluding conversational text.

    Format the output using the following structure for each code, including the leading "###"/"####" markers exactly as shown:

### Code Family: [Theme Name]
#### Code Name: [Name]
Definition: [Concise Definition]
Inclusion Criteria: [When to use this code]
Key Words: [Words or phrases frequently found in this code]
Example: [Quote from data]
    """

    user_prompt = f"Here is the data for analysis: {posts_content} Additional Instructions: {custom_prompt}"

    result = await get_client(system_prompt, user_prompt, api_key, MODEL)
    return result, system_prompt, user_prompt
