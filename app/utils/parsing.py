import json


def parse_llm_review_json(raw: str) -> dict:
    """Parse LLM output into a JSON object with fallback extraction.

    Some models include extra text before/after JSON. We first try direct
    parsing, then attempt to decode from the first object-like segment.
    """
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[index:])
            if isinstance(candidate, dict):
                return candidate
        except json.JSONDecodeError:
            continue
    raise ValueError("LLM response does not contain a valid JSON object.")
