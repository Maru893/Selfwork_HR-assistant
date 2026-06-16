import os
import re
import hashlib
import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from markitdown import MarkItDown

from hr_assistant.config import Config
from hr_assistant.chunking import ChunkerFactory


class DocumentProcessor:
    SUPPORTED_EXTENSIONS = {
        ".txt": "text",
        ".pdf": "document",
        ".doc": "document",
        ".docx": "document",
        ".ppt": "presentation",
        ".pptx": "presentation",
        ".xls": "spreadsheet",
        ".xlsx": "spreadsheet",
        ".html": "web",
        ".htm": "web",
        ".csv": "data",
        ".json": "data",
        ".xml": "data",
        ".zip": "archive",
    }

    _markdown_converter = None

    @classmethod
    def get_markdown_converter(cls):
        if cls._markdown_converter is None:
            cls._markdown_converter = MarkItDown()

        return cls._markdown_converter

    @classmethod
    def is_supported_file(cls, file_path: str) -> bool:
        extension = Path(file_path).suffix.lower()
        return extension in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_supported_extensions(cls) -> tuple[str, ...]:
        return tuple(cls.SUPPORTED_EXTENSIONS.keys())

    @staticmethod
    def read_first_lines(file_path: str, n_lines: int = 100) -> list[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                return [line.strip() for line, _ in zip(file, range(n_lines))]
        except Exception:
            return []

    @staticmethod
    def read_document(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return file.read()

    @staticmethod
    def get_file_hash(file_path: str) -> str:
        hash_sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    @staticmethod
    def get_chunking_signature() -> str:
        return (
            f"{Config.PROCESSOR_VERSION}|"
            f"{Config.CHUNKING_STRATEGY}|"
            f"{Config.CHUNK_SIZE}|"
            f"{Config.CHUNK_OVERLAP}|"
            f"{Config.SEMANTIC_BREAKPOINT_PERCENTILE}|"
            f"{Config.SEMANTIC_BUFFER_SIZE}|"
            f"{Config.SEMANTIC_MIN_CHUNK_SIZE}"
        )

    @staticmethod
    def extract_candidate_info(text: str) -> dict[str, str]:
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
            "formazione",
            "lingue",
        ]

        for line in lines[:12]:
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

    @classmethod
    def get_document_metadata(
        cls,
        file_path: str,
        content: str = "",
        internal_files_count: int = 0,
    ) -> dict[str, Any]:
        extension = Path(file_path).suffix.lower()
        file_type = cls.SUPPORTED_EXTENSIONS.get(extension, "unknown")
        mime_type = mimetypes.guess_type(file_path)[0] or ""

        candidate_info = cls.extract_candidate_info(content)

        return {
            "hash": cls.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
            "file_type": file_type,
            "mime_type": mime_type,
            "extension": extension,
            "internal_files_count": internal_files_count,
            "chunking_signature": cls.get_chunking_signature(),
            "candidate_name": candidate_info["candidate_name"],
            "email": candidate_info["email"],
            "phone": candidate_info["phone"],
        }

    @classmethod
    def convert_to_markdown(cls, file_path: str) -> str:
        extension = Path(file_path).suffix.lower()

        if extension == ".txt":
            return cls.read_document(file_path)

        try:
            converter = cls.get_markdown_converter()
            result = converter.convert(file_path)
            return result.text_content or ""

        except Exception as error:
            print(f"Errore nella conversione di {file_path}: {error}")

            if extension in {".csv", ".json", ".xml", ".html", ".htm"}:
                return cls.read_document(file_path)

            return ""

    @classmethod
    def process_zip_file(cls, file_path: str) -> tuple[str, int]:
        converted_parts = []

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir).resolve()

                with ZipFile(file_path, "r") as zip_ref:
                    for member in zip_ref.infolist():
                        if member.is_dir():
                            continue

                        member_extension = Path(member.filename).suffix.lower()

                        if member_extension not in cls.SUPPORTED_EXTENSIONS:
                            continue

                        if member_extension == ".zip":
                            continue

                        target_path = (temp_dir_path / member.filename).resolve()

                        if not str(target_path).startswith(str(temp_dir_path)):
                            continue

                        zip_ref.extract(member, temp_dir_path)

                        content = cls.convert_to_markdown(str(target_path))

                        if content.strip():
                            converted_parts.append(
                                f"## File interno: {member.filename}\n\n{content}"
                            )

        except BadZipFile:
            print(f"Archivio ZIP non valido: {file_path}")
            return "", 0

        except Exception as error:
            print(f"Errore nel processare lo ZIP {file_path}: {error}")
            return "", 0

        return "\n\n".join(converted_parts), len(converted_parts)

    @classmethod
    def load_document_content(cls, file_path: str) -> tuple[str, int]:
        extension = Path(file_path).suffix.lower()
        file_type = cls.SUPPORTED_EXTENSIONS.get(extension)

        if not file_type:
            return "", 0

        if file_type == "archive":
            return cls.process_zip_file(file_path)

        content = cls.convert_to_markdown(file_path)
        return content, 0

    @staticmethod
    def split_text_into_chunks(text: str) -> list[str]:
        chunker = ChunkerFactory.create()
        return chunker.split(text)

    @classmethod
    def process_single_document(
        cls,
        file_path: str,
    ) -> tuple[list[str], list[dict], list[str]]:
        documents = []
        metadatas = []
        ids = []

        if not cls.is_supported_file(file_path):
            return [], [], []

        content, internal_files_count = cls.load_document_content(file_path)

        if not content.strip():
            return [], [], []

        chunks = cls.split_text_into_chunks(content)

        file_metadata = cls.get_document_metadata(
            file_path=file_path,
            content=content,
            internal_files_count=internal_files_count,
        )

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

    @classmethod
    def process_documents(cls, db):
        os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)

        current_files = {
            filename: cls.get_document_metadata(
                os.path.join(Config.DOCUMENTS_DIR, filename)
            )
            for filename in os.listdir(Config.DOCUMENTS_DIR)
            if cls.is_supported_file(filename)
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

                documents, metadatas, ids = cls.process_single_document(file_path)

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