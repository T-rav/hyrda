#!/usr/bin/env python3
"""
Test script to demonstrate the new source citation functionality
"""

def test_add_source_citations():
    """Test the _add_source_citations method with sample data"""

    # Sample response from LLM
    response = "Based on the project requirements, we need to implement three key features: user authentication, data processing, and reporting capabilities. The budget analysis shows we have sufficient resources allocated for Q4 development."

    # Sample context chunks with Google Drive metadata
    context_chunks = [
        {
            "content": "Project requirements include user auth, data processing, and reporting...",
            "similarity": 0.87,
            "metadata": {
                "file_id": "abc123",
                "file_name": "Project Requirements.docx",
                "web_view_link": "https://drive.google.com/file/d/abc123/view",
                "folder_path": "Projects/Current",
                "source": "google_drive"
            }
        },
        {
            "content": "Budget allocation for Q4 development shows $50k available...",
            "similarity": 0.73,
            "metadata": {
                "file_id": "def456",
                "file_name": "Budget Analysis Q4.xlsx",
                "web_view_link": "https://drive.google.com/file/d/def456/view",
                "folder_path": "Finance/2024",
                "source": "google_drive"
            }
        },
        {
            "content": "Additional requirements from the same document...",
            "similarity": 0.65,
            "metadata": {
                "file_id": "abc123",  # Same document as first chunk
                "file_name": "Project Requirements.docx",
                "web_view_link": "https://drive.google.com/file/d/abc123/view",
                "folder_path": "Projects/Current",
                "source": "google_drive"
            }
        }
    ]

    # Simulate the _add_source_citations method
    def add_source_citations(response: str, context_chunks: list) -> str:
        # Extract unique sources from context chunks
        sources = {}
        for chunk in context_chunks:
            metadata = chunk.get("metadata", {})

            # Use file_id as the key to avoid duplicates
            file_id = metadata.get("file_id")
            if not file_id:
                continue

            file_name = metadata.get("file_name", "Unknown Document")
            web_view_link = metadata.get("web_view_link")
            folder_path = metadata.get("folder_path", "")

            if file_id not in sources:
                sources[file_id] = {
                    "name": file_name,
                    "link": web_view_link,
                    "path": folder_path,
                    "similarity": chunk.get("similarity", 0)
                }
            else:
                # Keep the highest similarity score if we see the same document multiple times
                sources[file_id]["similarity"] = max(
                    sources[file_id]["similarity"],
                    chunk.get("similarity", 0)
                )

        if not sources:
            return response

        # Build citations section
        citations = ["\n\n📚 **Sources:**"]

        # Sort sources by similarity score (highest first)
        sorted_sources = sorted(
            sources.items(),
            key=lambda x: x[1]["similarity"],
            reverse=True
        )

        for i, (file_id, source_info) in enumerate(sorted_sources, 1):
            name = source_info["name"]
            link = source_info["link"]
            path = source_info["path"]
            similarity = source_info["similarity"]

            if link:
                # Create clickable link for Slack
                citation = f"{i}. [{name}]({link})"
                if path:
                    citation += f" (📁 {path})"
                citation += f" - *Relevance: {similarity:.1%}*"
            else:
                # Fallback if no link available
                citation = f"{i}. {name}"
                if path:
                    citation += f" (📁 {path})"
                citation += f" - *Relevance: {similarity:.1%}*"

            citations.append(citation)

        return response + "\n".join(citations)

    # Test the function
    result = add_source_citations(response, context_chunks)

    print("🤖 AI Response with Source Citations:")
    print("=" * 50)
    print(result)
    print("=" * 50)
    print("\n✅ This shows how your Slack bot will now respond!")
    print("📌 Notice how it automatically:")
    print("   • Deduplicates sources (same document appears only once)")
    print("   • Sorts by relevance (highest similarity first)")
    print("   • Creates clickable Google Drive links")
    print("   • Shows folder paths for context")
    print("   • Displays relevance percentages")

if __name__ == "__main__":
    test_add_source_citations()
