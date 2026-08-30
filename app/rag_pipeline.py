"""
rag_pipeline.py
----------------
PDF ingestion + retrieval for the RAG tool.

Primary path: extract text with pypdf -> chunk with LangChain's
RecursiveCharacterTextSplitter -> embed with a small local
sentence-transformers model -> store in an in-memory FAISS index.

Fallback path: if sentence-transformers/FAISS aren't available or fail
to load (e.g. no internet to download the embedding model on first
run), fall back to a dependency-light TF-IDF vector store so the app
keeps working instead of crashing.
"""
from dataclasses import dataclass, field
from typing import List

from pypdf import PdfReader

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from app import config


# ---------------------------------------------------------------------------
# Simple TF-IDF fallback store (no external model download required)
# ---------------------------------------------------------------------------
class _TfidfStore:
    def __init__(self, chunks: List[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(chunks)

    def similarity_search(self, query: str, k: int = 4):
        from sklearn.metrics.pairwise import cosine_similarity
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]
        top_idx = scores.argsort()[::-1][:k]
        return [self.chunks[i] for i in top_idx if scores[i] > 0]


# ---------------------------------------------------------------------------
# FAISS + HuggingFace embeddings store
# ---------------------------------------------------------------------------
class _FaissStore:
    def __init__(self, chunks: List[str]):
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self._store = FAISS.from_texts(chunks, embeddings)

    def similarity_search(self, query: str, k: int = 4):
        docs = self._store.similarity_search(query, k=k)
        return [d.page_content for d in docs]


@dataclass
class VectorStoreWrapper:
    """Wraps whichever backend loaded successfully, plus source filenames."""
    backend: object
    source_files: List[str] = field(default_factory=list)
    engine: str = "faiss"

    def search(self, query: str, k: int = None) -> List[str]:
        k = k or config.RETRIEVAL_K
        return self.backend.similarity_search(query, k=k)


def extract_text_from_pdfs(uploaded_files) -> str:
    """Extract and concatenate text from one or more uploaded PDF files."""
    all_text = []
    for f in uploaded_files:
        try:
            reader = PdfReader(f)
            for page in reader.pages:
                text = page.extract_text() or ""
                all_text.append(text)
        except Exception as e:
            raise ValueError(f"Could not read '{getattr(f, 'name', 'file')}': {e}")
    return "\n".join(all_text)


def build_vectorstore(uploaded_files) -> VectorStoreWrapper:
    """
    Full ingestion pipeline: extract -> chunk -> embed -> store.
    Raises ValueError on invalid/empty PDFs so the UI can show a
    friendly error instead of crashing.
    """
    if not uploaded_files:
        raise ValueError("No PDF files were provided.")

    raw_text = extract_text_from_pdfs(uploaded_files)
    if not raw_text.strip():
        raise ValueError("No extractable text found in the uploaded PDF(s). "
                          "They may be scanned images without OCR text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(raw_text)
    if not chunks:
        raise ValueError("PDF text could not be split into chunks.")

    filenames = [getattr(f, "name", "uploaded.pdf") for f in uploaded_files]

    try:
        backend = _FaissStore(chunks)
        return VectorStoreWrapper(backend=backend, source_files=filenames, engine="faiss")
    except Exception:
        # Graceful fallback if the embedding model can't be downloaded/loaded.
        backend = _TfidfStore(chunks)
        return VectorStoreWrapper(backend=backend, source_files=filenames, engine="tfidf")


def get_relevant_chunks(vectorstore: VectorStoreWrapper, query: str, k: int = None) -> List[str]:
    if vectorstore is None:
        return []
    return vectorstore.search(query, k=k)
