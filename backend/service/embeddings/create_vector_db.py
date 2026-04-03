import os 
import torch 
import json 
import warnings
warnings.filterwarnings('ignore')
import logging

from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from langchain.embeddings.base import Embeddings 

from core.config import vector_settings, settings


logger = logging.getLogger(__name__)

class CPUEmbeddings(Embeddings):
    """
    CPU-only embeddings with persistent caching for fraud detection.
    Supports both training (GPU if available) and deployment (CPU-only) modes.
    """
    
    def __init__(self, training_mode: bool = False):

        """
        Initialize embeddings with caching.
        
            model_name: HuggingFace model name
            model_path: Local path to save/load model
            cache_path: Directory for embedding cache
            training_mode: If True, uses GPU if available; if False, forces CPU
        """
        
        self.model_name = vector_settings.MODEL_NAME
        self.model_path = vector_settings.MODEL_PATH
        self.cache_path = vector_settings.CACHE_PATH
        self.cache_file = os.path.join(self.cache_path, "embedding_cache.json")
        
        # Ensure directories exist
        os.makedirs(self.cache_path, exist_ok=True)
        os.makedirs(self.model_path, exist_ok=True)

        self.cache = self._load_cache()

        # Determine device
        if training_mode:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            # print(f"🚀 Training mode: Using {device.upper()}")
            logger.info(f"Training mode initialized. Using device: {device.upper()}")
        else:
            device = 'cpu'
            # print(f"📦 Deployment mode: Using CPU")
            logger.info("Deployment mode initialized. Forced CPU usage.")

        
        # Load or download model
        if os.path.exists(os.path.join(self.model_path, "config.json")):
            # print(f"Loading model from {self.model_path}")
            self.model = SentenceTransformer(self.model_path, device=device)
        else:
            # print(f"Downloading model {self.model_name}")
            logger.info(f"Loading existing model from {self.model_path}")
            self.model = SentenceTransformer(
                model_name_or_path=self.model_name, 
                device=device
            )
            self.model.save(self.model_path)
            # print(f"Model saved to {self.model_path}")
            logger.info(f"Successfully downloaded and saved model to {self.model_path}")


    def _load_cache(self) -> Dict[str, List[float]]:
        """
        Load embedding cache from disk.
        
        Returns:
            Dictionary mapping text to embeddings
        """
        if os.path.exists(self.cache_file):
            try: 
            
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

                logger.info(f"Successfully loaded {len(cache)} cached embeddings from disk.")
                return cache
            
            except (json.JSONDecodeError, IOError) as e:
                # print(f"⚠️ Cache file corrupted or unreadable: {e}")
                # print("   Starting with empty cache")
                logger.warning(f"Cache file corrupted or unreadable: {e}. Starting with an empty cache.")
                return {}

        logger.info("No existing cache found. Starting fresh.")
        return {}
    

    # TODO: Update this funciton alos 

    def _save_cache(self) -> None:
        """
        Save embedding cache to disk.
        """
        try:

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)

            # print(f"💾 Cache saved with {len(self.cache)} entries")
            logger.debug(f"Cache saved successfully to {self.cache_file} with {len(self.cache)} entries.")

        except IOError as e:
            # print(f"❌ Failed to save cache: {e}")
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")

    
    # override
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents with caching.
        
        Args:
            texts: List of text documents to embed
            
        Returns:
            List of embedding vectors (one per document)
        """

        if not texts:
            logger.debug("embed_documents called with empty list. Returning empty.")
            return []
        
        embeddings = [None] * len(texts)
        new_texts = []
        new_indices = []

        for i, text in enumerate(texts):
            if text in self.cache:
                embeddings[i] = self.cache[text]
            else:
                new_texts.append(text)
                new_indices.append(i)

        if new_texts:
            # print(f"🔄 Computing embeddings for {len(new_texts)} new documents...")
            logger.info(f"Computing fresh embeddings for {len(new_texts)} new documents...")
            
            new_embeddings = self.model.encode(
                new_texts, 
                normalize_embeddings=True,
                show_progress_bar=len(new_texts) > 10,
                convert_to_numpy=True
            )
            
            # Convert to list if tensor/numpy
            if hasattr(new_embeddings, 'tolist'):
                new_embeddings = new_embeddings.tolist()
            
            # Update embeddings and cache
            for idx, emb in zip(new_indices, new_embeddings):
                embeddings[idx] = emb
                self.cache[texts[idx]] = emb
            
            # Save cache after computing new embeddings
            self._save_cache()
            # print(f"✅ Added {len(new_texts)} embeddings to cache")
            logger.info(f"Successfully added {len(new_texts)} new embeddings to cache.")
        else:
            # print(f"✓ All {len(texts)} documents found in cache")
            logger.debug(f"All {len(texts)} requested documents were retrieved from cache.")
        
        return embeddings


    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query with caching.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """

        # Check cache
        if text in self.cache:
            logger.debug("Query found in cache. Returning cached vector.")
            return self.cache[text]
        
        logger.debug("Query not in cache. Computing new embedding.")
        
        # Compute embedding
        embedding = self.model.encode(
            [text], 
            normalize_embeddings=True,
            convert_to_numpy=True
        )[0]
        
        # Convert to list if needed
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
        
        # Cache and save
        self.cache[text] = embedding
        self._save_cache()
        
        return embedding


    def clear_cache(self) -> None:
        """
        Clear the embedding cache (both in-memory and on disk).
        """
        self.cache = {}
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                logger.info(f"Deleted cache file at {self.cache_file}")

            except OSError as e:
                logger.error(f"Error deleting cache file: {e}")
                
        # print("🗑️ Cache cleared")
        logger.info("In-memory cache cleared.")


    def get_cache_size(self) -> int:
        """
        Get the number of cached embeddings.
        
        Returns:
            Number of entries in cache
        """
        return len(self.cache)
    

    def get_cache_info(self) -> Dict:
        """
        Get detailed cache statistics.
        
        Returns:
            Dictionary with cache information
        """
        cache_size_mb = 0
        if os.path.exists(self.cache_file):
            cache_size_mb = os.path.getsize(self.cache_file) / (1024 * 1024)
        
        info = {
            "num_entries": len(self.cache),
            "cache_file": self.cache_file,
            "cache_size_mb": round(cache_size_mb, 2),
            "model_name": self.model_name,
            "model_path": self.model_path,
            "embedding_dimension": self.model.get_sentence_embedding_dimension()
        }
        
        logger.debug(f"Cache info requested: {info}")
        return info
