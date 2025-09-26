#!/usr/bin/env python3
"""
Simple script to check Elasticsearch for documents
"""

import asyncio
import os
from datetime import datetime

try:
    from elasticsearch import AsyncElasticsearch
except ImportError:
    print("❌ elasticsearch package not installed. Run: pip install elasticsearch")
    exit(1)


async def check_elasticsearch():
    """Check Elasticsearch cluster and document counts"""

    # Configuration
    es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    base_index = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print(f"🔍 Checking Elasticsearch at: {es_url}")
    print(f"📚 Base index name: {base_index}")
    print("=" * 50)

    try:
        # Initialize client
        client = AsyncElasticsearch(
            hosts=[es_url], verify_certs=False, ssl_show_warn=False
        )

        # Test connection
        if not await client.ping():
            print("❌ Cannot connect to Elasticsearch!")
            print("   Make sure Elasticsearch is running:")
            print("   docker compose up elasticsearch -d")
            return

        print("✅ Connected to Elasticsearch")

        # Get cluster info
        info = await client.info()
        print(f"📊 Cluster: {info['cluster_name']}")
        print(f"🏷️  Version: {info['version']['number']}")

        # Get cluster health
        health = await client.cluster.health()
        print(f"💚 Health: {health['status']}")
        print()

        # Check for indices
        indices_to_check = [base_index, f"{base_index}_sparse", f"{base_index}_dense"]

        print("📋 Index Status:")
        print("-" * 30)

        for index_name in indices_to_check:
            try:
                exists = await client.indices.exists(index=index_name)
                if exists:
                    # Get document count
                    count_response = await client.count(index=index_name)
                    doc_count = count_response["count"]

                    # Get index stats
                    stats = await client.indices.stats(index=index_name)
                    size_bytes = stats["indices"][index_name]["total"]["store"][
                        "size_in_bytes"
                    ]
                    size_mb = size_bytes / (1024 * 1024)

                    print(f"✅ {index_name}")
                    print(f"   📄 Documents: {doc_count:,}")
                    print(f"   💾 Size: {size_mb:.2f} MB")

                    # Show sample documents if any exist
                    if doc_count > 0:
                        sample = await client.search(
                            index=index_name,
                            body={"size": 3, "sort": [{"_score": {"order": "desc"}}]},
                        )

                        print("   📝 Sample documents:")
                        for i, hit in enumerate(sample["hits"]["hits"][:3], 1):
                            source = hit["_source"]
                            title = source.get("title", "No title")
                            content_preview = source.get("content", "")[:100]
                            if len(content_preview) == 100:
                                content_preview += "..."
                            print(f"      {i}. {title}")
                            print(f"         {content_preview}")

                else:
                    print(f"❌ {index_name} - Does not exist")

            except Exception as e:
                print(f"⚠️  {index_name} - Error: {e}")

            print()

        # Search functionality test
        print("🔍 Testing Search:")
        print("-" * 20)

        # Try a simple search on the main indices
        for index_name in [base_index, f"{base_index}_sparse"]:
            try:
                exists = await client.indices.exists(index=index_name)
                if exists:
                    search_response = await client.search(
                        index=index_name, body={"query": {"match_all": {}}, "size": 1}
                    )

                    total_hits = search_response["hits"]["total"]["value"]
                    print(f"✅ {index_name}: {total_hits} searchable documents")

            except Exception as e:
                print(f"⚠️  Search test failed for {index_name}: {e}")

        await client.close()

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main function"""
    print("🚀 Elasticsearch Document Checker")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    asyncio.run(check_elasticsearch())

    print()
    print("✨ Check complete!")


if __name__ == "__main__":
    main()
