#!/usr/bin/env python3
"""
Legacy compatibility wrapper for the old ingester.py

This file maintains backward compatibility for any code that imports from ingester.py.
The actual implementation has been refactored into modular services:
- services/document_processor.py
- services/google_drive_client.py
- services/ingestion_orchestrator.py

DEPRECATED: Use the new modular services or main.py entry point instead.
"""

import warnings

from services import GoogleDriveClient, IngestionOrchestrator

# Issue deprecation warning
warnings.warn(
    "ingester.py is deprecated. Use the new modular services or main.py instead. "
    "See services/ directory for the refactored implementation.",
    DeprecationWarning,
    stacklevel=2
)

# Compatibility class that mimics the old GoogleDriveIngester
class GoogleDriveIngester:
    """
    DEPRECATED: Legacy compatibility wrapper.
    Use services.IngestionOrchestrator instead.
    """

    def __init__(self, credentials_file=None, token_file=None):
        warnings.warn(
            "GoogleDriveIngester is deprecated. Use services.IngestionOrchestrator instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.orchestrator = IngestionOrchestrator(credentials_file, token_file)
        self.google_drive_client = self.orchestrator.google_drive_client
        self.document_processor = self.google_drive_client.document_processor

        # Legacy compatibility attributes
        self.service = None
        self.vector_service = None
        self.embedding_service = None

    def authenticate(self):
        """Legacy compatibility method."""
        result = self.orchestrator.authenticate()
        if result:
            self.service = self.google_drive_client.service
        return result

    def list_folder_contents(self, folder_id, recursive=True, folder_path=""):
        """Legacy compatibility method."""
        return self.google_drive_client.list_folder_contents(folder_id, recursive, folder_path)

    def download_file_content(self, file_id, mime_type):
        """Legacy compatibility method."""
        return self.google_drive_client.download_file_content(file_id, mime_type)

    def set_services(self, vector_service, embedding_service):
        """Legacy compatibility method."""
        self.vector_service = vector_service
        self.embedding_service = embedding_service
        self.orchestrator.set_services(vector_service, embedding_service)

    async def ingest_files(self, files, metadata=None):
        """Legacy compatibility method."""
        return await self.orchestrator.ingest_files(files, metadata)

    async def ingest_folder(self, folder_id, recursive=True, metadata=None):
        """Legacy compatibility method."""
        return await self.orchestrator.ingest_folder(folder_id, recursive, metadata)

    # Legacy document processing methods
    def _extract_pdf_text(self, pdf_content):
        """Legacy compatibility method."""
        return self.document_processor._extract_pdf_text(pdf_content)

    def _extract_docx_text(self, docx_content):
        """Legacy compatibility method."""
        return self.document_processor._extract_docx_text(docx_content)

    def _extract_xlsx_text(self, xlsx_content):
        """Legacy compatibility method."""
        return self.document_processor._extract_xlsx_text(xlsx_content)

    def _extract_pptx_text(self, pptx_content):
        """Legacy compatibility method."""
        return self.document_processor._extract_pptx_text(pptx_content)

    # Legacy permission methods
    def _format_permissions(self, permissions):
        """Legacy compatibility method."""
        return GoogleDriveClient.format_permissions(permissions)

    def _get_permissions_summary(self, permissions):
        """Legacy compatibility method."""
        return GoogleDriveClient.get_permissions_summary(permissions)

    def _get_owner_emails(self, owners):
        """Legacy compatibility method."""
        return GoogleDriveClient.get_owner_emails(owners)


# Legacy main function for backward compatibility
async def main():
    """
    DEPRECATED: Legacy main function.
    Use main.py instead: python main.py --folder-id YOUR_FOLDER_ID
    """
    warnings.warn(
        "Using ingester.py as main entry point is deprecated. Use main.py instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Import and run the new main function
    from main import main as new_main
    await new_main()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
