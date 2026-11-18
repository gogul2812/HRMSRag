"""rag_platform_embedding — BGE-large-en-v1.5 wrapper."""

from rag_platform_embedding.embedder import embed, embed_texts, reset_model_cache

__all__ = ["embed", "embed_texts", "reset_model_cache"]
