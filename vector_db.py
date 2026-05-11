"""
Vector DB wrapper: ChromaDB with SentenceTransformer embeddings.

Uses EphemeralClient (in-memory) to avoid HNSW persistence issues
on Windows with ChromaDB 1.x Rust backend.
The index is rebuilt once per Streamlit session via @st.cache_resource.
"""

import pandas as pd
# pyrefly: ignore [missing-import]
import chromadb
# pyrefly: ignore [missing-import]
from chromadb.utils import embedding_functions
from config import EMBEDDING_MODEL_NAME


class RecipeVectorDB:
    """In-memory ChromaDB collection of recipe embeddings."""

    def __init__(self, collection_name: str = "recipes"):
        # EphemeralClient keeps everything in RAM — no file locks, no HNSW issues
        self.client = chromadb.EphemeralClient()
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
        )

    # ────────── Indexing ──────────
    def build_index(self, df: pd.DataFrame) -> None:
        """Load recipes into the collection (skips if already populated)."""
        if self.collection.count() > 0:
            print(f"[DB] Collection already has {self.collection.count()} records.")
            return

        docs = df["text_for_embedding"].tolist()
        ids  = df["id"].astype(str).tolist()

        metadatas = []
        for _, row in df.iterrows():
            allergens_csv = (
                row["allergens"] if isinstance(row["allergens"], str)
                else ", ".join(row["allergens"])
            )
            metadatas.append({
                "name":        str(row["name"]),
                "calories":    float(row["calories"]),
                "protein":     float(row["protein"]),
                "fat":         float(row["fat"]),
                "carbs":       float(row["carbs"]),
                "allergens":   allergens_csv,
                "ingredients": str(row.get("ingredients", "")),
                "steps":       str(row.get("steps", "")),
                "description": str(row.get("description", "")),
            })

        batch = 500
        for i in range(0, len(docs), batch):
            end = min(i + batch, len(docs))
            self.collection.add(
                documents=docs[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end],
            )
            print(f"[DB] Indexed {end}/{len(docs)}")
        print("[DB] Indexing complete.")

    # ────────── Semantic search ──────────
    def search(self, query: str, top_k: int = 10) -> dict:
        """Return top_k nearest recipes by cosine similarity."""
        if self.collection.count() == 0:
            return {"ids": [[]], "metadatas": [[]], "distances": [[]], "documents": [[]]}
        return self.collection.query(query_texts=[query], n_results=top_k)
