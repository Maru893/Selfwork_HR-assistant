import re
from abc import ABC, abstractmethod

import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

from hr_assistant.config import Config


class BaseChunker(ABC):
    @abstractmethod
    def split(self, text: str) -> list[str]:
        pass

    def clean_chunks(self, chunks: list[str]) -> list[str]:
        return [
            chunk.strip()
            for chunk in chunks
            if chunk and chunk.strip()
        ]


class SectionChunker(BaseChunker):
    def split(self, text: str) -> list[str]:
        chunks = text.split("### ")
        return self.clean_chunks(chunks)


class ParagraphChunker(BaseChunker):
    def split(self, text: str) -> list[str]:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text)
            if paragraph.strip()
        ]

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            candidate_chunk = (
                current_chunk + "\n\n" + paragraph
                if current_chunk
                else paragraph
            )

            if len(candidate_chunk) <= Config.CHUNK_SIZE:
                current_chunk = candidate_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                current_chunk = paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return self.clean_chunks(chunks)


class FixedSizeChunker(BaseChunker):
    def split(self, text: str) -> list[str]:
        chunks = []

        step = Config.CHUNK_SIZE - Config.CHUNK_OVERLAP

        if step <= 0:
            step = Config.CHUNK_SIZE

        for start in range(0, len(text), step):
            end = start + Config.CHUNK_SIZE
            chunk = text[start:end]

            if chunk.strip():
                chunks.append(chunk.strip())

        return self.clean_chunks(chunks)


class SemanticChunker(BaseChunker):
    def __init__(
        self,
        breakpoint_percentile: int | None = None,
        buffer_size: int | None = None,
    ):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=Config.OPENAI_KEY,
            model=Config.MODEL_NAME,
        )

        self.breakpoint_percentile = (
            breakpoint_percentile
            if breakpoint_percentile is not None
            else Config.SEMANTIC_BREAKPOINT_PERCENTILE
        )

        self.buffer_size = (
            buffer_size
            if buffer_size is not None
            else Config.SEMANTIC_BUFFER_SIZE
        )

    def split(self, text: str) -> list[str]:
        sentences = self._process_sentences(text)

        if len(sentences) <= 1:
            return [text.strip()] if text.strip() else []

        distances = self._calculate_distances(sentences)

        if not distances:
            return [text.strip()] if text.strip() else []

        threshold = np.percentile(
            distances,
            self.breakpoint_percentile,
        )

        split_points = [
            index
            for index, distance in enumerate(distances)
            if distance > threshold
        ]

        chunks = self._build_chunks_from_split_points(
            sentences=sentences,
            split_points=split_points,
        )

        return self._merge_small_chunks(chunks)

    def _process_sentences(self, text: str) -> list[dict]:
        raw_sentences = re.split(
            r"(?<=[.?!])\s+|\n+",
            text,
        )

        clean_sentences = [
            sentence.strip()
            for sentence in raw_sentences
            if sentence and sentence.strip()
        ]

        sentences = [
            {
                "sentence": sentence,
                "index": index,
            }
            for index, sentence in enumerate(clean_sentences)
        ]

        for index, current in enumerate(sentences):
            context_range = range(
                max(0, index - self.buffer_size),
                min(len(sentences), index + self.buffer_size + 1),
            )

            current["combined_sentence"] = " ".join(
                sentences[context_index]["sentence"]
                for context_index in context_range
            )

        return sentences

    def _calculate_distances(self, sentences: list[dict]) -> list[float]:
        combined_sentences = [
            sentence["combined_sentence"]
            for sentence in sentences
        ]

        embeddings = self.embeddings.embed_documents(
            combined_sentences
        )

        distances = []

        for index in range(len(sentences) - 1):
            distance = 1 - cosine_similarity(
                [embeddings[index]],
                [embeddings[index + 1]],
            )[0][0]

            distances.append(distance)

        return distances

    def _build_chunks_from_split_points(
        self,
        sentences: list[dict],
        split_points: list[int],
    ) -> list[str]:
        chunks = []
        start = 0

        for point in split_points + [len(sentences) - 1]:
            chunk = " ".join(
                sentence["sentence"]
                for sentence in sentences[start : point + 1]
            )

            if chunk.strip():
                chunks.append(chunk.strip())

            start = point + 1

        return chunks

    def _merge_small_chunks(self, chunks: list[str]) -> list[str]:
        merged_chunks = []
        current_chunk = ""

        for chunk in chunks:
            candidate_chunk = (
                current_chunk + " " + chunk
                if current_chunk
                else chunk
            )

            if len(candidate_chunk) < Config.SEMANTIC_MIN_CHUNK_SIZE:
                current_chunk = candidate_chunk
                continue

            if len(candidate_chunk) <= Config.CHUNK_SIZE:
                current_chunk = candidate_chunk
            else:
                if current_chunk:
                    merged_chunks.append(current_chunk)

                current_chunk = chunk

        if current_chunk:
            merged_chunks.append(current_chunk)

        return self.clean_chunks(merged_chunks)


class ChunkerFactory:
    @staticmethod
    def create() -> BaseChunker:
        strategy = Config.CHUNKING_STRATEGY

        if strategy == "section":
            return SectionChunker()

        if strategy == "paragraph":
            return ParagraphChunker()

        if strategy == "fixed":
            return FixedSizeChunker()

        if strategy == "semantic":
            return SemanticChunker()

        return SectionChunker()