#!/usr/bin/env python3
"""
Test the RRF scoring fix that scales low scores (1.6%) to meaningful ranges
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))


def test_rrf_scaling():
    print("🔍 Testing RRF Score Scaling Fix")
    print("=" * 50)

    # Simulate typical RRF scores
    rrf_scores = {
        "doc1": 1.0 / (60 + 1),  # ≈ 0.0164 (1.64%)
        "doc2": 1.0 / (60 + 2),  # ≈ 0.0161 (1.61%)
        "doc3": 1.0 / (60 + 3),  # ≈ 0.0159 (1.59%)
        "doc4": 1.0 / (60 + 10),  # ≈ 0.0143 (1.43%)
    }

    print("🔸 Before Fix (Raw RRF Scores):")
    for doc, score in rrf_scores.items():
        print(f"   {doc}: {score:.4f} ({score:.1%})")
    print()

    # Apply the new scaling logic
    max_rrf_score = max(rrf_scores.values())
    scaled_scores = {}

    for doc, score in rrf_scores.items():
        # Scale RRF scores to meaningful similarity range (0.3-0.95)
        normalized_score = score / max_rrf_score
        scaled_score = normalized_score**0.8  # Gentle power curve
        final_similarity = 0.3 + (scaled_score * 0.65)  # Scale to 0.3-0.95 range
        scaled_scores[doc] = final_similarity

    print("✅ After Fix (Scaled Similarity Scores):")
    for doc, score in scaled_scores.items():
        print(f"   {doc}: {score:.4f} ({score:.1%})")
    print()

    print("📈 Improvements:")
    print(
        f"   - Score range: {min(scaled_scores.values()):.1%} - {max(scaled_scores.values()):.1%}"
    )
    print(
        f"   - Now passes 50% threshold: {sum(1 for s in scaled_scores.values() if s >= 0.5)} docs"
    )
    print(
        f"   - Would have passed 70% threshold: {sum(1 for s in rrf_scores.values() if s >= 0.7)} docs (before)"
    )
    print(
        f"   - Now passes 70% threshold: {sum(1 for s in scaled_scores.values() if s >= 0.7)} docs (after)"
    )
    print()
    print("🎯 This fix resolves the 1.6% scoring issue by:")
    print("   1. Normalizing RRF scores against the maximum score")
    print("   2. Applying a gentle power curve for better distribution")
    print("   3. Scaling to a meaningful 0.3-0.95 similarity range")
    print("   4. Making scores comparable to Elasticsearch's improved scaling")


if __name__ == "__main__":
    test_rrf_scaling()
