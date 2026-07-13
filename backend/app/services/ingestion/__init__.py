"""AI ingestion of uploaded materials.

Same pattern as the professor's report consolidation: extract text, run one LLM
pass, persist plain Text columns, feed the result to the ContextBuilder. No
embeddings/RAG.
"""

INGESTION_PENDING = "pending"
INGESTION_PROCESSING = "processing"
INGESTION_DONE = "done"
INGESTION_FAILED = "failed"
INGESTION_UNSUPPORTED = "unsupported"
