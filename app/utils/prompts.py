def build_review_prompt(
    language: str,
    code: str,
    context: str | None = None,
    review_language: str = "en",
) -> str:
    """Build a consistent prompt that asks the model for structured JSON.

    Why this helper exists:
    - keeps prompt format identical across providers,
    - reduces copy/paste prompt drift,
    - makes output parsing easier because the model is instructed to return
      fixed keys: summary, issues, suggestions.
    """
    language_label = "Python" if language == "python" else "JavaScript"
    output_language = "Thai" if review_language == "th" else "English"
    context_block = f"\nAdditional context:\n{context}\n" if context else ""
    return (
        f"You are a strict senior {language_label} reviewer.\n"
        "Review the code for correctness, bugs, security, and maintainability.\n"
        "Respond in JSON with fields: summary, issues, suggestions.\n"
        "Each issue should include severity (low|medium|high), message, and optional line.\n"
        f"Write summary, issues, and suggestions in {output_language}.\n"
        f"{context_block}\n"
        f"Code ({language_label}):\n"
        "```"
        f"{language}\n"
        f"{code}\n"
        "```"
    )
