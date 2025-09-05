# Google Drive Document Ingestion - THE ONLY SUPPORTED METHOD

This is the sole document ingestion system for the RAG pipeline. It provides comprehensive Google Drive authentication and ingests documents with rich metadata including file paths and permissions.

## Setup

1. **Install dependencies:**
   ```bash
   cd ingest
   pip install -r requirements.txt
   ```

2. **Google Drive API Setup:**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable the Google Drive API
   - Create OAuth2 credentials (Desktop application type)
   - Download the credentials as `credentials.json` and place in this directory

3. **Environment Configuration:**
   Ensure your `.env` file has the vector database settings:
   ```bash
   VECTOR_ENABLED=true
   VECTOR_PROVIDER=chroma  # or pinecone
   VECTOR_URL=http://localhost:8000
   EMBEDDING_PROVIDER=openai
   EMBEDDING_MODEL=text-embedding-3-small
   ```

## Usage

### Basic Usage

Ingest all documents from a Google Drive folder:

```bash
python google_drive_ingester.py --folder-id "1ABC123DEF456GHI789"
```

### Advanced Usage

```bash
# Ingest with custom metadata
python google_drive_ingester.py \
  --folder-id "1ABC123DEF456GHI789" \
  --metadata '{"department": "engineering", "project": "docs"}'

# Use custom credentials file
python google_drive_ingester.py \
  --folder-id "1ABC123DEF456GHI789" \
  --credentials "./my-credentials.json" \
  --token "./my-token.json"

# Non-recursive (only top-level folder)
python google_drive_ingester.py \
  --folder-id "1ABC123DEF456GHI789" \
  --recursive false
```

## Finding Folder IDs

1. Open the Google Drive folder in your browser
2. The folder ID is in the URL: `https://drive.google.com/drive/folders/[FOLDER_ID]`
3. Copy the folder ID for use with the ingester

## Supported File Types

- Google Docs (exported as plain text)
- Google Sheets (exported as CSV)
- Google Slides (exported as plain text)
- Plain text files (.txt, .md, etc.)
- PDF files
- Other text-based formats

## Authentication Flow

1. On first run, the script will open a browser for OAuth2 authentication
2. Grant the requested permissions
3. The token will be saved locally for future runs
4. Token will be automatically refreshed when needed

## Comprehensive Metadata

Each ingested document includes rich metadata for enhanced search and access control:

### File Information
- `source`: Always "google_drive"  
- `file_id`: Google Drive file ID
- `file_name`: Original file name
- `full_path`: Complete path within Google Drive (e.g., "Projects/Documentation/API Guide.pdf")
- `folder_path`: Parent folder path
- `mime_type`: File MIME type
- `web_view_link`: Direct Google Drive viewing URL

### Timestamps
- `modified_time`: Last modified timestamp from Google Drive
- `created_time`: File creation timestamp
- `ingested_at`: When document was processed into the system

### File Properties
- `size`: File size in bytes
- `owners`: List of file owners with email and display name

### Permissions (Comprehensive Access Control)
- `permissions.readers`: Users/groups with read access
- `permissions.writers`: Users/groups with write access  
- `permissions.owners`: File owners
- `permissions.is_public`: Whether file is publicly accessible
- `permissions.anyone_can_read`: Public read access
- `permissions.anyone_can_write`: Public write access

Each permission entry includes:
- `type`: user, group, domain, or anyone
- `email`: Email address (when applicable)
- `display_name`: Human-readable name
- `role`: owner, writer, editor, reader, or commenter

### Custom Metadata
- Any additional metadata provided via `--metadata` flag

## Security Notes

- Keep `credentials.json` and `token.json` secure and never commit to version control
- Add them to your `.gitignore` file
- The ingester only requests read-only access to your Google Drive
- All document content is processed locally before being stored in your vector database
