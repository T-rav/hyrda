"""Integration tests for SlackUserImportJob.

These tests verify:
1. Slack SDK response schema contract (field names, pagination structure)
2. SQLAlchemy database write path end-to-end (INSERT + UPDATE + upsert logic)
   using sqlite:///:memory: so no real database is required
3. SlackUser model column contract against the expected slack_users table DDL
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from jobs.slack_user_import import SlackUser, SlackUserImportJob

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _build_slack_user(
    user_id="U1234567",
    name="john.doe",
    real_name="John Doe",
    display_name="John",
    email="john@example.com",
    is_admin=False,
    is_owner=False,
    is_bot=False,
    deleted=False,
    tz="America/New_York",
):
    """Build a realistic Slack users.list member dict."""
    return {
        "id": user_id,
        "name": name,
        "real_name": real_name,
        "profile": {
            "display_name": display_name,
            "email": email,
            "status_text": "",
        },
        "is_admin": is_admin,
        "is_owner": is_owner,
        "is_bot": is_bot,
        "deleted": deleted,
        "tz": tz,
        "updated": 1234567890,
    }


def _build_slack_response(members, next_cursor=""):
    """Build a Slack users.list response dict."""
    return {
        "ok": True,
        "members": members,
        "response_metadata": {"next_cursor": next_cursor},
    }


def _make_in_memory_session():
    """Create a SQLAlchemy session backed by a fresh in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    SlackUser.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def test_settings(tmp_path):
    """Real TasksSettings backed by a temporary SQLite database."""
    import os

    db_file = tmp_path / "data.db"
    os.environ.update(
        {
            "SECRET_KEY": "test-secret-key",
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "TASK_DATABASE_URL": f"sqlite:///{tmp_path / 'tasks.db'}",
            "DATA_DATABASE_URL": f"sqlite:///{db_file}",
        }
    )
    from config.settings import TasksSettings

    return TasksSettings()


@pytest.fixture
def job(test_settings):
    """SlackUserImportJob with a real in-memory data DB."""
    job = SlackUserImportJob(test_settings)
    # Override _get_data_session to use in-memory SQLite
    engine = create_engine("sqlite:///:memory:")
    SlackUser.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _in_memory_session():
        return Session()

    job._get_data_session = _in_memory_session
    return job


# ===========================================================================
# 1. SlackUser model column contract
# ===========================================================================


class TestSlackUserModelContract:
    """Verify the inline SlackUser model matches the expected DDL."""

    def test_tablename(self):
        assert SlackUser.__tablename__ == "slack_users"

    def test_required_columns_exist(self):
        """All expected columns must be present in the model."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("slack_users")}
        expected = {
            "id",
            "slack_user_id",
            "email_address",
            "display_name",
            "real_name",
            "is_active",
            "user_type",
            "created_at",
            "updated_at",
        }
        assert expected == columns

    def test_slack_user_id_is_unique(self):
        """slack_user_id column must have a unique constraint."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        inspector = inspect(engine)
        unique_constraints = inspector.get_unique_constraints("slack_users")
        unique_cols = {col for uc in unique_constraints for col in uc["column_names"]}
        # Also check via indexes (SQLite renders unique as unique index)
        indexes = inspector.get_indexes("slack_users")
        unique_indexed_cols = {
            col for idx in indexes if idx.get("unique") for col in idx["column_names"]
        }
        all_unique = unique_cols | unique_indexed_cols
        assert "slack_user_id" in all_unique

    def test_is_active_not_nullable(self):
        """is_active must be NOT NULL."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        inspector = inspect(engine)
        col_map = {col["name"]: col for col in inspector.get_columns("slack_users")}
        assert col_map["is_active"]["nullable"] is False

    def test_slack_user_id_not_nullable(self):
        """slack_user_id must be NOT NULL."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        inspector = inspect(engine)
        col_map = {col["name"]: col for col in inspector.get_columns("slack_users")}
        assert col_map["slack_user_id"]["nullable"] is False

    def test_user_type_is_nullable(self):
        """user_type is nullable (admin/member/bot can be NULL during initial load)."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        inspector = inspect(engine)
        col_map = {col["name"]: col for col in inspector.get_columns("slack_users")}
        assert col_map["user_type"]["nullable"] is True


# ===========================================================================
# 2. Slack SDK response schema contract
# ===========================================================================


class TestSlackSdkResponseContract:
    """Verify the job correctly interprets the Slack users.list response shape."""

    @pytest.mark.asyncio
    async def test_fetch_reads_members_key(self, job):
        """_fetch_slack_users reads 'members' key from the SDK response."""
        member = _build_slack_user()
        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([member])
        job.slack_client = mock_client

        users = await job._fetch_slack_users(include_deactivated=True)

        assert len(users) == 1
        assert users[0]["id"] == "U1234567"

    @pytest.mark.asyncio
    async def test_fetch_reads_ok_flag(self, job):
        """_fetch_slack_users raises RuntimeError when ok=False."""
        mock_client = MagicMock()
        mock_client.users_list.return_value = {"ok": False, "error": "invalid_auth"}
        job.slack_client = mock_client

        with pytest.raises(RuntimeError, match="Slack API error"):
            await job._fetch_slack_users(include_deactivated=False)

    @pytest.mark.asyncio
    async def test_fetch_pagination_via_next_cursor(self, job):
        """_fetch_slack_users follows pagination using response_metadata.next_cursor."""
        page1_user = _build_slack_user("U0000001")
        page2_user = _build_slack_user("U0000002")

        page1 = _build_slack_response([page1_user], next_cursor="cursor-abc")
        page2 = _build_slack_response([page2_user], next_cursor="")

        mock_client = MagicMock()
        mock_client.users_list.side_effect = [page1, page2]
        job.slack_client = mock_client

        users = await job._fetch_slack_users(include_deactivated=True)

        assert len(users) == 2
        assert mock_client.users_list.call_count == 2
        # Second call must pass the cursor from the first response
        second_call_kwargs = mock_client.users_list.call_args_list[1][1]
        assert second_call_kwargs["cursor"] == "cursor-abc"

    @pytest.mark.asyncio
    async def test_fetch_excludes_deleted_when_not_include_deactivated(self, job):
        """Deleted users are filtered out when include_deactivated=False."""
        active = _build_slack_user("U0000001", deleted=False)
        deleted = _build_slack_user("U0000002", deleted=True)

        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([active, deleted])
        job.slack_client = mock_client

        users = await job._fetch_slack_users(include_deactivated=False)

        assert len(users) == 1
        assert users[0]["id"] == "U0000001"

    @pytest.mark.asyncio
    async def test_fetch_includes_deleted_when_include_deactivated_true(self, job):
        """Deleted users are included when include_deactivated=True."""
        active = _build_slack_user("U0000001", deleted=False)
        deleted = _build_slack_user("U0000002", deleted=True)

        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([active, deleted])
        job.slack_client = mock_client

        users = await job._fetch_slack_users(include_deactivated=True)

        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_fetch_uses_limit_200_and_include_locale(self, job):
        """users_list is called with limit=200 and include_locale=True."""
        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([])
        job.slack_client = mock_client

        await job._fetch_slack_users(include_deactivated=False)

        call_kwargs = mock_client.users_list.call_args[1]
        assert call_kwargs["limit"] == 200
        assert call_kwargs["include_locale"] is True


# ===========================================================================
# 3. Database write path (INSERT + UPDATE + upsert logic)
# ===========================================================================


class TestDatabaseWritePath:
    """End-to-end database write tests using sqlite:///:memory:."""

    @pytest.mark.asyncio
    async def test_new_user_inserted(self, job):
        """A user not yet in the DB must be inserted as a new row."""
        users = [
            {
                "id": "U9999001",
                "email": "new@example.com",
                "display_name": "New User",
                "real_name": "New User Real",
                "is_active": True,
                "user_type": "member",
            }
        ]
        result = await job._store_users_in_database(users)

        assert result["new_users_count"] == 1
        assert result["updated_users_count"] == 0
        assert result["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_existing_user_updated_not_duplicated(self, job):
        """A user that already exists must be updated, not duplicated."""
        users = [
            {
                "id": "U9999002",
                "email": "existing@example.com",
                "display_name": "Existing User",
                "real_name": "Existing",
                "is_active": True,
                "user_type": "member",
            }
        ]
        # First write
        await job._store_users_in_database(users)

        # Update with new email
        users[0]["email"] = "updated@example.com"
        result = await job._store_users_in_database(users)

        assert result["new_users_count"] == 0
        assert result["updated_users_count"] == 1
        assert result["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_updated_user_fields_are_persisted(self, job):
        """After an update, the new field values must be readable from the DB."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        job._get_data_session = lambda: session

        users = [
            {
                "id": "U9999003",
                "email": "before@example.com",
                "display_name": "Before",
                "real_name": "Before Real",
                "is_active": True,
                "user_type": "member",
            }
        ]
        await job._store_users_in_database(users)

        users[0]["email"] = "after@example.com"
        users[0]["display_name"] = "After"
        users[0]["is_active"] = False
        users[0]["user_type"] = "admin"
        await job._store_users_in_database(users)

        from sqlalchemy import select

        db_user = session.execute(
            select(SlackUser).where(SlackUser.slack_user_id == "U9999003")
        ).scalar_one()
        assert db_user.email_address == "after@example.com"
        assert db_user.display_name == "After"
        assert db_user.is_active is False
        assert db_user.user_type == "admin"

    @pytest.mark.asyncio
    async def test_multiple_users_processed_in_single_transaction(self, job):
        """Multiple users are written in one call."""
        users = [
            {
                "id": f"U888000{i}",
                "email": f"user{i}@example.com",
                "display_name": f"User {i}",
                "real_name": f"Real {i}",
                "is_active": True,
                "user_type": "member",
            }
            for i in range(5)
        ]
        result = await job._store_users_in_database(users)

        assert result["processed_count"] == 5
        assert result["new_users_count"] == 5
        assert result["updated_users_count"] == 0

    @pytest.mark.asyncio
    async def test_mixed_insert_and_update(self, job):
        """A batch with both new and existing users is handled correctly."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        job._get_data_session = lambda: session

        existing_user = {
            "id": "U7777001",
            "email": "existing@example.com",
            "display_name": "Existing",
            "real_name": "Existing Real",
            "is_active": True,
            "user_type": "member",
        }
        await job._store_users_in_database([existing_user])

        batch = [
            existing_user,  # should be updated
            {
                "id": "U7777002",
                "email": "brand.new@example.com",
                "display_name": "Brand New",
                "real_name": "Brand New Real",
                "is_active": True,
                "user_type": "admin",
            },
        ]
        result = await job._store_users_in_database(batch)

        assert result["new_users_count"] == 1
        assert result["updated_users_count"] == 1
        assert result["processed_count"] == 2

    @pytest.mark.asyncio
    async def test_is_active_false_for_deactivated_user(self, job):
        """is_active=False is persisted correctly for deactivated users."""
        engine = create_engine("sqlite:///:memory:")
        SlackUser.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        job._get_data_session = lambda: session

        users = [
            {
                "id": "U6666001",
                "email": "deactivated@example.com",
                "display_name": "Gone",
                "real_name": "Gone Real",
                "is_active": False,
                "user_type": "member",
            }
        ]
        await job._store_users_in_database(users)

        from sqlalchemy import select

        db_user = session.execute(
            select(SlackUser).where(SlackUser.slack_user_id == "U6666001")
        ).scalar_one()
        assert db_user.is_active is False


# ===========================================================================
# 4. _filter_users contract tests
# ===========================================================================


class TestFilterUsersContract:
    """Verify the _filter_users method correctly interprets Slack user fields."""

    def test_bot_excluded_by_default(self, job):
        """is_bot=True users are excluded when 'bot' not in user_types."""
        users = [
            _build_slack_user("U1", is_bot=True),
            _build_slack_user("U2", is_bot=False),
        ]
        filtered = job._filter_users(users, ["member"])
        ids = [u["id"] for u in filtered]
        assert "U1" not in ids
        assert "U2" in ids

    def test_bot_included_when_bot_in_user_types(self, job):
        """is_bot=True users are included when 'bot' is in user_types.

        The filter logic checks admin/owner/member eligibility independently of
        the bot flag.  A plain bot (non-admin, non-owner) is treated as a member
        by the type filter, so "member" must also be in user_types for the bot
        to pass through.
        """
        users = [_build_slack_user("U1", is_bot=True)]
        filtered = job._filter_users(users, ["bot", "member"])
        assert len(filtered) == 1
        assert filtered[0]["user_type"] == "bot"

    def test_admin_user_type_assigned_correctly(self, job):
        """is_admin=True results in user_type='admin'."""
        users = [_build_slack_user("U1", is_admin=True)]
        filtered = job._filter_users(users, ["admin"])
        assert filtered[0]["user_type"] == "admin"

    def test_owner_user_type_assigned_correctly(self, job):
        """is_owner=True results in user_type='owner'."""
        users = [_build_slack_user("U1", is_owner=True)]
        filtered = job._filter_users(users, ["owner"])
        assert filtered[0]["user_type"] == "owner"

    def test_member_user_type_assigned_correctly(self, job):
        """Regular (non-admin, non-owner, non-bot) user gets user_type='member'."""
        users = [_build_slack_user("U1")]
        filtered = job._filter_users(users, ["member"])
        assert filtered[0]["user_type"] == "member"

    def test_bot_type_takes_priority_over_admin(self, job):
        """If a user is both a bot and admin, user_type='bot' (priority order)."""
        users = [_build_slack_user("U1", is_bot=True, is_admin=True)]
        filtered = job._filter_users(users, ["bot", "admin"])
        assert filtered[0]["user_type"] == "bot"

    def test_owner_takes_priority_over_admin(self, job):
        """If a user is both owner and admin, user_type='owner'."""
        users = [_build_slack_user("U1", is_owner=True, is_admin=True)]
        filtered = job._filter_users(users, ["owner", "admin"])
        assert filtered[0]["user_type"] == "owner"

    def test_profile_email_extracted(self, job):
        """email is extracted from profile.email field."""
        user = _build_slack_user("U1", email="test@example.com")
        filtered = job._filter_users([user], ["member"])
        assert filtered[0]["email"] == "test@example.com"

    def test_profile_display_name_extracted(self, job):
        """display_name is extracted from profile.display_name field."""
        user = _build_slack_user("U1", display_name="My Display")
        filtered = job._filter_users([user], ["member"])
        assert filtered[0]["display_name"] == "My Display"

    def test_is_active_is_inverse_of_deleted(self, job):
        """is_active=True when deleted=False, is_active=False when deleted=True."""
        active_user = _build_slack_user("U1", deleted=False)
        inactive_user = _build_slack_user("U2", deleted=True)
        filtered = job._filter_users([active_user, inactive_user], ["member"])
        active = next(u for u in filtered if u["id"] == "U1")
        inactive = next(u for u in filtered if u["id"] == "U2")
        assert active["is_active"] is True
        assert inactive["is_active"] is False

    def test_admin_excluded_when_not_in_user_types(self, job):
        """Admin users are excluded when 'admin' not in user_types."""
        users = [
            _build_slack_user("U1", is_admin=True),
            _build_slack_user("U2", is_admin=False),
        ]
        filtered = job._filter_users(users, ["member"])
        ids = [u["id"] for u in filtered]
        assert "U1" not in ids
        assert "U2" in ids

    def test_empty_user_list_returns_empty(self, job):
        """Empty input returns empty output."""
        assert job._filter_users([], ["member", "admin"]) == []


# ===========================================================================
# 5. Full execution path (mocked Slack, real DB)
# ===========================================================================


class TestFullExecutionPath:
    """End-to-end execute() test: mocked Slack SDK + real in-memory SQLite."""

    @pytest.mark.asyncio
    async def test_execute_inserts_users_into_db(self, job):
        """execute() fetches users from Slack and writes them to the database."""
        slack_users = [
            _build_slack_user("U5555001", name="alice", email="alice@example.com"),
            _build_slack_user(
                "U5555002", name="bob", is_admin=True, email="bob@example.com"
            ),
        ]
        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response(slack_users)
        job.slack_client = mock_client

        result = await job.execute()

        assert result["status"] == "success"
        job_result = result["result"]
        assert job_result["total_users_fetched"] == 2
        assert job_result["records_processed"] == 2

    @pytest.mark.asyncio
    async def test_execute_result_structure(self, job):
        """execute() result must include all expected keys."""
        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([])
        job.slack_client = mock_client

        result = await job.execute()

        assert result["status"] == "success"
        job_result = result["result"]
        for key in (
            "records_processed",
            "records_success",
            "records_failed",
            "total_users_fetched",
            "filtered_users_count",
            "new_users_count",
            "updated_users_count",
            "users_sample",
        ):
            assert key in job_result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_execute_counts_new_and_updated_separately(self, job):
        """new_users_count and updated_users_count are tracked independently."""
        user = _build_slack_user("U4444001")
        mock_client = MagicMock()
        mock_client.users_list.return_value = _build_slack_response([user])
        job.slack_client = mock_client

        # First run: inserts
        result1 = await job.execute()
        assert result1["result"]["new_users_count"] == 1
        assert result1["result"]["updated_users_count"] == 0

        # Second run: updates
        result2 = await job.execute()
        assert result2["result"]["new_users_count"] == 0
        assert result2["result"]["updated_users_count"] == 1
