# document_processor.py
import os
import hashlib
from hr_assistant.config import Config


class DocumentProcessor:

    @staticmethod
    def read_first_lines(file_path, n_lines=100):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return [line.strip() for line, _ in zip(file, range(n_lines))]

    @staticmethod
    def get_file_hash(file_path):
        hash_sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    @staticmethod
    def get_document_metadata(file_path):
        return {
            "hash": DocumentProcessor.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
        }

    @staticmethod
    def process_single_document(file_path):
        documents = []
        metadatas = []
        ids = []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()

        chunks = content.replace("\n", ". ").split("### ")

        file_metadata = DocumentProcessor.get_document_metadata(file_path)
        source = file_metadata["source"]
        file_hash = file_metadata["hash"]

        for index, chunk in enumerate(chunks):
            clean_chunk = chunk.strip()

            if not clean_chunk:
                continue

            documents.append(clean_chunk)

            metadatas.append(
                {
                    **file_metadata,
                    "chunk_index": index,
                }
            )

            ids.append(
                f"{source}:{file_hash[:16]}:{index}"
            )

        return documents, metadatas, ids

    @staticmethod
    def process_documents(db):
        os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)

        current_files = {
            filename: DocumentProcessor.get_document_metadata(
                os.path.join(Config.DOCUMENTS_DIR, filename)
            )
            for filename in os.listdir(Config.DOCUMENTS_DIR)
            if filename.endswith(".txt")
        }

        existing_files = db.get_tracked_files()

        files_to_add = set(current_files.keys()) - set(existing_files.keys())

        files_to_remove = set(existing_files.keys()) - set(current_files.keys())

        files_to_update = {
            filename
            for filename in set(current_files.keys()) & set(existing_files.keys())
            if current_files[filename]["hash"] != existing_files[filename]["hash"]
        }

        indexed_chunks = 0

        for action, files in [
            ("add", files_to_add),
            ("update", files_to_update),
        ]:
            for filename in files:
                file_path = os.path.join(Config.DOCUMENTS_DIR, filename)

                documents, metadatas, ids = DocumentProcessor.process_single_document(
                    file_path
                )

                if action == "update":
                    db.remove_document_by_source(filename)

                if documents:
                    db.add_documents(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids,
                    )

                    indexed_chunks += len(documents)

        for filename in files_to_remove:
            db.remove_document_by_source(filename)

        unchanged_files = (
            set(current_files.keys())
            - files_to_add
            - files_to_update
        )

        return {
            "added": len(files_to_add),
            "updated": len(files_to_update),
            "removed": len(files_to_remove),
            "unchanged": len(unchanged_files),
            "total_files": len(current_files),
            "indexed_chunks": indexed_chunks,
            "added_files": sorted(files_to_add),
            "updated_files": sorted(files_to_update),
            "removed_files": sorted(files_to_remove),
            "unchanged_files": sorted(unchanged_files),
        }