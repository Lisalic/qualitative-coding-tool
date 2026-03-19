import re
import time
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FREE_MODEL = "arcee-ai/trinity-large-preview:free"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

POST_ID_LINE_RE = re.compile(
    r"^\s*POST[\s_-]*ID\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
CODE_EVIDENCE_LINE_RE = re.compile(
    r"^\s*CODE\s*:\s*(.+?)\s*(?:-|–|—)\s*EVIDENCE\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
MARKDOWN_HEADER_RE = re.compile(r"^\s*#{1,6}\s*")
HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
MARKDOWN_FENCE_RE = re.compile(r"^\s*```")
LEADING_LABEL_BULLET_RE = re.compile(
    r"^\s*[-*+]\s*(?=(?:POST[\s_-]*ID|CODE)\s*:)",
    re.IGNORECASE,
)
QUOTED_EVIDENCE_BLOCK_RE = re.compile(r'^"[^"\n]+"(?:§"[^"\n]+")*$')
QUOTED_SNIPPET_RE = re.compile(r'"([^"\n]+)"')

def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=OPENROUTER_URL,
            )
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


def _clean_inline_text(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _preprocess_output_lines(raw_text: str) -> list[str]:
    normalized = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if MARKDOWN_FENCE_RE.match(line):
            continue
        if HORIZONTAL_RULE_RE.match(line):
            continue

        line = MARKDOWN_HEADER_RE.sub("", line)
        line = LEADING_LABEL_BULLET_RE.sub("", line)
        line = _clean_inline_text(line)
        if not line:
            continue
        lines.append(line)

    return lines


def _split_evidence_snippets(raw_evidence: str) -> list[str]:
    cleaned_input = _clean_inline_text(raw_evidence)
    if not cleaned_input:
        return []

    quoted_matches = QUOTED_SNIPPET_RE.findall(cleaned_input)
    source_segments = quoted_matches if quoted_matches else cleaned_input.split("§")

    snippets = []
    for segment in source_segments:
        cleaned = _clean_inline_text(segment)
        cleaned = cleaned.strip('"').strip("'")
        cleaned = cleaned.replace('"', "'")
        if cleaned:
            snippets.append(cleaned)
    return snippets


def _format_evidence_segments(evidence_segments: list[str]) -> str:
    formatted = []
    for segment in evidence_segments:
        cleaned = _clean_inline_text(segment)
        cleaned = cleaned.strip('"').strip("'")
        cleaned = cleaned.replace('"', "'")
        if cleaned:
            formatted.append(f'"{cleaned}"')
    return "§".join(formatted)


def _extract_structured_records(raw_text: str) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    lines = _preprocess_output_lines(raw_text)
    records: list[tuple[str, list[tuple[str, list[str]]]]] = []
    current_post_id: str | None = None
    current_entries: list[tuple[str, list[str]]] = []

    def flush_current() -> None:
        nonlocal current_post_id, current_entries
        if current_post_id and current_entries:
            records.append((current_post_id, current_entries))
        current_post_id = None
        current_entries = []

    for line in lines:
        post_match = POST_ID_LINE_RE.match(line)
        if post_match:
            flush_current()
            post_id = _clean_inline_text(post_match.group(1))
            current_post_id = post_id if post_id else None
            continue

        if not current_post_id:
            continue

        code_evidence_match = CODE_EVIDENCE_LINE_RE.match(line)
        if code_evidence_match:
            code_name = _clean_inline_text(code_evidence_match.group(1))
            evidence_segments = _split_evidence_snippets(code_evidence_match.group(2))
            if code_name and evidence_segments:
                current_entries.append((code_name, evidence_segments))

    flush_current()
    return records


def normalize_coding_output(raw_text: str) -> str:
    records = _extract_structured_records(raw_text)
    out_lines: list[str] = []

    for post_id, entries in records:
        out_lines.append(f"POST_ID: {post_id}")
        for code_name, evidence_segments in entries:
            evidence_text = _format_evidence_segments(evidence_segments)
            if evidence_text:
                out_lines.append(f"CODE: {code_name} - EVIDENCE: {evidence_text}")
        out_lines.append("")

    return "\n".join(out_lines).strip()


def validate_coding_output(normalized_text: str) -> bool:
    lines = [line.strip() for line in (normalized_text or "").splitlines() if line.strip()]
    if not lines:
        return False

    saw_post = False
    current_post_has_code = False

    for line in lines:
        post_match = POST_ID_LINE_RE.match(line)
        if post_match:
            if saw_post and not current_post_has_code:
                return False
            post_id = _clean_inline_text(post_match.group(1))
            if not post_id:
                return False
            saw_post = True
            current_post_has_code = False
            continue

        if not saw_post:
            return False

        code_match = CODE_EVIDENCE_LINE_RE.match(line)
        if not code_match:
            return False

        code_name = _clean_inline_text(code_match.group(1))
        evidence_block = (code_match.group(2) or "").strip()

        if not code_name or not evidence_block:
            return False
        if not QUOTED_EVIDENCE_BLOCK_RE.fullmatch(evidence_block):
            return False

        evidence_segments = _split_evidence_snippets(evidence_block)
        if not evidence_segments:
            return False

        current_post_has_code = True

    if saw_post and not current_post_has_code:
        return False

    return saw_post

def classify_posts(codebook: str, posts_content: str, methodology: str, api_key: str, model: str = "") -> tuple[str, str, str]:
    
    print("Starting codebook application process...")
    
    system_prompt = """
    You are a qualitative data coder.

    Apply codes from CODEBOOK to POSTS CONTENT using METHODOLOGY guidance.

    Output plain text only in this exact structure:
    POST_ID: <exact_post_id_from_input>
    CODE: <exact_code_name_from_codebook> - EVIDENCE: "<exact_snippet>"§"<exact_snippet>"

    Rules:
    - Use only POST_ID values that appear in POSTS CONTENT.
    - Use exact code names from CODEBOOK.
    - Include one or more CODE lines per included post.
    - Evidence snippets must be exact contiguous substrings copied from source content.
    - If only one snippet exists, still keep it quoted.
    - If multiple snippets exist for one code, separate only with §.
    - Do not output markdown, bullets, headings, code fences, or explanation text.
    - Omit posts with no applicable codes.
    """
    
    user_prompt = (
        "Apply CODEBOOK to POSTS CONTENT and return the coding report in the required format. "
        "Use as many relevant codes per post as supported by evidence. "
        "Every evidence snippet must be in double quotes and multiple snippets must use §. "
        "Return plain text only. "
        f"\n\nCODEBOOK:\n{codebook}\n\nPOSTS CONTENT:\n{posts_content}\n\nMETHODOLOGY:\n{methodology}"
    )
    
    print("Prompts prepared. Sending request to AI model...")
    chosen_model = model or FREE_MODEL
    raw_result = get_client(system_prompt, user_prompt, api_key, chosen_model)
    normalized_result = normalize_coding_output(raw_result)

    if validate_coding_output(normalized_result):
        result = normalized_result
    else:
        print("Coding output failed canonical validation. Returning raw AI output.")
        result = (raw_result or "").strip() or normalized_result

    print("Response received from AI model. Codebook application completed.")
    return result, system_prompt, user_prompt


