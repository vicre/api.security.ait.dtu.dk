"""Template context helpers."""


def swagger_defaults(_request):
    """Expose default placeholders used by legacy templates."""

    return {"swagger_token_placeholder": "Token YOUR_API_KEY"}
