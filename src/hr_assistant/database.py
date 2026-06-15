# database.py
import chromadb
from chromadb.utils import embedding_functions
from config import Config

class Database:
    def __init__(self):
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=Config.OPENAI_KEY, model_name=Config.MODEL_NAME
        )

        # FASE 3: Client persistente su disco. Crea la cartella data/chromadb in automatico!
        self.client = chromadb.PersistentClient(path=Config.PERSISTENT_DIR)
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.openai_ef
        )

    def add_documents(self, documents, metadatas, ids):
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def query(self, query_text, n_results=1):
        return self.collection.query(query_texts=[query_text], n_results=n_results)

    def count(self):
        # """FASE 3: Ritorna il numero di vettori salvati per evitare ricaricamenti inutili."""
        return self.collection.count()
