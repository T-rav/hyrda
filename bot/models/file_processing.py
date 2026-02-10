"""Typed models for file processing and document handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FileType(StrEnum):
    """Supported file types for processing."""

    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    PPTX = "pptx"
    PPT = "ppt"
    TXT = "txt"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "md"
    HTML = "html"
    SUBTITLE_SRT = "srt"
    SUBTITLE_VTT = "vtt"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, extension: str) -> FileType:
        """Get file type from extension."""
        ext_map = {
            ".pdf": cls.PDF,
            ".docx": cls.DOCX,
            ".doc": cls.DOC,
            ".xlsx": cls.XLSX,
            ".xls": cls.XLS,
            ".pptx": cls.PPTX,
            ".ppt": cls.PPT,
            ".txt": cls.TXT,
            ".csv": cls.CSV,
            ".json": cls.JSON,
            ".md": cls.MARKDOWN,
            ".html": cls.HTML,
            ".srt": cls.SUBTITLE_SRT,
            ".vtt": cls.SUBTITLE_VTT,
        }
        return ext_map.get(extension.lower(), cls.UNKNOWN)


class ProcessingStatus(StrEnum):
    """File processing status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FileMetadata(BaseModel):
    file_id: str
    filename: str
    file_type: FileType
    size_bytes: int
    mime_type: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    author: str | None = None
    title: str | None = None
    subject: str | None = None
    keywords: list[str] = Field(default_factory=list)
    language: str | None = None
    page_count: int | None = None
    word_count: int | None = None

    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class ProcessingResult:
    file_metadata: FileMetadata
    status: ProcessingStatus
    content: str | None = None
    extracted_text: str | None = None
    chunks: list[str] | None = None
    chunk_count: int = 0
    processing_time_ms: float = 0.0
    error_message: str | None = None
    warnings: list[str] | None = None


@dataclass(frozen=True)
class SlackFileInfo:
    id: str
    name: str
    title: str | None
    mimetype: str | None
    filetype: str | None
    size: int
    url_private: str
    url_private_download: str
    permalink: str | None = None
    permalink_public: str | None = None
    user: str | None = None
    timestamp: str | None = None
    is_external: bool = False
    is_public: bool = False

    @property
    def file_type(self) -> FileType:
        if self.filetype:
            return FileType.from_extension(f".{self.filetype}")
        elif self.mimetype:
            mime_map = {
                "application/pdf": FileType.PDF,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
                "application/msword": FileType.DOC,
                "text/plain": FileType.TXT,
                "text/csv": FileType.CSV,
                "application/json": FileType.JSON,
                "text/html": FileType.HTML,
                "text/markdown": FileType.MARKDOWN,
            }
            return mime_map.get(self.mimetype, FileType.UNKNOWN)
        return FileType.UNKNOWN


@dataclass(frozen=True)
class DocumentChunk:
    content: str
    chunk_id: str
    document_id: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: FileMetadata
    embedding: list[float] | None = None
    similarity_score: float | None = None


class EmbeddingResult(BaseModel):
    text: str
    embedding: list[float]
    model_name: str
    dimensions: int
    processing_time_ms: float
    token_count: int | None = None

    model_config = ConfigDict(frozen=True)
