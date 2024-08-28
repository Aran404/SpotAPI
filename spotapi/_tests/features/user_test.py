import pytest
from spotapi import User
from spotapi.exceptions import UserError
from spotapi.login import Login
from spotapi._tests.features.session import _MainFixture

instance = User(login=_MainFixture.login)


def test_user_initialization():
    """Test the initialization of the User class."""
    user_with_login = User(login=_MainFixture.login)
    assert user_with_login.login == _MainFixture.login
    assert user_with_login._user_plan is None
    assert user_with_login._user_info is None


def test_has_premium():
    """Test the has_premium property."""
    user = User(login=_MainFixture.login)
    plan_info = user.get_plan_info()

    assert "plan" in plan_info
    assert "name" in plan_info["plan"]
    if plan_info["plan"]["name"] == "Spotify Premium":
        assert user.has_premium is True
    else:
        assert user.has_premium is False


def test_username():
    """Test the username property."""
    user = User(login=_MainFixture.login)
    user_info = user.get_user_info()

    assert "profile" in user_info
    assert "username" in user_info["profile"]
    assert user.username == user_info["profile"]["username"]


def test_get_plan_info():
    """Test the get_plan_info method."""
    user = User(login=_MainFixture.login)
    plan_info = user.get_plan_info()

    assert "plan" in plan_info
    assert "name" in plan_info["plan"]


def test_edit_user_info():
    """Test the edit_user_info method."""
    user = User(login=_MainFixture.login)
    user_info = user.get_user_info()

    # Prepare data to update
    updated_info = dict(user_info).copy()
    updated_info["profile"]["email"] = "new_email@example.com"

    try:
        user.edit_user_info(updated_info)
        updated_user_info = user.get_user_info()
        assert updated_user_info["profile"]["email"] == "new_email@example.com"
    except UserError as e:
        pytest.fail(f"UserError occurred: {e}")
