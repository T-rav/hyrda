"""Comprehensive tests for Qdrant client service."""

import hashlib
import logging
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add tasks to path
tasks_dir = Path(__file__).parent.parent
if str(tasks_dir) not in sys.path:
    sys.path.insert(0, str(tasks_dir))

from services.qdrant_client import QdrantClient  # noqa: E402


class TestQdrantClientInitialization:
    """Test Qdrant client initialization."""

    def test_init_with_default_env_vars(self):
        """Test initialization uses default environment variables."""
        with patch.dict(
            os.environ,
            {
                "QDRANT_HOST": "test-host",
                "QDRANT_PORT": "9999",
                "QDRANT_API_KEY": "test-api-key",
                "VECTOR_COLLECTION_NAME": "test-collection",
            },
        ):
            client = QdrantClient()
            assert client.host == "test-host"
            assert client.port == 9999
            assert client.api_key == "test-api-key"
            assert client.collection_name == "test-collection"
            assert client.client is None

    def test_init_with_defaults_when_env_vars_missing(self):
        """Test initialization falls back to defaults when env vars missing."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove specific env vars
            env_copy = os.environ.copy()
            for key in [
                "QDRANT_HOST",
                "QDRANT_PORT",
                "QDRANT_API_KEY",
                "VECTOR_COLLECTION_NAME",
            ]:
                env_copy.pop(key, None)

            with patch.dict(os.environ, env_copy, clear=True):
                client = QdrantClient()
                assert client.host == "qdrant"
                assert client.port == 6333
                assert client.api_key is None
                assert client.collection_name == "insightmesh-knowledge-base"

    def test_init_client_starts_as_none(self):
        """Test that client starts as None before initialize() is called."""
        client = QdrantClient()
        assert client.client is None


class TestQdrantClientInitializeMethod:
    """Test initialize() method."""

    @pytest.mark.asyncio
    async def test_initialize_with_api_key_success(self, caplog):
        """Test successful initialization with API key."""
        caplog.set_level(logging.INFO, logger="services.qdrant_client")

        # Create mock SDK and models
        mock_qdrant_sdk = Mock()
        mock_client_instance = Mock()
        mock_qdrant_sdk.return_value = mock_client_instance

        mock_distance = Mock()
        mock_vector_params = Mock()

        # Mock collections response
        mock_collections_response = Mock()
        mock_collections_response.collections = [Mock(name="existing-collection")]

        with (
            patch("services.qdrant_client.QdrantClient.__init__", return_value=None),
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
        ):
            # Setup client
            client = QdrantClient()
            client.host = "test-host"
            client.port = 6333
            client.api_key = "test-key"
            client.collection_name = "existing-collection"
            client.client = None

            # Mock async executor to return collections
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=mock_collections_response
            )

            # Patch the imports
            with (
                patch.dict(
                    "sys.modules",
                    {"qdrant_client": Mock(), "qdrant_client.models": Mock()},
                ),
            ):
                sys.modules["qdrant_client"].QdrantClient = mock_qdrant_sdk
                sys.modules["qdrant_client.models"].Distance = mock_distance
                sys.modules["qdrant_client.models"].VectorParams = mock_vector_params

                await client.initialize()

                # Verify client was created with URL format
                assert mock_qdrant_sdk.called
                # Check for either initialization or creation message
                assert (
                    "Qdrant initialized" in caplog.text
                    or "Created Qdrant" in caplog.text
                )

    @pytest.mark.asyncio
    async def test_initialize_without_api_key_success(self):
        """Test successful initialization without API key."""
        mock_qdrant_sdk = Mock()
        mock_client_instance = Mock()
        mock_qdrant_sdk.return_value = mock_client_instance

        mock_distance = Mock()
        mock_vector_params = Mock()

        mock_collections_response = Mock()
        mock_collections_response.collections = [Mock(name="test-collection")]

        with (
            patch("services.qdrant_client.QdrantClient.__init__", return_value=None),
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
        ):
            client = QdrantClient()
            client.host = "localhost"
            client.port = 6333
            client.api_key = None
            client.collection_name = "test-collection"
            client.client = None

            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=mock_collections_response
            )

            with patch.dict(
                "sys.modules", {"qdrant_client": Mock(), "qdrant_client.models": Mock()}
            ):
                sys.modules["qdrant_client"].QdrantClient = mock_qdrant_sdk
                sys.modules["qdrant_client.models"].Distance = mock_distance
                sys.modules["qdrant_client.models"].VectorParams = mock_vector_params

                await client.initialize()

                assert mock_qdrant_sdk.called

    @pytest.mark.asyncio
    async def test_initialize_raises_import_error_when_qdrant_not_installed(self):
        """Test initialize raises ImportError if qdrant-client not installed."""
        with (
            patch("services.qdrant_client.QdrantClient.__init__", return_value=None),
            patch.dict("sys.modules", {"qdrant_client": None}),
        ):
            client = QdrantClient()
            client.host = "localhost"
            client.port = 6333
            client.api_key = None
            client.collection_name = "test"
            client.client = None

            with pytest.raises(
                ImportError, match="qdrant-client package not installed"
            ):
                await client.initialize()


class TestUpsertWithNamespace:
    """Test upsert_with_namespace() method."""

    @pytest.mark.asyncio
    async def test_upsert_raises_error_if_not_initialized(self):
        """Test upsert raises RuntimeError if client not initialized."""
        client = QdrantClient()
        client.client = None

        with pytest.raises(RuntimeError, match="Qdrant not initialized"):
            await client.upsert_with_namespace(
                texts=["test"],
                embeddings=[[0.1] * 3072],
                metadata=[{}],
            )

    @pytest.mark.asyncio
    async def test_upsert_with_single_document(self, caplog):
        """Test upserting a single document."""
        caplog.set_level(logging.INFO, logger="services.qdrant_client")

        client = QdrantClient()
        mock_client_instance = Mock()
        mock_client_instance.upsert = Mock(return_value=None)
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        # Mock PointStruct
        mock_point_struct = Mock()

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = mock_point_struct

            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await client.upsert_with_namespace(
                texts=["Document text"],
                embeddings=[[0.1] * 3072],
                metadata=[{"doc_id": "123"}],
                namespace="test",
            )

            # Verify PointStruct was called
            assert mock_point_struct.called
            assert "Added 1 documents to Qdrant namespace 'test'" in caplog.text

    @pytest.mark.asyncio
    async def test_upsert_generates_deterministic_uuid(self):
        """Test that upsert generates deterministic UUIDs."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        generated_ids = []

        def mock_point_constructor(id, vector, payload):
            generated_ids.append(id)
            return Mock(id=id, vector=vector, payload=payload)

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = mock_point_constructor
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            # First upsert
            await client.upsert_with_namespace(
                texts=["Doc 1"],
                embeddings=[[0.1] * 3072],
                metadata=[{"employee_id": "emp123"}],
                namespace="employees",
            )

            first_id = generated_ids[0]

            # Second upsert with same data
            await client.upsert_with_namespace(
                texts=["Doc 1"],
                embeddings=[[0.1] * 3072],
                metadata=[{"employee_id": "emp123"}],
                namespace="employees",
            )

            second_id = generated_ids[1]

            # IDs should be identical (deterministic)
            assert first_id == second_id

            # Verify it's a valid UUID
            try:
                uuid.UUID(first_id)
            except ValueError:
                pytest.fail(f"Generated ID is not valid UUID: {first_id}")

    @pytest.mark.asyncio
    async def test_upsert_uses_different_metadata_id_fields(self):
        """Test that upsert extracts IDs from various metadata fields."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        generated_ids = []

        def mock_point_constructor(id, vector, payload):
            generated_ids.append(id)
            return Mock(id=id, vector=vector, payload=payload)

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = mock_point_constructor
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            # Test different ID fields generate different UUIDs
            test_cases = [
                {"employee_id": "emp1"},
                {"project_id": "proj1"},
                {"client_id": "client1"},
                {"allocation_id": "alloc1"},
                {"chunk_id": "chunk1"},
            ]

            for metadata in test_cases:
                await client.upsert_with_namespace(
                    texts=["Doc"],
                    embeddings=[[0.1] * 3072],
                    metadata=[metadata],
                    namespace="test",
                )

            # All IDs should be different
            assert len(set(generated_ids)) == len(generated_ids)

    @pytest.mark.asyncio
    async def test_upsert_adds_text_and_namespace_to_payload(self):
        """Test that upsert adds text and namespace to metadata payload."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        captured_payload = {}

        def mock_point_constructor(id, vector, payload):
            captured_payload.update(payload)
            return Mock(id=id, vector=vector, payload=payload)

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = mock_point_constructor
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await client.upsert_with_namespace(
                texts=["Test document"],
                embeddings=[[0.1] * 3072],
                metadata=[{"custom_field": "value"}],
                namespace="docs",
            )

            assert captured_payload["text"] == "Test document"
            assert captured_payload["namespace"] == "docs"
            assert captured_payload["custom_field"] == "value"

    @pytest.mark.asyncio
    async def test_upsert_handles_multiple_documents(self, caplog):
        """Test upserting multiple documents."""
        caplog.set_level(logging.INFO, logger="services.qdrant_client")

        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = Mock(return_value=Mock())
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await client.upsert_with_namespace(
                texts=["Doc 1", "Doc 2", "Doc 3"],
                embeddings=[[0.1] * 3072, [0.2] * 3072, [0.3] * 3072],
                metadata=[{"doc_id": "1"}, {"doc_id": "2"}, {"doc_id": "3"}],
                namespace="test",
            )

            assert "Added 3 documents to Qdrant namespace 'test'" in caplog.text

    @pytest.mark.asyncio
    async def test_upsert_batches_large_datasets(self):
        """Test that upsert processes large datasets in batches of 100."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = Mock(return_value=Mock())

            call_count = [0]

            async def count_calls(executor, fn):
                call_count[0] += 1

            mock_loop.return_value.run_in_executor = count_calls

            # Test with 250 documents (should be 3 batches: 100, 100, 50)
            num_docs = 250
            await client.upsert_with_namespace(
                texts=[f"Doc {i}" for i in range(num_docs)],
                embeddings=[[0.1] * 3072 for _ in range(num_docs)],
                metadata=[{"doc_id": str(i)} for i in range(num_docs)],
                namespace="test",
            )

            assert call_count[0] == 3  # 250 docs = 3 batches

    @pytest.mark.asyncio
    async def test_upsert_default_namespace(self, caplog):
        """Test upsert uses default namespace 'metric' if not specified."""
        caplog.set_level(logging.INFO, logger="services.qdrant_client")

        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = Mock(return_value=Mock())
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await client.upsert_with_namespace(
                texts=["Doc"],
                embeddings=[[0.1] * 3072],
                metadata=[{"id": "123"}],
            )

            assert "Added 1 documents to Qdrant namespace 'metric'" in caplog.text


class TestClose:
    """Test close() method."""

    @pytest.mark.asyncio
    async def test_close_calls_client_close(self, caplog):
        """Test close method calls client.close()."""
        caplog.set_level(logging.DEBUG, logger="services.qdrant_client")

        client = QdrantClient()
        mock_client_instance = Mock()
        mock_client_instance.close = Mock()
        client.client = mock_client_instance

        with patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop:

            async def mock_executor(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = mock_executor

            await client.close()

            # Verify close was called
            mock_client_instance.close.assert_called_once()
            assert "Qdrant connection closed" in caplog.text

    @pytest.mark.asyncio
    async def test_close_handles_none_client(self, caplog):
        """Test close method handles None client gracefully."""
        caplog.set_level(logging.DEBUG, logger="services.qdrant_client")

        client = QdrantClient()
        client.client = None

        await client.close()

        # Should log but not crash
        assert "Qdrant connection closed" in caplog.text

    @pytest.mark.asyncio
    async def test_close_handles_client_close_error(self):
        """Test close handles errors from client.close()."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance

        with patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop:

            async def mock_executor_error(executor, fn):
                raise Exception("Connection already closed")

            mock_loop.return_value.run_in_executor = mock_executor_error

            # Should raise the exception
            with pytest.raises(Exception, match="Connection already closed"):
                await client.close()


class TestQdrantClientUUIDGeneration:
    """Test UUID generation logic."""

    def test_uuid_generation_is_deterministic(self):
        """Test that UUID generation is deterministic for same inputs."""
        namespace = "employees"
        record_id = "emp123"

        # Generate UUID using same logic as the code
        id_string = f"{namespace}_{record_id}"
        id_hash = hashlib.md5(id_string.encode(), usedforsecurity=False).hexdigest()
        uuid1 = str(uuid.UUID(id_hash))

        # Generate again
        id_string2 = f"{namespace}_{record_id}"
        id_hash2 = hashlib.md5(id_string2.encode(), usedforsecurity=False).hexdigest()
        uuid2 = str(uuid.UUID(id_hash2))

        assert uuid1 == uuid2

    def test_uuid_generation_differs_for_different_namespaces(self):
        """Test that different namespaces produce different UUIDs."""
        record_id = "123"

        id_string1 = f"namespace1_{record_id}"
        id_hash1 = hashlib.md5(id_string1.encode(), usedforsecurity=False).hexdigest()
        uuid1 = str(uuid.UUID(id_hash1))

        id_string2 = f"namespace2_{record_id}"
        id_hash2 = hashlib.md5(id_string2.encode(), usedforsecurity=False).hexdigest()
        uuid2 = str(uuid.UUID(id_hash2))

        assert uuid1 != uuid2

    def test_uuid_generation_differs_for_different_record_ids(self):
        """Test that different record IDs produce different UUIDs."""
        namespace = "test"

        id_string1 = f"{namespace}_record1"
        id_hash1 = hashlib.md5(id_string1.encode(), usedforsecurity=False).hexdigest()
        uuid1 = str(uuid.UUID(id_hash1))

        id_string2 = f"{namespace}_record2"
        id_hash2 = hashlib.md5(id_string2.encode(), usedforsecurity=False).hexdigest()
        uuid2 = str(uuid.UUID(id_hash2))

        assert uuid1 != uuid2


class TestQdrantClientEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_upsert_with_mismatched_lengths(self):
        """Test upsert handles mismatched text/embedding lengths gracefully."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = Mock(return_value=Mock())
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            # More texts than embeddings (zip with strict=False handles this)
            await client.upsert_with_namespace(
                texts=["Doc 1", "Doc 2", "Doc 3"],
                embeddings=[[0.1] * 3072, [0.2] * 3072],  # Only 2 embeddings
                metadata=[{"id": "1"}, {"id": "2"}],
                namespace="test",
            )

    @pytest.mark.asyncio
    async def test_upsert_with_no_identifiable_metadata_uses_fallback(self):
        """Test upsert generates fallback ID when no standard ID fields exist."""
        client = QdrantClient()
        mock_client_instance = Mock()
        client.client = mock_client_instance
        client.collection_name = "test-collection"

        generated_ids = []

        def mock_point_constructor(id, vector, payload):
            generated_ids.append(id)
            return Mock(id=id, vector=vector, payload=payload)

        with (
            patch("services.qdrant_client.asyncio.get_event_loop") as mock_loop,
            patch.dict("sys.modules", {"qdrant_client.models": Mock()}),
        ):
            sys.modules["qdrant_client.models"].PointStruct = mock_point_constructor
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            # Metadata with no standard ID fields
            await client.upsert_with_namespace(
                texts=["Doc"],
                embeddings=[[0.1] * 3072],
                metadata=[{"random_field": "value"}],
                namespace="test",
            )

            # Should generate a fallback ID
            assert len(generated_ids) == 1
            # The ID should be based on "test_unknown_0"
            expected_id_string = "test_unknown_0"
            expected_hash = hashlib.md5(
                expected_id_string.encode(), usedforsecurity=False
            ).hexdigest()
            expected_uuid = str(uuid.UUID(expected_hash))
            assert generated_ids[0] == expected_uuid
