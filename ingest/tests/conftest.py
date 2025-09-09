"""
Pytest configuration and fixtures for ingest tests.
"""

import sys
from pathlib import Path

import pytest

# Add the ingest directory to Python path so we can import services
ingest_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ingest_dir))

# Also add the bot directory for bot services
bot_dir = ingest_dir.parent / "bot"
sys.path.insert(0, str(bot_dir))


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF bytes for testing."""
    # Minimal PDF structure for testing
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000105 00000 n
0000000179 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
268
%%EOF"""


@pytest.fixture
def sample_text_content():
    """Sample text content for testing."""
    return "This is sample text content for testing document processing."


@pytest.fixture
def sample_file_metadata():
    """Sample file metadata for testing."""
    return {
        'id': 'test_file_id',
        'name': 'test_document.pdf',
        'mimeType': 'application/pdf',
        'size': '1024',
        'modifiedTime': '2023-01-01T00:00:00.000Z',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
        'owners': [
            {
                'emailAddress': 'owner@example.com',
                'displayName': 'Test Owner'
            }
        ],
        'permissions': {
            'readers': [],
            'writers': [],
            'owners': [
                {
                    'type': 'user',
                    'email': 'owner@example.com',
                    'display_name': 'Test Owner',
                    'role': 'owner'
                }
            ],
            'is_public': False,
            'anyone_can_read': False,
            'anyone_can_write': False
        },
        'folder_path': 'Documents/Project',
        'full_path': 'Documents/Project/test_document.pdf'
    }


@pytest.fixture
def sample_google_docs_metadata():
    """Sample Google Docs metadata for testing."""
    return {
        'id': 'test_gdoc_id',
        'name': 'Test Google Doc',
        'mimeType': 'application/vnd.google-apps.document',
        'size': None,
        'modifiedTime': '2023-01-01T00:00:00.000Z',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'webViewLink': 'https://docs.google.com/document/d/test_gdoc_id/edit',
        'owners': [],
        'permissions': {
            'readers': [],
            'writers': [],
            'owners': [],
            'is_public': False,
            'anyone_can_read': False,
            'anyone_can_write': False
        },
        'folder_path': '',
        'full_path': 'Test Google Doc'
    }


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/to/service_account.json")
    monkeypatch.setenv("VECTOR_ENABLED", "true")
    monkeypatch.setenv("VECTOR_PROVIDER", "chroma")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")


# Async test marker for pytest-asyncio
pytest_plugins = ['pytest_asyncio']
