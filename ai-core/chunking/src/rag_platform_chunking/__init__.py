"""rag_platform_chunking — LlamaIndex table/header-aware splitter."""

from rag_platform_chunking.chunker import chunk
from rag_platform_chunking.models import Chunk

__all__ = ["Chunk", "chunk"]
