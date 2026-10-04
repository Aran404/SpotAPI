"""Offline regression tests for optional saver dependencies."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from spotapi import MongoSaver, RedisSaver, SqliteSaver
from spotapi.utils import saver as saver_module


def test_mongo_initialization_with_available_dependency(monkeypatch):
    # Arrange
    client = MagicMock()
    mongo_client = MagicMock(return_value=client)
    monkeypatch.setitem(
        sys.modules, "pymongo", SimpleNamespace(MongoClient=mongo_client)
    )
    register = MagicMock()
    monkeypatch.setattr(saver_module.atexit, "register", register)

    # Act
    saver = MongoSaver("mongodb://example:27017/", "test_db", "test_sessions")

    # Assert
    mongo_client.assert_called_once_with("mongodb://example:27017/")
    assert saver.conn is client
    assert saver.database is client["test_db"]
    assert saver.collection is client["test_db"]["test_sessions"]
    register.assert_called_once_with(client.close)


def test_redis_initialization_with_available_dependency(monkeypatch):
    # Arrange
    client = MagicMock()
    strict_redis = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(StrictRedis=strict_redis))
    register = MagicMock()
    monkeypatch.setattr(saver_module.atexit, "register", register)

    # Act
    saver = RedisSaver("example", 6380, 2)

    # Assert
    strict_redis.assert_called_once_with(host="example", port=6380, db=2)
    assert saver.client is client
    register.assert_called_once_with(client.close)


def test_sqlite_with_available_dependency(monkeypatch, tmp_path):
    # Arrange
    pytest.importorskip("sqlite3")
    monkeypatch.setattr(saver_module.atexit, "register", MagicMock())
    saver = SqliteSaver(str(tmp_path / "sessions.db"))
    # Act
    try:
        saver.save([{"identifier": "test", "password": "secret", "cookies": {}}])

        # Assert
        assert saver.load({"identifier": "test"}) == ("test", "secret", "{}")
        saver.delete({"identifier": "test"})
        with pytest.raises(saver_module.SaverError, match="Item not found"):
            saver.load({"identifier": "test"})
    finally:
        saver.cursor.close()
        saver.conn.close()
