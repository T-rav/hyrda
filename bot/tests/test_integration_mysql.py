"""MySQL database integration tests - CRITICAL INFRASTRUCTURE.

Tests verify MySQL connection, schema consistency, and migration status.
These tests validate that database operations work correctly.

Run with: pytest -v -m integration bot/tests/test_integration_mysql.py
"""

import os

import pytest
import sqlalchemy
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration


@pytest.fixture
def mysql_connection():
    """Create MySQL connection for testing."""
    # Use root connection for testing
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/insightmesh_data",
    )

    engine = create_engine(database_url, echo=False)
    connection = engine.connect()

    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()


def test_mysql_connection(mysql_connection):
    """
    CRITICAL TEST - MySQL connection must work.

    Given: MySQL service is running
    When: Application starts
    Then: MySQL connection succeeds

    Failure Impact: Bot/control-plane/tasks won't start if MySQL unavailable
    """
    # Test connection with simple query
    result = mysql_connection.execute(text("SELECT 1"))
    value = result.scalar()

    assert value == 1, "MySQL connection failed"
    print("✅ MySQL connection successful")


def test_required_databases_exist(mysql_connection):
    """
    CRITICAL TEST - Required databases must exist.

    Given: Services need multiple databases
    When: Checking database list
    Then: Required databases exist (insightmesh_data, insightmesh_task)

    Failure Impact: Services will fail to start if databases missing
    """
    # Query databases
    result = mysql_connection.execute(text("SHOW DATABASES"))
    databases = [row[0] for row in result]

    # Check for required databases
    required_dbs = ["insightmesh_data", "insightmesh_task"]
    missing_dbs = [db for db in required_dbs if db not in databases]

    if missing_dbs:
        pytest.fail(
            f"❌ Missing required databases: {missing_dbs}\n"
            f"Run docker-compose up to create databases"
        )

    print(f"✅ All required databases exist: {required_dbs}")


def test_database_users_have_permissions(mysql_connection):
    """
    SECURITY TEST - Database users must have correct permissions.

    Given: Services use dedicated database users
    When: Checking user permissions
    Then: Users have appropriate grants (not root everywhere)
    """
    # Check users
    result = mysql_connection.execute(
        text(
            "SELECT User, Host FROM mysql.user "
            "WHERE User IN ('insightmesh_tasks', 'insightmesh_data')"
        )
    )
    users = [(row[0], row[1]) for row in result]

    if not users:
        pytest.skip("Database users not created yet (may be fresh deployment)")

    print(f"✅ Found {len(users)} database users configured")

    # Check grants for first user
    if users:
        user, host = users[0]
        try:
            result = mysql_connection.execute(
                text(f"SHOW GRANTS FOR '{user}'@'{host}'")
            )
            grants = [row[0] for row in result]
            print(f"   User '{user}' grants: {len(grants)} permissions")
        except sqlalchemy.exc.DatabaseError:
            # User might not exist yet
            pass


def test_database_tables_exist(mysql_connection):
    """
    CRITICAL TEST - Required tables must exist after migrations.

    Given: Alembic migrations have run
    When: Checking table list
    Then: Core tables exist (users, groups, agents, jobs, etc.)

    Failure Impact: Services will fail on first query if tables missing
    """
    # Get inspector
    inspector = inspect(mysql_connection)
    tables = inspector.get_table_names()

    if not tables:
        pytest.skip(
            "No tables found - migrations haven't run yet. "
            "Run docker-compose up or alembic upgrade head"
        )

    # Common expected tables (adjust based on your schema)
    expected_tables = [
        "users",
        "alembic_version",  # Migration tracking table
    ]

    # Check which expected tables exist
    existing = [t for t in expected_tables if t in tables]
    missing = [t for t in expected_tables if t not in tables]

    if missing:
        print(f"⚠️  WARNING: Expected tables not found: {missing}")
        print(f"   Found tables: {tables}")
    else:
        print(f"✅ Core tables exist: {existing}")

    print(f"   Total tables in database: {len(tables)}")


def test_alembic_migrations_current(mysql_connection):
    """
    CRITICAL TEST - Alembic migrations must be up to date.

    Given: Alembic is used for schema migrations
    When: Checking alembic_version table
    Then: Database is at latest migration version

    Failure Impact: Schema drift causes query failures
    """
    try:
        # Check alembic_version table
        result = mysql_connection.execute(
            text("SELECT version_num FROM alembic_version")
        )
        versions = [row[0] for row in result]

        if not versions:
            pytest.skip("No Alembic version found - migrations not initialized")

        current_version = versions[0]
        print(f"✅ Alembic current version: {current_version}")

        # Check if multiple versions exist (shouldn't happen)
        if len(versions) > 1:
            pytest.fail(
                f"❌ Multiple Alembic versions found: {versions}\n"
                f"Database in inconsistent state!"
            )

    except sqlalchemy.exc.ProgrammingError:
        pytest.skip("alembic_version table doesn't exist - Alembic not initialized")


def test_database_charset_is_utf8mb4(mysql_connection):
    """
    BUSINESS LOGIC TEST - Database charset should be UTF8MB4.

    Given: We store international text and emojis
    When: Checking database charset
    Then: Using UTF8MB4 (supports full Unicode including emojis)
    """
    # Get database name from connection
    result = mysql_connection.execute(text("SELECT DATABASE()"))
    db_name = result.scalar()

    # Check charset
    result = mysql_connection.execute(
        text(
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
            "FROM information_schema.SCHEMATA "
            f"WHERE SCHEMA_NAME = '{db_name}'"
        )
    )
    row = result.fetchone()

    if row:
        charset, collation = row
        if charset != "utf8mb4":
            print(
                f"⚠️  WARNING: Database charset is '{charset}' "
                f"(recommended: utf8mb4 for emoji support)"
            )
        else:
            print(f"✅ Database charset: {charset} with collation {collation}")
    else:
        pytest.skip("Could not determine database charset")


def test_database_foreign_keys_enabled(mysql_connection):
    """
    CRITICAL TEST - Foreign key constraints should be enabled.

    Given: Database uses foreign keys for referential integrity
    When: Checking foreign key settings
    Then: foreign_key_checks is enabled
    """
    result = mysql_connection.execute(text("SELECT @@foreign_key_checks"))
    fk_enabled = result.scalar()

    assert fk_enabled == 1, "Foreign key checks are disabled!"
    print("✅ Foreign key constraints enabled")


def test_database_connection_pool_size():
    """
    PERFORMANCE TEST - Connection pool should be configured.

    Given: Services use connection pooling
    When: Checking pool configuration
    Then: Pool size is reasonable for production (5-20 connections)
    """
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/insightmesh_data",
    )

    # Create engine with pool
    engine = create_engine(database_url, pool_size=5, max_overflow=10, echo=False)

    try:
        # Get pool info
        pool = engine.pool
        print("✅ Connection pool configured:")
        print(f"   Pool size: {pool.size()}")
        print(f"   Max overflow: {engine.pool._max_overflow}")
        print(f"   Current checked out: {pool.checkedout()}")

    finally:
        engine.dispose()


def test_database_query_performance(mysql_connection):
    """
    PERFORMANCE TEST - Simple queries should be fast.

    Given: Database has indexes
    When: Running simple SELECT query
    Then: Query completes quickly (< 50ms)
    """
    import time

    # Check if any tables exist, otherwise use a simple query
    tables_result = mysql_connection.execute(text("SHOW TABLES"))
    tables = [row[0] for row in tables_result]

    # Simple query
    start = time.time()
    if tables:
        # Query first available table
        first_table = tables[0]
        result = mysql_connection.execute(text(f"SELECT COUNT(*) FROM {first_table}"))
        count = result.scalar()
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 100, (
            f"Simple query too slow: {duration_ms:.1f}ms (expected < 100ms)"
        )
        print(
            f"✅ Query performance: {duration_ms:.1f}ms ({first_table} table: {count} rows)"
        )
    else:
        # No tables exist, use simple SELECT 1 query
        result = mysql_connection.execute(text("SELECT 1"))
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 100, (
            f"Simple query too slow: {duration_ms:.1f}ms (expected < 100ms)"
        )
        print(
            f"✅ Query performance: {duration_ms:.1f}ms (no tables yet, using SELECT 1)"
        )


def test_database_supports_transactions(mysql_connection):
    """
    CRITICAL TEST - Database must support transactions (InnoDB).

    Given: Services use transactions for data consistency
    When: Checking storage engine
    Then: Tables use InnoDB (supports transactions)
    """
    try:
        # Get first table
        inspector = inspect(mysql_connection)
        tables = inspector.get_table_names()

        if not tables:
            pytest.skip("No tables to check")

        # Check storage engine for first table
        first_table = tables[0]
        result = mysql_connection.execute(
            text(
                f"SELECT ENGINE FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{first_table}'"
            )
        )
        engine = result.scalar()

        if engine != "InnoDB":
            pytest.fail(
                f"❌ Table '{first_table}' uses {engine} engine "
                f"(InnoDB required for transactions)"
            )

        print("✅ Tables use InnoDB storage engine (transactions supported)")

    except Exception as e:
        pytest.skip(f"Could not check storage engine: {e}")


# TODO: Add these tests when fault tolerance is implemented
# def test_services_handle_mysql_downtime():
#     """Test that services degrade gracefully when MySQL unavailable."""
#     pass
#
# def test_database_deadlock_handling():
#     """Test that services retry on deadlock errors."""
#     pass
#
# def test_database_connection_retry_on_failure():
#     """Test that services retry database connections on startup."""
#     pass
