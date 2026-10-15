"""User-facing messages for OpenRouter HTTP status codes (filter + tag expansion)."""

OPENROUTER_HTTP_MESSAGES = {
    400: "Bad Request: The AI model is unreachable. Try another model.",
    401: "Invalid API key: Your key is missing, disabled, or expired. Please check your API key.",
    402: "Insufficient credits: Your account or API key needs more credits. Add more credits and retry.",
    403: "Content flagged: Your chosen model requires moderation and your input was flagged.",
    404: (
        "Model not found on OpenRouter: the model slug may be invalid or no longer available. "
        "Choose another model from the list or verify the slug in the OpenRouter model catalog."
    ),
    408: "Request timed out: This can happen with long inputs or heavy model load. Please try again.",
    429: "Rate limited: Too many requests. Please wait and try again.",
    502: "Model unavailable: Your chosen model is down or returned an invalid response. Try another model.",
    503: "Service unavailable: No model provider is available right now. Please try again later.",
}

# HTTP statuses we pass through to the client for OpenRouter failures (not remapped to 502).
OPENROUTER_CLIENT_ERROR_CODES = frozenset(
    {400, 401, 402, 403, 404, 408, 429, 502, 503}
)


def openrouter_user_message(code: int, model_slug: str = "") -> str:
    """Human-readable message for an HTTP status from OpenRouter."""
    base = OPENROUTER_HTTP_MESSAGES.get(code, f"API error (code {code})")
    if code == 404 and (model_slug or "").strip():
        return f"{base} Requested model: {model_slug.strip()}"
    return base
