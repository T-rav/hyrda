"""
Tests for Elasticsearch Vector Store Diversification Logic

Tests the document diversification algorithm that ensures varied results.
"""

from config.settings import Settings
from services.vector_stores.elasticsearch_store import ElasticsearchVectorStore

# Force CI formatting consistency


class TestElasticsearchDiversification:
    """Test diversification logic in Elasticsearch vector store"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create a mock settings object
        self.settings = Settings()
        self.store = ElasticsearchVectorStore(self.settings.vector)

    def test_diversify_results_basic(self):
        """Test basic diversification with multiple documents"""
        # Mock documents from 3 different files
        documents = [
            {
                "content": "Apple content 1",
                "similarity": 0.95,
                "metadata": {"file_name": "Apple Doc 1"},
            },
            {
                "content": "Apple content 2",
                "similarity": 0.94,
                "metadata": {"file_name": "Apple Doc 1"},
            },  # Same file
            {
                "content": "Apple content 3",
                "similarity": 0.90,
                "metadata": {"file_name": "Apple Doc 2"},
            },
            {
                "content": "Apple content 4",
                "similarity": 0.89,
                "metadata": {"file_name": "Apple Doc 2"},
            },  # Same file
            {
                "content": "Other content",
                "similarity": 0.85,
                "metadata": {"file_name": "Other Doc"},
            },
            {
                "content": "Apple content 5",
                "similarity": 0.80,
                "metadata": {"file_name": "Apple Doc 3"},
            },
        ]

        # Diversify to 4 results - should get 1 from each of the top 3 Apple docs + 1 other
        result = self.store._diversify_results(documents, limit=4)

        assert len(result) == 4

        # Should get the best chunk from each document first (round-robin)
        file_names = [r["metadata"]["file_name"] for r in result]

        # First result should be from Apple Doc 1 (highest similarity)
        assert result[0]["metadata"]["file_name"] == "Apple Doc 1"
        assert result[0]["similarity"] == 0.95

        # Should have results from multiple different documents
        unique_files = set(file_names)
        assert len(unique_files) >= 3, (
            f"Expected 3+ unique files, got {len(unique_files)}: {unique_files}"
        )

        # Should include Apple Doc 1, Apple Doc 2, Apple Doc 3, and Other Doc
        expected_files = {"Apple Doc 1", "Apple Doc 2", "Other Doc", "Apple Doc 3"}
        assert unique_files.issubset(expected_files), (
            f"Unexpected files: {unique_files - expected_files}"
        )

    def test_diversify_results_prioritizes_one_per_document(self):
        """Test that diversification takes 1 chunk per document before duplicating"""
        documents = [
            {
                "content": "Doc A chunk 1",
                "similarity": 0.95,
                "metadata": {"file_name": "Doc A"},
            },
            {
                "content": "Doc A chunk 2",
                "similarity": 0.94,
                "metadata": {"file_name": "Doc A"},
            },
            {
                "content": "Doc B chunk 1",
                "similarity": 0.90,
                "metadata": {"file_name": "Doc B"},
            },
            {
                "content": "Doc C chunk 1",
                "similarity": 0.85,
                "metadata": {"file_name": "Doc C"},
            },
            {
                "content": "Doc D chunk 1",
                "similarity": 0.80,
                "metadata": {"file_name": "Doc D"},
            },
        ]

        # Request 4 results - should get 1 from each of the first 4 documents
        result = self.store._diversify_results(documents, limit=4)

        assert len(result) == 4

        # Should be exactly one result from each of the 4 documents
        file_names = [r["metadata"]["file_name"] for r in result]
        unique_files = set(file_names)

        assert len(unique_files) == 4, (
            f"Expected 4 unique files, got {len(unique_files)}: {unique_files}"
        )
        assert unique_files == {"Doc A", "Doc B", "Doc C", "Doc D"}

        # Order should prioritize by similarity within the round-robin
        assert result[0]["metadata"]["file_name"] == "Doc A"  # Highest similarity
        assert result[1]["metadata"]["file_name"] == "Doc B"  # Second highest
        assert result[2]["metadata"]["file_name"] == "Doc C"  # Third highest
        assert result[3]["metadata"]["file_name"] == "Doc D"  # Fourth highest

    def test_diversify_results_empty_input(self):
        """Test diversification with empty input"""
        result = self.store._diversify_results([], limit=5)
        assert result == []

    def test_diversify_results_single_document(self):
        """Test diversification when all chunks are from the same document"""
        documents = [
            {
                "content": "Same doc chunk 1",
                "similarity": 0.95,
                "metadata": {"file_name": "Same Doc"},
            },
            {
                "content": "Same doc chunk 2",
                "similarity": 0.90,
                "metadata": {"file_name": "Same Doc"},
            },
            {
                "content": "Same doc chunk 3",
                "similarity": 0.85,
                "metadata": {"file_name": "Same Doc"},
            },
        ]

        result = self.store._diversify_results(documents, limit=2)

        assert len(result) == 2
        # Both should be from the same document (only option)
        assert all(r["metadata"]["file_name"] == "Same Doc" for r in result)
        # Should get the top 2 by similarity
        assert result[0]["similarity"] == 0.95
        assert result[1]["similarity"] == 0.90

    def test_diversify_results_limit_greater_than_available(self):
        """Test when limit is greater than available documents"""
        documents = [
            {
                "content": "Doc 1",
                "similarity": 0.95,
                "metadata": {"file_name": "Doc 1"},
            },
            {
                "content": "Doc 2",
                "similarity": 0.90,
                "metadata": {"file_name": "Doc 2"},
            },
        ]

        result = self.store._diversify_results(documents, limit=5)

        # Should return all available documents
        assert len(result) == 2
        assert result[0]["metadata"]["file_name"] == "Doc 1"
        assert result[1]["metadata"]["file_name"] == "Doc 2"

    def test_diversify_results_apple_scenario(self):
        """Test the specific Apple search scenario that was fixed"""
        # Simulate the Apple search scenario
        documents = [
            # Apple Doc 1 - many chunks, very high similarity
            {
                "content": "Apple project details 1",
                "similarity": 0.95,
                "metadata": {"file_name": "Apple - Project Details File"},
            },
            {
                "content": "Apple project details 2",
                "similarity": 0.944,
                "metadata": {"file_name": "Apple - Project Details File"},
            },
            {
                "content": "Apple project details 3",
                "similarity": 0.94,
                "metadata": {"file_name": "Apple - Project Details File"},
            },
            # Apple Doc 2 - many chunks, high similarity
            {
                "content": "Apple experimentation 1",
                "similarity": 0.863,
                "metadata": {
                    "file_name": "Apple - Accelerating Experimentation with Automation and Self-Service Tools - Kristin Kaeding"
                },
            },
            {
                "content": "Apple experimentation 2",
                "similarity": 0.853,
                "metadata": {
                    "file_name": "Apple - Accelerating Experimentation with Automation and Self-Service Tools - Kristin Kaeding"
                },
            },
            # Other relevant doc
            {
                "content": "Hindman content",
                "similarity": 0.78,
                "metadata": {
                    "file_name": "Hindman – Unlocking a Legacy Auction House's Potential with a Digital Transformation"
                },
            },
            # Apple Doc 3 - fewer chunks, medium-high similarity
            {
                "content": "Apple frontend 1",
                "similarity": 0.757,
                "metadata": {
                    "file_name": "Apple - Frontend Engineering: Strategic Interface Design in Services-First Ecosystems"
                },
            },
            {
                "content": "Apple frontend 2",
                "similarity": 0.728,
                "metadata": {
                    "file_name": "Apple - Frontend Engineering: Strategic Interface Design in Services-First Ecosystems"
                },
            },
            # Apple Doc 4 - single chunk, medium-high similarity
            {
                "content": "Apple scaling",
                "similarity": 0.751,
                "metadata": {
                    "file_name": "Apple - Scaling Experimentation in a Fortune 100 Company: Lessons in Automation and Developer Efficiency"
                },
            },
        ]

        # With diversification fix, should get chunks from 4 different Apple docs + Hindman
        result = self.store._diversify_results(documents, limit=5)

        assert len(result) == 5

        # Count unique Apple documents
        file_names = [r["metadata"]["file_name"] for r in result]
        apple_files = [f for f in file_names if "apple" in f.lower()]
        unique_apple_files = set(apple_files)

        # Should have 4 different Apple documents represented
        assert len(unique_apple_files) == 4, (
            f"Expected 4 Apple documents, got {len(unique_apple_files)}: {unique_apple_files}"
        )

        # Should include the specific Apple documents we expect
        expected_apple_docs = {
            "Apple - Project Details File",
            "Apple - Accelerating Experimentation with Automation and Self-Service Tools - Kristin Kaeding",
            "Apple - Frontend Engineering: Strategic Interface Design in Services-First Ecosystems",
            "Apple - Scaling Experimentation in a Fortune 100 Company: Lessons in Automation and Developer Efficiency",
        }
        assert unique_apple_files == expected_apple_docs

        # Should also include the Hindman document for variety
        assert (
            "Hindman – Unlocking a Legacy Auction House's Potential with a Digital Transformation"
            in file_names
        )

    def test_diversify_results_preserves_similarity_within_documents(self):
        """Test that within each document, chunks are ordered by similarity"""
        documents = [
            {
                "content": "Doc A low",
                "similarity": 0.80,
                "metadata": {"file_name": "Doc A"},
            },  # Lower similarity first
            {
                "content": "Doc A high",
                "similarity": 0.95,
                "metadata": {"file_name": "Doc A"},
            },  # Higher similarity second
            {
                "content": "Doc B chunk",
                "similarity": 0.90,
                "metadata": {"file_name": "Doc B"},
            },
        ]

        # Should take the HIGHEST similarity chunk from each document first
        result = self.store._diversify_results(documents, limit=2)

        assert len(result) == 2
        # First should be Doc A with highest similarity (0.95)
        doc_a_result = next(r for r in result if r["metadata"]["file_name"] == "Doc A")
        assert doc_a_result["similarity"] == 0.95
        assert doc_a_result["content"] == "Doc A high"
