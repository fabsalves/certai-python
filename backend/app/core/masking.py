"""Mask sensitive values for API responses — never expose full secrets."""


def mask_secret(value: str, *, visible: int = 4, max_stars: int = 14) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= visible:
        return "*" * len(cleaned)
    hidden = min(len(cleaned) - visible, max_stars)
    return cleaned[:visible] + ("*" * hidden)


def mask_api_key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("sk-proj-"):
        return mask_secret(cleaned, visible=10)
    if cleaned.startswith("sk-"):
        return mask_secret(cleaned, visible=7)
    if cleaned.startswith("gsk_"):
        return mask_secret(cleaned, visible=8)
    return mask_secret(cleaned, visible=4)
