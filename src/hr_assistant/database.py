# database.py
import chromadb
from chromadb.utils import embedding_functions
from hr_assistant.config import Config

class Database:
    def __init__(self):
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=Config.OPENAI_KEY, model_name=Config.MODEL_NAME
        )

        # Client persistente su disco. Crea la cartella data/chromadb in automatico!
        self.client = chromadb.PersistentClient(path=Config.PERSISTENT_DIR)

        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.openai_ef
        )

    def add_documents(self, documents, metadatas, ids):
        if not documents:
            return
        
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def query(self, query_text, n_results=1):
        return self.collection.query(query_texts=[query_text], n_results=n_results)

    def get_tracked_files(self):
        result = self.collection.get(
            include=["metadatas"]
        )

        tracked_files = {}

        metadatas = result.get("metadatas", []) if result else []

        for metadata in metadatas:
            if not metadata:
                continue

            source = metadata.get("source")
            file_hash = metadata.get("hash")
            last_modified = metadata.get("last_modified")

            if source and source not in tracked_files:
                tracked_files[source] = {
                    "hash": file_hash,
                    "last_modified": last_modified,
                    "source": source,
                }

        return tracked_files

    def remove_document_by_source(self, source):
        self.collection.delete(
            where={"source": source}
        )

    def count(self):
        return self.collection.count()

    def reset(self):

        try:
            self.client.delete_collection(
                name=Config.COLLECTION_NAME
            )
        except ValueError:
            pass

        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME,
            embedding_function=self.openai_ef,
        )
