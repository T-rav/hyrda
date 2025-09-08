# Document Ingestion Services

This directory contains the refactored modular services for document ingestion from Google Drive.

## 🏗️ Service Architecture

### 📄 DocumentProcessor (`document_processor.py`)

**Purpose:** Text extraction from various document formats  
**Responsibilities:**
- Extract text from PDF files using PyMuPDF
- Extract text from Word documents (.docx) including tables
- Extract text from Excel spreadsheets (.xlsx) with multi-sheet support
- Extract text from PowerPoint presentations (.pptx) including slide tables
- Handle plain text files with proper encoding detection

**Usage:**
```python
from services import DocumentProcessor

processor = DocumentProcessor()
text = processor.extract_text(file_bytes, 'application/pdf')
```

### 🔗 GoogleDriveClient (`google_drive_client.py`)

**Purpose:** Google Drive API operations and authentication  
**Responsibilities:**
- OAuth2 authentication with environment variable fallback
- List folder contents with comprehensive metadata
- Download file content from Google Drive
- Handle Google Workspace document export
- Extract permissions and sharing information
- Support for shared drives and complex folder structures

**Usage:**
```python
from services import GoogleDriveClient

client = GoogleDriveClient()
client.authenticate()
files = client.list_folder_contents('folder_id', recursive=True)
content = client.download_file_content('file_id', 'mime_type')
```

### 🎭 IngestionOrchestrator (`ingestion_orchestrator.py`)

**Purpose:** Main workflow coordination  
**Responsibilities:**
- Coordinate between GoogleDriveClient and DocumentProcessor
- Manage vector database and embedding service integration
- Handle chunking and embedding generation
- Orchestrate the complete ingestion workflow
- Provide progress tracking and error handling

**Usage:**
```python
from services import IngestionOrchestrator

orchestrator = IngestionOrchestrator()
orchestrator.authenticate()
orchestrator.set_services(vector_service, embedding_service)
success, errors = await orchestrator.ingest_folder('folder_id')
```

## 🔄 Migration Guide

### From Legacy `ingester.py`:

**Old Way:**
```python
from ingester import GoogleDriveIngester

ingester = GoogleDriveIngester()
ingester.authenticate()
ingester.set_services(vector_service, embedding_service)
success, errors = await ingester.ingest_folder(folder_id)
```

**New Way:**
```python
from services import IngestionOrchestrator

orchestrator = IngestionOrchestrator()
orchestrator.authenticate()
orchestrator.set_services(vector_service, embedding_service)
success, errors = await orchestrator.ingest_folder(folder_id)
```

### Direct Service Usage:

```python
# Use individual services as needed
from services import DocumentProcessor, GoogleDriveClient

# Just document processing
processor = DocumentProcessor()
text = processor.extract_text(pdf_bytes, 'application/pdf')

# Just Google Drive operations  
drive_client = GoogleDriveClient()
drive_client.authenticate()
files = drive_client.list_folder_contents('folder_id')
```

## 🧪 Testing

Each service can be tested independently:

```python
# Test DocumentProcessor
from services import DocumentProcessor
processor = DocumentProcessor()
# Test with sample documents...

# Test GoogleDriveClient (requires auth)  
from services import GoogleDriveClient
client = GoogleDriveClient()
# Test authentication and file operations...

# Test IngestionOrchestrator
from services import IngestionOrchestrator  
orchestrator = IngestionOrchestrator()
# Test full workflow...
```

## 📊 Supported Document Formats

| Format | Extension | Library | Features |
|--------|-----------|---------|----------|
| PDF | `.pdf` | PyMuPDF | Multi-page text extraction |
| Word | `.docx` | python-docx | Paragraphs + tables |
| Excel | `.xlsx` | openpyxl | Multi-sheet + all cells |
| PowerPoint | `.pptx` | python-pptx | Slides + shapes + tables |
| Google Docs | - | Google Drive API | Export as plain text |
| Google Sheets | - | Google Drive API | Export as CSV |
| Google Slides | - | Google Drive API | Export as plain text |
| Text Files | `.txt`, `.md`, etc. | Built-in | UTF-8/Latin-1 encoding |

## 🔧 Dependencies

**Document Processing:**
- `pymupdf>=1.23.0` - PDF text extraction
- `python-docx>=1.1.0` - Word document processing  
- `openpyxl>=3.1.0` - Excel spreadsheet processing
- `python-pptx>=0.6.23` - PowerPoint presentation processing

**Google Drive API:**
- `google-api-python-client>=2.108.0`
- `google-auth-httplib2>=0.2.0`
- `google-auth-oauthlib>=1.1.0`

## 💡 Benefits of Modular Architecture

✅ **Single Responsibility** - Each service has one clear purpose  
✅ **Testability** - Services can be tested in isolation  
✅ **Maintainability** - Changes are localized to specific services  
✅ **Reusability** - Services can be used independently  
✅ **Extensibility** - Easy to add new document processors or clients  
✅ **Debugging** - Easier to trace issues to specific services
