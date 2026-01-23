"""Factory for creating database mock objects.

Phase 1 improvement: Eliminate duplication of database mock setup
across 20+ test occurrences.
"""

from unittest.mock import MagicMock


class DatabaseMockFactory:
    """Factory for creating consistent database mocks.

    Replaces repeated mock database session setup with pre-configured factories.

    Examples:
        # Session with results
        mock_runs = [Mock(id=1, status="completed"), Mock(id=2, status="failed")]
        session = DatabaseMockFactory.create_session_with_results(mock_runs)

        # Empty session
        session = DatabaseMockFactory.create_empty_session()

        # Session context manager
        mock_context = DatabaseMockFactory.create_session_context(mock_runs)
        mock_db_session.return_value = mock_context
    """

    @staticmethod
    def create_session_with_results(results: list) -> MagicMock:
        """Create mock session that returns specific query results.

        Supports common SQLAlchemy query patterns:
        - session.query().filter().order_by().limit().all()
        - session.query().filter().first()
        - session.query().count()
        - session.add() / session.commit() / session.delete()

        Args:
            results: List of mock objects to return from queries

        Returns:
            MagicMock session with query chaining support

        Example:
            mock_jobs = [Mock(id=1, name="Job 1"), Mock(id=2, name="Job 2")]
            session = DatabaseMockFactory.create_session_with_results(mock_jobs)

            # Will return mock_jobs
            jobs = session.query(Job).all()
        """
        mock_session = MagicMock()
        mock_query = MagicMock()

        # Support chaining: query().filter().order_by().limit().all()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = results
        mock_query.first.return_value = results[0] if results else None
        mock_query.count.return_value = len(results)

        # Session methods
        mock_session.query.return_value = mock_query
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.delete = MagicMock()
        mock_session.rollback = MagicMock()
        mock_session.close = MagicMock()

        return mock_session

    @staticmethod
    def create_empty_session() -> MagicMock:
        """Create mock session with no results.

        Returns:
            MagicMock session that returns empty lists

        Example:
            session = DatabaseMockFactory.create_empty_session()
            assert session.query(Job).all() == []
        """
        return DatabaseMockFactory.create_session_with_results([])

    @staticmethod
    def create_session_context(results: list | None = None) -> MagicMock:
        """Create mock context manager for `with get_db_session() as session:`.

        Args:
            results: Optional list of results to return from queries

        Returns:
            MagicMock context manager that yields a session

        Example:
            from unittest.mock import patch

            mock_runs = [Mock(id=1), Mock(id=2)]
            mock_context = DatabaseMockFactory.create_session_context(mock_runs)

            with patch("models.get_db_session", return_value=mock_context):
                # Your test code that uses get_db_session()
                ...
        """
        results = results or []
        mock_session = DatabaseMockFactory.create_session_with_results(results)

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        return mock_context

    @staticmethod
    def create_session_with_custom_query(query_mock: MagicMock) -> MagicMock:
        """Create session with a custom query mock for complex scenarios.

        Use this when you need to customize query behavior beyond simple results.

        Args:
            query_mock: Pre-configured MagicMock for session.query()

        Returns:
            MagicMock session

        Example:
            # Custom query that raises an exception on count()
            mock_query = MagicMock()
            mock_query.count.side_effect = DatabaseError("Connection failed")

            session = DatabaseMockFactory.create_session_with_custom_query(mock_query)
        """
        mock_session = MagicMock()
        mock_session.query.return_value = query_mock
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.delete = MagicMock()
        mock_session.rollback = MagicMock()
        mock_session.close = MagicMock()

        return mock_session
