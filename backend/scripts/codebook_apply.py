import re

from backend.app.ai_models import model_slug_at
from backend.app.external.openrouter_client import chat_completion

FREE_MODEL = model_slug_at(0)
MAX_RETRIES = 3

POST_ID_LINE_RE = re.compile(
    r"^\s*POST[\s_-]*ID\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
CODE_EVIDENCE_LINE_RE = re.compile(
    r"^\s*CODE\s*:\s*(.+?)\s*(?:-|–|—)\s*EVIDENCE\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
CODE_LINE_RE = re.compile(r"^\s*CODE\s*:\s*(.+?)\s*$", re.IGNORECASE)
EVIDENCE_LINE_RE = re.compile(r"^\s*EVIDENCE\s*:\s*(.+?)\s*$", re.IGNORECASE)
MARKDOWN_HEADER_RE = re.compile(r"^\s*#{1,6}\s*")
HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
MARKDOWN_FENCE_RE = re.compile(r"^\s*```")
LEADING_LABEL_BULLET_RE = re.compile(
    r"^\s*[-*+]\s*(?=(?:POST[\s_-]*ID|CODE|EVIDENCE)\s*:)",
    re.IGNORECASE,
)
QUOTED_EVIDENCE_BLOCK_RE = re.compile(r'^"[^"\n]+"(?:§"[^"\n]+")*$')
QUOTED_SNIPPET_RE = re.compile(r'"([^"\n]+)"')

async def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")

    def _on_retry(attempt: int, exc: Exception, wait_seconds: float) -> None:
        print(f"\nAPI call failed (attempt {attempt}/{MAX_RETRIES}): {type(exc).__name__}")
        print(f"Retrying in {wait_seconds}s...")

    result = await chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=model,
        timeout=30.0,
        use_middle_out=True,
        max_retries=MAX_RETRIES,
        on_retry=_on_retry,
    )
    print("API call successful.")
    return result


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


def _is_valid_evidence_block(evidence_block: str) -> bool:
    raw_block = (evidence_block or "").strip()
    if not raw_block:
        return False
    if not QUOTED_EVIDENCE_BLOCK_RE.fullmatch(raw_block):
        return False
    return bool(_split_evidence_snippets(raw_block))


def _extract_structured_records(raw_text: str) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    lines = _preprocess_output_lines(raw_text)
    records: list[tuple[str, list[tuple[str, list[str]]]]] = []
    current_post_id: str | None = None
    current_entries: list[tuple[str, list[str]]] = []
    pending_code: str | None = None

    def flush_current() -> None:
        nonlocal current_post_id, current_entries, pending_code
        if current_post_id and current_entries:
            records.append((current_post_id, current_entries))
        current_post_id = None
        current_entries = []
        pending_code = None

    def append_entry(code_value: str, evidence_value: str) -> None:
        code_name = _clean_inline_text(code_value)
        evidence_segments = _split_evidence_snippets(evidence_value)
        if code_name and evidence_segments:
            current_entries.append((code_name, evidence_segments))

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
            append_entry(code_evidence_match.group(1), code_evidence_match.group(2))
            pending_code = None
            continue

        code_match = CODE_LINE_RE.match(line)
        if code_match:
            pending_code = _clean_inline_text(code_match.group(1))
            continue

        evidence_match = EVIDENCE_LINE_RE.match(line)
        if evidence_match and pending_code:
            append_entry(pending_code, evidence_match.group(1))
            pending_code = None

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
                out_lines.append(f"CODE: {code_name}")
                out_lines.append(f"EVIDENCE: {evidence_text}")
        out_lines.append("")

    return "\n".join(out_lines).strip()


def validate_coding_output(normalized_text: str) -> bool:
    lines = [line.strip() for line in (normalized_text or "").splitlines() if line.strip()]
    if not lines:
        return False

    saw_post = False
    current_post_has_code = False
    pending_code = False

    for line in lines:
        post_match = POST_ID_LINE_RE.match(line)
        if post_match:
            if pending_code:
                return False
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

        one_line_match = CODE_EVIDENCE_LINE_RE.match(line)
        if one_line_match:
            code_name = _clean_inline_text(one_line_match.group(1))
            evidence_block = one_line_match.group(2)
            if not code_name or not _is_valid_evidence_block(evidence_block):
                return False
            current_post_has_code = True
            pending_code = False
            continue

        code_line_match = CODE_LINE_RE.match(line)
        if code_line_match:
            code_name = _clean_inline_text(code_line_match.group(1))
            if not code_name or pending_code:
                return False
            pending_code = True
            continue

        evidence_line_match = EVIDENCE_LINE_RE.match(line)
        if evidence_line_match:
            if not pending_code:
                return False
            evidence_block = evidence_line_match.group(1)
            if not _is_valid_evidence_block(evidence_block):
                return False
            current_post_has_code = True
            pending_code = False
            continue

        return False

    if pending_code:
        return False

    if saw_post and not current_post_has_code:
        return False

    return saw_post

async def classify_posts(codebook: str, posts_content: str, methodology: str, api_key: str, model: str = "") -> tuple[str, str, str]:
    
    print("Starting codebook application process...")
    
    system_prompt = (
        "You are a qualitative data coder.\n"
        "Apply CODEBOOK to POSTS CONTENT using METHODOLOGY.\n"
        "Return plain text only in this exact format:\n"
        "POST_ID: <exact_post_id_from_input>\n"
        "CODE: <exact_code_name_from_codebook>\n"
        "EVIDENCE: \"<exact_snippet>\"§\"<exact_snippet>\"\n"
        "CODE: <exact_code_name_from_codebook>\n"
        "EVIDENCE: \"<exact_snippet>\"§\"<exact_snippet>\"\n"

        "POST_ID: <exact_post_id_from_input>\n"
        "CODE: <exact_code_name_from_codebook>\n"
        "EVIDENCE: \"<exact_snippet>\"§\"<exact_snippet>\"\n"
        
        "POST_ID: <exact_post_id_from_input>\n"
        "CODE: <exact_code_name_from_codebook>\n"
        "EVIDENCE: \"<exact_snippet>\"§\"<exact_snippet>\"\n"


        "Rules:\n"
        "- Use only POST_ID values that appear in POSTS CONTENT.\n"
        "- Use only exact code names from CODEBOOK WITHOUT code family name.\n"
        "- For each included post, output one or more CODE EVIDENCE pairs.\n"
        "- EVIDENCE snippets must be exact contiguous substrings copied from source content.\n"
        "- Keep each snippet quoted; use § only between snippets for the same code.\n"
        "- Do not output markdown, bullets, headings, code fences, or explanation text.\n"
        "- Omit posts with no applicable codes."
        "- Apply CODEBOOK on as many posts as possible based on evidence in the content"
    )
    
    user_prompt = (
        "Apply CODEBOOK to POSTS CONTENT and return only the required format. "
        "Use as many relevant codes per post as evidence supports. "
        "Each evidence snippet must be quoted; use § only between snippets for one code. "
        f"\n\nCODEBOOK:\n{codebook}\n\nPOSTS CONTENT:\n{posts_content}\n\nMETHODOLOGY:\n{methodology}"
    )
    
    print("Prompts prepared. Sending request to AI model...")
    chosen_model = model or FREE_MODEL
    raw_result = await get_client(system_prompt, user_prompt, api_key, chosen_model)
    normalized_result = normalize_coding_output(raw_result)

    if validate_coding_output(normalized_result):
        result = normalized_result
    else:
        print("Coding output failed canonical validation. Returning raw AI output.")
        result = (raw_result or "").strip() or normalized_result

    print("Response received from AI model. Codebook application completed.")
    return result, system_prompt, user_prompt


