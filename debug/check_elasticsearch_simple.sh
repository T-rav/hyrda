#!/bin/bash
# Simple curl-based Elasticsearch document checker

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
INDEX_NAME="${VECTOR_COLLECTION_NAME:-insightmesh-knowledge-base}"

echo "🔍 Checking Elasticsearch at: $ES_URL"
echo "📚 Base index name: $INDEX_NAME"
echo "=================================================="

# Test connection
echo "🔗 Testing connection..."
if curl -s "$ES_URL" > /dev/null; then
    echo "✅ Connected to Elasticsearch"
else
    echo "❌ Cannot connect to Elasticsearch!"
    echo "   Make sure it's running: docker compose up elasticsearch -d"
    exit 1
fi

# Get cluster info
echo ""
echo "📊 Cluster Info:"
curl -s "$ES_URL" | jq -r '"Cluster: " + .cluster_name + " | Version: " + .version.number'

# Get cluster health
echo ""
echo "💚 Cluster Health:"
curl -s "$ES_URL/_cluster/health" | jq -r '"Status: " + .status + " | Nodes: " + (.number_of_nodes|tostring)'

echo ""
echo "📋 Index Status:"
echo "------------------------------"

# Check different index variations
for suffix in "" "_sparse"; do
    index="${INDEX_NAME}${suffix}"
    echo ""
    echo "🔍 Checking: $index"

    # Check if index exists
    if curl -s -f "$ES_URL/$index" > /dev/null 2>&1; then
        echo "✅ Index exists"

        # Get document count
        count=$(curl -s "$ES_URL/$index/_count" | jq -r '.count')
        echo "📄 Documents: $count"

        # Get index size
        size=$(curl -s "$ES_URL/$index/_stats" | jq -r '.indices."'$index'".total.store.size_in_bytes')
        size_mb=$(echo "scale=2; $size / 1024 / 1024" | bc -l 2>/dev/null || echo "N/A")
        echo "💾 Size: ${size_mb} MB"

        # Show sample document if any exist
        if [ "$count" -gt 0 ]; then
            echo "📝 Sample document:"
            curl -s "$ES_URL/$index/_search?size=1" | jq -r '.hits.hits[0]._source | "   Title: " + (.title // "No title") + "\n   Content: " + (.content // "No content")[0:100] + "..."'
        fi
    else
        echo "❌ Index does not exist"
    fi
done

echo ""
echo "🔍 Quick Search Test:"
echo "--------------------"
# Test search on main index
if curl -s -f "$ES_URL/$INDEX_NAME" > /dev/null 2>&1; then
    total=$(curl -s "$ES_URL/$INDEX_NAME/_search?size=0" | jq -r '.hits.total.value')
    echo "✅ $INDEX_NAME: $total searchable documents"
else
    echo "❌ Cannot search $INDEX_NAME (index doesn't exist)"
fi

echo ""
echo "✨ Check complete!"
