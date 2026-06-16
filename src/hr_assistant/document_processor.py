# document_processor.py

import os
import re
import hashlib
from hr_assistant.config import Config
from hr_assistant.chunking import ChunkerFactory


class DocumentProcessor:

    @staticmethod
    def read_first_lines(file_path, n_lines=100):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return [line.strip() for line, _ in zip(file, range(n_lines))]

    @staticmethod
    def read_document(file_path):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return file.read()

    @staticmethod
    def get_file_hash(file_path):
        hash_sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    @staticmethod
    def get_chunking_signature():
        return (
            f"{Config.CHUNKING_STRATEGY}|"
            f"{Config.CHUNK_SIZE}|"
            f"{Config.CHUNK_OVERLAP}|"
            f"{Config.SEMANTIC_BREAKPOINT_PERCENTILE}|"
            f"{Config.SEMANTIC_BUFFER_SIZE}|"
            f"{Config.SEMANTIC_MIN_CHUNK_SIZE}"
        )

    @staticmethod
    def extract_candidate_info(text): # cerca nome, email e telefono senza chiamare il modello 
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        email_match = re.search(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            text,
        )

        phone_match = re.search(
            r"(?:\+?\d[\d\s().-]{7,}\d)",
            text,
        )

        email = email_match.group(0) if email_match else ""

        phone = ""
        if phone_match:
            raw_phone = phone_match.group(0).strip()
            digits = re.sub(r"\D", "", raw_phone)

            if 8 <= len(digits) <= 15:
                phone = raw_phone

        candidate_name = ""

        excluded_words = [
            "curriculum",
            "cv",
            "profilo",
            "telefono",
            "email",
            "e-mail",
            "contatti",
            "esperienza",
            "competenze",
        ]

        for line in lines[:10]:
            lowered = line.lower()

            if any(word in lowered for word in excluded_words):
                continue

            if "@" in line:
                continue

            if re.search(r"\d", line):
                continue

            if 2 <= len(line.split()) <= 4:
                candidate_name = line
                break

        return {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
        }

    @staticmethod
    def get_document_metadata(file_path):
        text = DocumentProcessor.read_document(file_path)
        candidate_info = DocumentProcessor.extract_candidate_info(text)

        return {
            "hash": DocumentProcessor.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
            "chunking_signature": DocumentProcessor.get_chunking_signature(),
            "candidate_name": candidate_info["candidate_name"],
            "email": candidate_info["email"],
            "phone": candidate_info["phone"],
        }

    @staticmethod
    def split_text_into_chunks(text):
        chunker = ChunkerFactory.create()
        return chunker.split(text)

    @staticmethod
    def process_single_document(file_path):
        documents = []
        metadatas = []
        ids = []

        content = DocumentProcessor.read_document(file_path)

        chunks = DocumentProcessor.split_text_into_chunks(content)

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
            if (
                current_files[filename]["hash"] != existing_files[filename].get("hash")
                or current_files[filename]["chunking_signature"]
                != existing_files[filename].get("chunking_signature")
            )
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