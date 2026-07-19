"""AI ingestion of uploaded materials.

Same pattern as the professor's report consolidation: extract text, run one LLM
pass, persist plain Text columns, feed the result to the ContextBuilder. No
embeddings/RAG.
"""

import json
from typing import Any

INGESTION_PENDING = "pending"
INGESTION_PROCESSING = "processing"
INGESTION_DONE = "done"
INGESTION_FAILED = "failed"
INGESTION_UNSUPPORTED = "unsupported"


def coerce_llm_text_field(value: Any) -> str:
    """Ensure LLM output is stored as a string in Text/VARCHAR columns."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
