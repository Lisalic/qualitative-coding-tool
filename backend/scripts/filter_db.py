import time
import ast
import re
import datetime
from openai import OpenAI

from backend.app.ai_models import is_paid_model
from backend.scripts.openrouter_http import openrouter_user_message

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

MODEL_CONTEXT_LIMITS = {
    "default": 100_000 * 4,   
    "gemini": 800_000 * 4,    
    "claude": 160_000 * 4,    
    "gpt-4": 100_000 * 4,  
    "stepfun": 80_000 * 4,   
}

MAX_BATCHES_FOR_FREE = 3

ENTRY_SEPARATOR = "\n---\n"


class AIFilterError(Exception):
    """Raised when AI filtering fails with a known error code."""
    def __init__(self, message: str, code: int = 0):
        self.code = code
        super().__init__(message)


class _EmptyCompletionError(Exception):
    """HTTP 200 but no usable assistant message — retry or fail with a clear message."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def _extract_error_code(error: Exception) -> int:
    """Extract HTTP error code from an OpenAI/OpenRouter exception."""
    error_str = str(error)
    # Match "Error code: 401" pattern
    match = re.search(r'Error code:\s*(\d{3})', error_str)
    if match:
        return int(match.group(1))
    # Check for status_code attribute
    if hasattr(error, 'status_code'):
        return error.status_code
    return 0


def _log_ai(stage: str, message: str, data: dict = None):
    """Human-readable logging for AI operations."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    prefix = f"[{timestamp}] AI_FILTER | {stage}"
    if data:
        details = " | ".join(f"{k}={v}" for k, v in data.items())
        print(f"{prefix} | {message} | {details}")
    else:
        print(f"{prefix} | {message}")


def _estimate_context_limit(model: str) -> int:
    """Estimate usable context limit in characters for a model."""
    model_lower = model.lower()
    if "gemini" in model_lower:
        return MODEL_CONTEXT_LIMITS["gemini"]
    elif "claude" in model_lower:
        return MODEL_CONTEXT_LIMITS["claude"]
    elif "gpt-4" in model_lower:
        return MODEL_CONTEXT_LIMITS["gpt-4"]
    elif "stepfun" in model_lower or "step-" in model_lower:
        return MODEL_CONTEXT_LIMITS["stepfun"]
    return MODEL_CONTEXT_LIMITS["default"]


def _batch_content(content: str, max_chars: int, separator: str = ENTRY_SEPARATOR) -> list[str]:
    """
    Split content into batches that fit within max_chars.
    Splits on separator boundaries to avoid cutting entries mid-way.
    """
    if len(content) <= max_chars:
        return [content]
    
    entries = content.split(separator)
    batches = []
    current_batch = []
    current_size = 0
    
    for entry in entries:
        entry_size = len(entry) + len(separator)
        if current_size + entry_size > max_chars and current_batch:
            batches.append(separator.join(current_batch))
            current_batch = [entry]
            current_size = entry_size
        else:
            current_batch.append(entry)
            current_size += entry_size
    
    if current_batch:
        batches.append(separator.join(current_batch))
    
    return batches


def _preview_response(response: str, max_len: int = 500) -> str:
    """Create a readable preview of AI response."""
    response = response.strip()
    if len(response) <= max_len:
        return response
    half = max_len // 2 - 10
    return f"{response[:half]}\n... [{len(response) - max_len} chars omitted] ...\n{response[-half:]}"


def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise AIFilterError("OpenRouter API key is required", code=401)
    
    total_chars = len(system_prompt) + len(user_prompt)
    
    _log_ai("REQUEST", f"API call to {model}", {
        "prompt_chars": f"{total_chars:,}"
    })
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_URL,
            )
            # middle-out can yield empty completions for some providers; omit on retries.
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.05,
                timeout=300,
            )
            if attempt == 1:
                kwargs["extra_body"] = {"transforms": ["middle-out"]}

            response = client.chat.completions.create(**kwargs)

            if not response.choices or not isinstance(response.choices, list) or len(response.choices) == 0:
                _log_ai(
                    "EMPTY",
                    "No choices in completion",
                    {"model": model, "attempt": attempt},
                )
                raise _EmptyCompletionError("no choices")

            choice0 = response.choices[0]
            finish = getattr(choice0, "finish_reason", None)
            msg = choice0.message if choice0 else None
            raw_content = (msg.content or "") if msg else ""
            if not msg or not raw_content.strip():
                _log_ai(
                    "EMPTY",
                    "Empty assistant content",
                    {"model": model, "attempt": attempt, "finish_reason": finish},
                )
                raise _EmptyCompletionError("empty content")

            return raw_content

        except KeyboardInterrupt:
            raise
        except AIFilterError:
            raise
        except _EmptyCompletionError:
            if attempt == MAX_RETRIES:
                msg = (
                    "The model returned no usable output (empty reply). "
                    "This often happens when a free model is overloaded or briefly unavailable—try another model or retry."
                )
                _log_ai("ERROR", msg, {"model": model})
                raise AIFilterError(msg, code=502) from None
            wait_time = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
            _log_ai(
                "RETRY",
                f"Empty completion, attempt {attempt}/{MAX_RETRIES}",
                {"wait": f"{wait_time}s", "model": model},
            )
            time.sleep(wait_time)
        except Exception as e:
            code = _extract_error_code(e)
            if attempt == MAX_RETRIES:
                msg = openrouter_user_message(code, model) if code else str(e)
                extra = {"model": model, "http_code": code} if code else None
                _log_ai("ERROR", f"All {MAX_RETRIES} attempts failed: {msg}", extra)
                raise AIFilterError(msg, code=code)
            wait_time = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
            _log_ai("RETRY", f"Attempt {attempt}/{MAX_RETRIES} failed: {type(e).__name__}", {"wait": f"{wait_time}s"})
            time.sleep(wait_time)


def _run_batched_filter(content_type: str, filter_prompt: str, content: str, api_key: str, model: str, system_prompt: str) -> tuple[list, str]:
    """
    Shared batched filtering logic for both posts and comments.
    
    Error policy:
    - If batch 1 fails -> raise immediately (likely a config/auth problem)
    - If batch 2+ fails -> stop processing, return results collected so far
    
    Returns:
        tuple: (list of IDs, last_user_prompt)
    """
    chosen_model = model or FREE_MODEL
    paid_model = is_paid_model(chosen_model)
    context_limit = _estimate_context_limit(chosen_model)
    max_content_chars = context_limit - len(system_prompt) - len(filter_prompt) - 1000
    
    _log_ai(f"FILTER_{content_type.upper()}", f"Starting with {chosen_model}", {
        "content_chars": f"{len(content):,}",
        "context_limit": f"{context_limit:,}",
        "max_per_batch": f"{max_content_chars:,}"
    })
    
    batches = _batch_content(content, max_content_chars)
    total_batches = len(batches)

    if not paid_model and total_batches > MAX_BATCHES_FOR_FREE:
        if MAX_BATCHES_FOR_FREE <= 1:
            _log_ai("BATCHING", f"Content requires {total_batches} batches, limiting to 1 (first batch only)")
            batches = [batches[0]]
        else:
            _log_ai("BATCHING", f"Content requires {total_batches} batches, limiting to {MAX_BATCHES_FOR_FREE} (sampling evenly)")
            indices = [int(i * (total_batches - 1) / (MAX_BATCHES_FOR_FREE - 1)) for i in range(MAX_BATCHES_FOR_FREE)]
            batches = [batches[i] for i in indices]
    else:
        _log_ai("BATCHING", f"Split into {total_batches} batch(es)")

    if paid_model:
        _log_ai("BATCH_POLICY", "Paid model: no max-batch cap applied")
    else:
        _log_ai("BATCH_POLICY", f"Free model: max {MAX_BATCHES_FOR_FREE} batches")

    all_ids = []
    last_user_prompt = ""
    label = "Posts" if content_type == "posts" else "Comments"
    
    for i, batch in enumerate(batches):
        if filter_prompt:
            user_prompt = f"Filter criteria: {filter_prompt}\n\n{label} to analyze:\n{batch}"
        else:
            user_prompt = f"Return ALL {content_type.lower()} IDs:\n{batch}"
        last_user_prompt = user_prompt
        
        _log_ai("BATCH", f"Processing batch {i+1}/{len(batches)}", {"chars": f"{len(batch):,}"})
        
        try:
            response = get_client(system_prompt, user_prompt, api_key, chosen_model)
            
            _log_ai("RESPONSE", f"Batch {i+1} response ({len(response)} chars):")
            print(f"    {_preview_response(response, 300)}")
            
            batch_ids = wrap_in_python_array(response)
            _log_ai("BATCH_RESULT", f"Batch {i+1}: extracted {len(batch_ids)} IDs")
            all_ids.extend(batch_ids)
            
        except AIFilterError as e:
            if i == 0:
                _log_ai("FATAL", f"Batch 1 failed, aborting: {e}")
                raise
            else:
                _log_ai("BATCH_STOP", f"Batch {i+1} failed, stopping with {len(all_ids)} IDs collected so far: {e}")
                break
    
    unique_ids = list(dict.fromkeys(all_ids))
    _log_ai("COMPLETE", f"Total unique IDs: {len(unique_ids)}")
    
    return unique_ids, last_user_prompt


def filter_posts_with_ai(filter_prompt: str, posts_content: str, api_key: str, model: str = "") -> tuple[list, str, str]:
    """
    Use AI to filter posts. Raises AIFilterError on first-batch failure.
    """
    system_prompt = """You are an expert content analyst. Your task is to filter posts and return ONLY a Python array of post IDs.

INSTRUCTIONS:
1. Analyze each post in the provided content. Posts are separated by "---".
2. Each post starts with [ID] followed by the content.
3. Return ONLY IDs of posts that match the filtering criteria.
4. RETURN ONLY a valid Python array of STRING IDs, e.g. ['t3_abc', 't3_xyz']
5. If no posts match, return: []

CRITICAL: Return ONLY the raw Python array. No markdown, no backticks, no explanation."""

    ids, last_user_prompt = _run_batched_filter("posts", filter_prompt, posts_content, api_key, model, system_prompt)
    return ids, system_prompt, last_user_prompt


def filter_comments_with_ai(filter_prompt: str, comments_content: str, api_key: str, model: str = "") -> tuple[list, str, str]:
    """
    Use AI to filter comments. Raises AIFilterError on first-batch failure.
    """
    system_prompt = """You are an expert content analyst. Your task is to filter comments and return ONLY a Python array of comment IDs.

INSTRUCTIONS:
1. Analyze each comment in the provided content. Comments are separated by "---".
2. Each comment starts with [ID] followed by the content.
3. Return ONLY IDs of comments that match the filtering criteria.
4. RETURN ONLY a valid Python array of STRING IDs, e.g. ['t1_abc', 't1_xyz']
5. If no comments match, return: []

CRITICAL: Return ONLY the raw Python array. No markdown, no backticks, no explanation."""

    ids, last_user_prompt = _run_batched_filter("comments", filter_prompt, comments_content, api_key, model, system_prompt)
    return ids, system_prompt, last_user_prompt



def wrap_in_python_array(content: str) -> list:
    """
    Parse AI response into a list of ID strings.
    Handles various formats the AI might return.
    """
    content = content.strip()
    
    # Remove common markdown artifacts
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line (```python or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        content = "\n".join(lines).strip()
    
    # Try to parse as Python literal
    try:
        obj = ast.literal_eval(content)
        if isinstance(obj, list):
            result = [str(x) for x in obj if x is not None]
            _log_ai("PARSE", f"Parsed {len(result)} IDs via ast.literal_eval")
            return result
    except Exception as e:
        _log_ai("PARSE_WARN", f"ast.literal_eval failed: {e}, falling back to regex")

    # Fallback: extract quoted strings
    matches = re.findall(r"['\"]([^'\"]+)['\"]", content)
    if not matches:
        _log_ai("PARSE_WARN", "No quoted strings found in response")
        return []

    # Filter to ID-like tokens only
    filtered = [m for m in matches if re.match(r"^[A-Za-z0-9_:-]+$", m)]
    _log_ai("PARSE", f"Extracted {len(filtered)} IDs via regex fallback (from {len(matches)} quoted strings)")
    return filtered