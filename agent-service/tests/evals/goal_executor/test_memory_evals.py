"""Evals for memory retrieval quality.

Tests that the memory system retrieves relevant past context.

Run with: pytest tests/evals/goal_executor/test_memory_evals.py -v
"""


class TestMemoryRetrievalQuality:
    """Evaluate memory retrieval relevance."""

    def test_bm25_finds_exact_terms(self):
        """Eval: BM25 should find documents with exact query terms."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")

        query_tokens = memory._tokenize("AI infrastructure funding")

        # Document with exact terms
        doc_with_terms = "AI infrastructure company received funding round"
        score = memory._bm25_score(query_tokens, doc_with_terms)

        assert score > 0.5, "Document with exact terms should score high"

    def test_bm25_scores_relevance_correctly(self):
        """Eval: More relevant documents should score higher."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")

        query_tokens = memory._tokenize("DevOps platform Kubernetes")

        # Highly relevant
        doc_relevant = "DevOps platform for Kubernetes container orchestration"
        # Partially relevant
        doc_partial = "DevOps tools for cloud deployment"
        # Not relevant
        doc_irrelevant = "Healthcare patient management system"

        score_relevant = memory._bm25_score(query_tokens, doc_relevant)
        score_partial = memory._bm25_score(query_tokens, doc_partial)
        score_irrelevant = memory._bm25_score(query_tokens, doc_irrelevant)

        assert score_relevant > score_partial, "Highly relevant should score higher"
        assert score_partial > score_irrelevant, "Partial should beat irrelevant"

    def test_temporal_decay_prioritizes_recent(self):
        """Eval: Recent memories should score higher than old ones."""
        from datetime import datetime, timedelta

        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")
        base_score = 0.8

        # Recent (today)
        recent = datetime.now().isoformat()
        score_recent = memory._apply_decay(base_score, recent)

        # Week old
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        score_week = memory._apply_decay(base_score, week_ago)

        # Month old
        month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        score_month = memory._apply_decay(base_score, month_ago)

        assert score_recent > score_week > score_month, "Recency should affect score"
        assert score_month > 0, "Old memories should still have some score"

    def test_mmr_increases_diversity(self):
        """Eval: MMR should select diverse results."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")

        # Create candidates with clusters of similar items
        candidates = [
            # Cluster 1: AI companies
            {"score": 0.95, "summary": "AI infrastructure company with ML platform"},
            {"score": 0.90, "summary": "AI infrastructure startup building ML tools"},
            {"score": 0.88, "summary": "AI infrastructure provider for deep learning"},
            # Cluster 2: DevOps companies
            {"score": 0.85, "summary": "DevOps platform for Kubernetes"},
            {"score": 0.82, "summary": "DevOps tools for container orchestration"},
            # Cluster 3: Different
            {"score": 0.80, "summary": "Fintech payment processing platform"},
            {"score": 0.75, "summary": "Healthcare data analytics"},
        ]

        # Without MMR: top 3 would all be AI (0.95, 0.90, 0.88)
        # With MMR: should include diversity

        reranked = memory._mmr_rerank(candidates, limit=4)

        assert len(reranked) == 4

        # Count unique "clusters" in results
        summaries = [r["summary"] for r in reranked]
        has_ai = any("AI" in s for s in summaries)
        has_devops = any("DevOps" in s or "Kubernetes" in s for s in summaries)
        has_other = any("Fintech" in s or "Healthcare" in s for s in summaries)

        # MMR should include at least 2 different clusters
        clusters_present = sum([has_ai, has_devops, has_other])
        assert clusters_present >= 2, "MMR should select from multiple clusters"


class TestMemorySessionScoping:
    """Evaluate session vs goal-wide memory scoping."""

    def test_session_activities_are_isolated(self):
        """Eval: Different threads should have isolated activities."""
        from agents.goal_executor.services.memory import GoalMemory

        # Thread 1
        mem1 = GoalMemory(bot_id="test", thread_id="thread_1")
        mem1.log_activity("search", {"query": "AI companies"}, persist=False)

        # Thread 2
        mem2 = GoalMemory(bot_id="test", thread_id="thread_2")
        mem2.log_activity("search", {"query": "DevOps companies"}, persist=False)

        # Activities should be isolated
        assert len(mem1.get_session_activity()) == 1
        assert len(mem2.get_session_activity()) == 1
        assert mem1.get_session_activity()[0]["data"]["query"] == "AI companies"
        assert mem2.get_session_activity()[0]["data"]["query"] == "DevOps companies"

    def test_goal_wide_sets_are_shared(self):
        """Eval: Goal-wide sets should be shared across threads."""
        from agents.goal_executor.services.memory import GoalMemory

        # Shared storage for this test
        stored: dict = {}

        def mock_remember(key, value):
            stored[key] = value
            return True

        def mock_recall(key):
            return stored.get(key)

        # Thread 1 adds company
        mem1 = GoalMemory(bot_id="test", thread_id="thread_1")
        mem1.remember = mock_remember
        mem1.recall = mock_recall
        mem1.add_to_set("companies_researched", "Acme Corp")

        # Thread 2 should see it (same bot_id)
        mem2 = GoalMemory(bot_id="test", thread_id="thread_2")
        mem2.remember = mock_remember
        mem2.recall = mock_recall

        assert mem2.is_in_set("companies_researched", "Acme Corp")


class TestCompactionQuality:
    """Evaluate session compaction quality."""

    def test_simple_summary_captures_key_info(self):
        """Eval: Simple summary should capture key entities."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")

        activities = [
            {"type": "search", "data": {"query": "AI startups funding"}},
            {"type": "company_research", "data": {"company": "Acme AI"}},
            {"type": "company_research", "data": {"company": "TechBot"}},
            {"type": "qualify", "data": {"company": "Acme AI", "score": 85}},
        ]

        summary = memory._simple_summary(
            activities,
            outcome="Found 2 qualified AI prospects",
            goal="Find AI companies with recent funding",
        )

        # Summary should contain key info
        assert "Acme AI" in summary or "Acme" in summary
        assert "TechBot" in summary or "2 qualified" in summary.lower()

    def test_summary_is_searchable(self):
        """Eval: Summary should be searchable with relevant queries."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test")

        summary = memory._simple_summary(
            activities=[
                {"type": "search", "data": {"query": "DevOps Kubernetes"}},
                {"type": "company_research", "data": {"company": "K8s Inc"}},
            ],
            outcome="Found K8s Inc as strong DevOps prospect",
            goal="Find Kubernetes platform companies",
        )

        # BM25 should match relevant queries
        query_tokens = memory._tokenize("DevOps Kubernetes companies")
        score = memory._bm25_score(query_tokens, summary)

        assert score > 0.3, "Summary should be searchable with relevant terms"
