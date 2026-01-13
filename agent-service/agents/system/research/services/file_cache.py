"""File cache manager for research agent using MinIO/S3.

Smart caching system with proper naming conventions for SEC data, web pages, PDFs, etc.
All files stored in MinIO S3-compatible object storage with 30-day lifecycle policies.
"""

import hashlib
import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from ..configuration import FILE_NAMING_PATTERNS
from ..state import CachedFile

logger = logging.getLogger(__name__)


class ResearchFileCache:
    """Smart file cache using MinIO/S3 for distributed storage."""

    # Bucket names for each file type
    BUCKETS = {
        "sec_filing": "research-sec-filings",
        "web_page": "research-web-pages",
        "pdf": "research-pdfs",
        "json_data": "research-json-data",
    }

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
    ):
        """Initialize MinIO/S3 cache manager.

        Args:
            endpoint_url: MinIO endpoint (e.g., http://minio:9000)
            access_key: MinIO access key
            secret_key: MinIO secret key
            region: AWS region (default: us-east-1)

        Raises:
            ValueError: If MinIO connection fails
        """
        # Get config from env vars if not provided
        self.endpoint_url = endpoint_url or os.getenv("MINIO_ENDPOINT")  # Internal endpoint for boto3
        self.public_url = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")  # Public endpoint for presigned URLs
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")
        self.region = region

        if not self.endpoint_url:
            raise ValueError(
                "MINIO_ENDPOINT not configured. Set MINIO_ENDPOINT env var or pass endpoint_url."
            )
        if not self.access_key:
            raise ValueError(
                "MINIO_ACCESS_KEY not configured. Set MINIO_ACCESS_KEY env var or pass access_key."
            )
        if not self.secret_key:
            raise ValueError(
                "MINIO_SECRET_KEY not configured. Set MINIO_SECRET_KEY env var or pass secret_key."
            )

        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

            # Test connection
            self.s3_client.list_buckets()
            logger.info(f"✅ MinIO connected successfully: {self.endpoint_url}")

        except Exception as e:
            raise ValueError(f"Failed to connect to MinIO at {self.endpoint_url}: {e}")

        # Create buckets if they don't exist
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        """Create required buckets if they don't exist."""
        for bucket_name in self.BUCKETS.values():
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.debug(f"Bucket exists: {bucket_name}")
            except ClientError:
                # Bucket doesn't exist, create it
                try:
                    self.s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"✅ Created bucket: {bucket_name}")

                    # Set lifecycle policy (30-day expiration)
                    lifecycle_config = {
                        "Rules": [
                            {
                                "Id": "ExpireAfter30Days",
                                "Status": "Enabled",
                                "Expiration": {"Days": 30},
                            }
                        ]
                    }
                    self.s3_client.put_bucket_lifecycle_configuration(
                        Bucket=bucket_name, LifecycleConfiguration=lifecycle_config
                    )
                    logger.info(f"✅ Set 30-day lifecycle policy on {bucket_name}")

                except Exception as e:
                    logger.error(f"Failed to create bucket {bucket_name}: {e}")

    def _generate_file_name(self, file_type: str, metadata: dict[str, Any]) -> str:
        """Generate smart file name based on type and metadata.

        Args:
            file_type: Type of file (sec_filing, web_page, pdf, json_data)
            metadata: Metadata dict with context-specific fields

        Returns:
            Generated filename following naming conventions
        """
        pattern = FILE_NAMING_PATTERNS.get(file_type, "{timestamp}.txt")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            if file_type == "sec_filing":
                # SEC filing: company_10K_2023_Q4.txt
                return pattern.format(
                    company=self._sanitize(metadata.get("company", "unknown")),
                    form_type=metadata.get("form_type", "10K"),
                    year=metadata.get("year", datetime.now().year),
                    quarter=metadata.get("quarter", ""),
                )
            elif file_type == "web_page":
                # Web page: example_com_article_slug_20231215.html
                url = metadata.get("url", "")
                domain = urlparse(url).netloc.replace(".", "_") if url else "web"
                slug = self._sanitize(metadata.get("title", "page"))[:50]
                return pattern.format(domain=domain, slug=slug, timestamp=timestamp)
            elif file_type == "pdf":
                # PDF: arxiv_paper_title_20231215.pdf
                source = self._sanitize(metadata.get("source", "unknown"))
                title = self._sanitize(metadata.get("title", "document"))[:50]
                return pattern.format(source=source, title=title, timestamp=timestamp)
            elif file_type == "json_data":
                # JSON data: api_query_hash_20231215.json
                source = self._sanitize(metadata.get("source", "data"))
                query = metadata.get("query", "")
                query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
                return pattern.format(
                    source=source, query_hash=query_hash, timestamp=timestamp
                )
            else:
                # Fallback
                return f"{file_type}_{timestamp}.txt"
        except Exception as e:
            logger.warning(f"Error generating filename: {e}, using fallback")
            return f"{file_type}_{timestamp}.txt"

    def _sanitize(self, text: str) -> str:
        """Sanitize text for use in filenames.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text safe for filenames
        """
        # Remove special characters, keep alphanumeric and basic punctuation
        sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in text)
        # Remove multiple underscores
        sanitized = "_".join(filter(None, sanitized.split("_")))
        return sanitized.lower()

    def cache_file(
        self, file_type: str, content: str | bytes, metadata: dict[str, Any]
    ) -> CachedFile:
        """Cache a file to MinIO S3.

        Args:
            file_type: Type of file (sec_filing, web_page, pdf, json_data)
            content: File content (text or bytes)
            metadata: Metadata dict (url, company, title, etc.)

        Returns:
            CachedFile object with cache details

        Raises:
            ValueError: If file_type is invalid
            ClientError: If S3 upload fails
        """
        bucket_name = self.BUCKETS.get(file_type)
        if not bucket_name:
            raise ValueError(
                f"Invalid file_type: {file_type}. Must be one of {list(self.BUCKETS.keys())}"
            )

        # Generate smart filename
        filename = self._generate_file_name(file_type, metadata)

        # Convert to bytes if string
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content

        # Store metadata in S3 object metadata
        s3_metadata = {
            "file_type": file_type,
            "cached_at": datetime.now().isoformat(),
            **{k: str(v) for k, v in metadata.items() if v is not None},
        }

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=filename,
                Body=content_bytes,
                Metadata=s3_metadata,
            )

            size_bytes = len(content_bytes)
            file_id = hashlib.md5(f"{bucket_name}/{filename}".encode()).hexdigest()[:12]

            logger.info(
                f"✅ Cached {file_type} to MinIO: s3://{bucket_name}/{filename} ({size_bytes} bytes) ID={file_id}"
            )

            return CachedFile(
                file_id=file_id,
                file_type=file_type,
                file_path=f"s3://{bucket_name}/{filename}",
                metadata=metadata,
                cached_at=datetime.now().isoformat(),
                size_bytes=size_bytes,
            )

        except ClientError as e:
            logger.error(f"Failed to upload to MinIO: {e}")
            raise

    def retrieve_file(self, file_path: str) -> str | bytes | None:
        """Retrieve cached file from MinIO S3.

        Args:
            file_path: S3 path (s3://bucket/key)

        Returns:
            File content or None if not found
        """
        try:
            # Parse S3 path
            if not file_path.startswith("s3://"):
                logger.error(f"Invalid S3 path: {file_path}")
                return None

            path_parts = file_path[5:].split("/", 1)
            if len(path_parts) != 2:
                logger.error(f"Invalid S3 path format: {file_path}")
                return None

            bucket_name, key = path_parts

            # Download from S3
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            content_bytes = response["Body"].read()

            # Try to decode as text, fall back to bytes
            try:
                return content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return content_bytes

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"File not found in MinIO: {file_path}")
            else:
                logger.error(f"Error retrieving from MinIO: {e}")
            return None

    def search_cache(
        self, query: str, file_type: str | None = None
    ) -> list[CachedFile]:
        """Search cached files in MinIO by query and optional file type.

        Args:
            query: Search query (matches filenames)
            file_type: Optional filter by file type

        Returns:
            List of matching CachedFile objects
        """
        matches = []
        query_lower = query.lower()

        # Determine which buckets to search
        if file_type:
            bucket_name = self.BUCKETS.get(file_type)
            if not bucket_name:
                logger.warning(f"Invalid file_type for search: {file_type}")
                return []
            buckets_to_search = [(file_type, bucket_name)]
        else:
            buckets_to_search = list(self.BUCKETS.items())

        # Search buckets
        for ftype, bucket_name in buckets_to_search:
            try:
                response = self.s3_client.list_objects_v2(Bucket=bucket_name)

                if "Contents" not in response:
                    continue

                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Match by filename
                    if query_lower in key.lower():
                        # Get object metadata
                        try:
                            head_response = self.s3_client.head_object(
                                Bucket=bucket_name, Key=key
                            )
                            s3_metadata = head_response.get("Metadata", {})

                            # Convert metadata back to dict
                            metadata = {
                                k: v
                                for k, v in s3_metadata.items()
                                if k not in ["file_type", "cached_at"]
                            }

                            matches.append(
                                CachedFile(
                                    file_id=hashlib.md5(
                                        f"{bucket_name}/{key}".encode()
                                    ).hexdigest()[:12],
                                    file_type=ftype,
                                    file_path=f"s3://{bucket_name}/{key}",
                                    metadata=metadata,
                                    cached_at=obj["LastModified"].isoformat(),
                                    size_bytes=obj["Size"],
                                )
                            )
                        except ClientError as e:
                            logger.warning(f"Error getting metadata for {key}: {e}")
                            continue

            except ClientError as e:
                logger.error(f"Error searching bucket {bucket_name}: {e}")

        logger.info(f"MinIO search for '{query}' found {len(matches)} files")
        return matches

    def save_metadata(self, file_path: str, metadata: dict[str, Any]) -> None:
        """Update metadata for cached file in MinIO.

        Args:
            file_path: S3 path (s3://bucket/key)
            metadata: Metadata dict to update
        """
        try:
            # Parse S3 path
            if not file_path.startswith("s3://"):
                logger.error(f"Invalid S3 path: {file_path}")
                return

            path_parts = file_path[5:].split("/", 1)
            if len(path_parts) != 2:
                logger.error(f"Invalid S3 path format: {file_path}")
                return

            bucket_name, key = path_parts

            # Get existing object
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            content = response["Body"].read()

            # Update metadata
            s3_metadata = {k: str(v) for k, v in metadata.items() if v is not None}

            # Re-upload with updated metadata
            self.s3_client.put_object(
                Bucket=bucket_name, Key=key, Body=content, Metadata=s3_metadata
            )

            logger.info(f"✅ Updated metadata for {file_path}")

        except ClientError as e:
            logger.error(f"Error updating metadata for {file_path}: {e}")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics from MinIO.

        Returns:
            Dict with cache stats (total files, size, types)
        """
        total_files = 0
        total_size = 0
        files_by_type = {}

        for file_type, bucket_name in self.BUCKETS.items():
            try:
                response = self.s3_client.list_objects_v2(Bucket=bucket_name)

                if "Contents" not in response:
                    files_by_type[file_type] = 0
                    continue

                file_count = len(response["Contents"])
                bucket_size = sum(obj["Size"] for obj in response["Contents"])

                total_files += file_count
                total_size += bucket_size
                files_by_type[file_type] = file_count

            except ClientError as e:
                logger.error(f"Error getting stats for {bucket_name}: {e}")
                files_by_type[file_type] = 0

        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files_by_type": files_by_type,
            "storage_backend": "MinIO S3",
            "endpoint": self.endpoint_url,
        }

    def get_presigned_url(self, file_path: str, expiration: int = 3600) -> str | None:
        """Generate presigned URL for file access.

        Args:
            file_path: S3 path (e.g., s3://bucket-name/filename)
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL string, or None if generation fails
        """
        try:
            # Parse S3 path
            if not file_path.startswith("s3://"):
                logger.error(f"Invalid S3 path: {file_path}")
                return None

            # Extract bucket and key
            path_parts = file_path.replace("s3://", "").split("/", 1)
            if len(path_parts) != 2:
                logger.error(f"Invalid S3 path format: {file_path}")
                return None

            bucket_name, key = path_parts

            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": key},
                ExpiresIn=expiration,
            )

            # Replace internal endpoint with public URL for external access
            # This allows the presigned URL to work from outside Docker network
            if self.endpoint_url in url:
                url = url.replace(self.endpoint_url, self.public_url)
                logger.debug(f"Converted presigned URL from {self.endpoint_url} to {self.public_url}")

            logger.info(
                f"Generated presigned URL for {file_path} (expires in {expiration}s)"
            )
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {file_path}: {e}")
            return None


logger.info("MinIO S3 file cache loaded")
