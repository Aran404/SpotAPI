""" 
Saver.py contains a few saver implementations using the SaverProtocol interface. 
These are popular savers that are used for session storing, but if you need a different saver, you can implement it yourself quite easily.
"""

from spotify.exceptions import SaverError
from spotify.interfaces import SaverProtocol
from readerwriterlock import rwlock
from typing import Any, List, Optional, Mapping
from psycopg2.extras import RealDictCursor
import psycopg2
import sqlite3
import pymongo
import atexit
import redis
import json
import os


class JSONSaver(SaverProtocol):
    """
    CRUD methods for JSON files
    """

    def __init__(self, path: Optional[str] = "sessions.json") -> None:
        self.path = path

        self.rwlock = rwlock.RWLockFairD()
        self.rlock = self.rwlock.gen_rlock()
        self.wlock = self.rwlock.gen_wlock()

    def save(self, data: List[Mapping[str, Any]], **kwargs) -> None:
        """
        Save data to a JSON file

        Kwargs
        -------
        overwrite (bool, optional): Defaults to False.
            Overwrites the entire file instead of appending.
        """
        with self.wlock:
            if len(data) == 0:
                raise ValueError("No data to save")

            if not os.path.exists(self.path):
                open(self.path, "w").close()

            if kwargs.get("overwrite", False):
                current = []
            else:
                with open(self.path, "r") as f:
                    file_content = f.read()
                    current = json.loads(file_content) if file_content.strip() else []

            current.extend(data)

            with open(self.path, "w") as f:
                json.dump(current, f, indent=4)

    def load(self, query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        """
        Load data from a JSON file given a query

        Kwargs
        -------
        allow_collisions (bool, optional): Defaults to False.
            Raises an error if the query returns more than one result.
        """
        with self.rlock:
            if not query:
                raise ValueError("Query dictionary cannot be empty")

            with open(self.path, "r") as f:
                data = json.load(f)

            allow_collisions = kwargs.get("allow_collisions", False)
            matches: List[Mapping[str, Any]] = []

            for item in data:
                if all(item[key] == query[key] for key in query):
                    matches.append(item)
                    # Save time by checking for collisions each iteration
                    if allow_collisions and len(matches) > 1:
                        raise SaverError("Collision found")

            if len(matches) >= 1:
                return matches[0]

            raise SaverError("Item not found")

    def delete(self, query: Mapping[str, Any], **kwargs) -> None:
        """
        Delete data from a JSON file given a query

        Kwargs
        -------
        all_instances (bool, optional): Defaults to True.
            Deletes all instances of the query.

        clear_all (bool, optional): Defaults to False.
            Deletes all data in the file.
        """
        with self.wlock:
            if not query:
                raise ValueError("Query dictionary cannot be empty")

            delete_all_instances = kwargs.get("all_instances", True)
            clear_all = kwargs.get("clear_all", False)

            if clear_all:
                with open(self.path, "w") as f:
                    return json.dump([], f)

            with open(self.path, "r") as f:
                data = json.load(f)

            assert isinstance(data, list), "JSON must be an array"

            # Copy the list to avoid modifying the original
            for item in data.copy():
                if all(item[key] == query[key] for key in query):
                    data.remove(item)
                    if not delete_all_instances:
                        break

            with open(self.path, "w") as f:
                json.dump(data, f, indent=4)


class SqliteSaver(SaverProtocol):
    """
    CRUD methods for SQLite3 files
    """

    def __init__(self, path: str = "sessions.db") -> None:
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # Create table
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                identifier TEXT PRIMARY KEY NOT NULL,
                password TEXT NOT NULL, 
                cookies TEXT
            )
        """
        )

        # Cleanup
        atexit.register(self.cursor.close)
        atexit.register(self.conn.close)

        # Sqlite may not behave as intended under multi-threaded environments
        self.rwlock = rwlock.RWLockFairD()
        self.rlock = self.rwlock.gen_rlock()
        self.wlock = self.rwlock.gen_wlock()

    def save(self, data: List[Mapping[str, Any]], **kwargs) -> None:
        """
        Saves data to a SQLite3 database

        Kwargs
        -------
        overwrite (bool, optional): Defaults to False.
            Overwrites the entire database instead of appending.
        """
        with self.wlock:
            try:
                if len(data) == 0:
                    raise ValueError("No data to save")

                if kwargs.get("overwrite", False):
                    self.cursor.execute("DELETE FROM sessions")
                    self.conn.commit()

                for item in data:
                    self.cursor.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?)",
                        (
                            item["identifier"],
                            item["password"],
                            json.dumps(item["cookies"]),
                        ),
                    )

                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                raise SaverError(e)

    def load(self, query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        """
        Loads data from a SQLite3 database given a query
        """

        with self.rlock:
            if not query:
                raise ValueError("Query dictionary cannot be empty")

            # Turn dictionary into sql query
            sql = "SELECT * FROM sessions WHERE "
            params = []

            for key, value in query.items():
                sql += f"{key} = ? AND "
                params.append(value)

            self.cursor.execute(sql[:-5], tuple(params))
            result = self.cursor.fetchall()

            if len(result) == 0:
                raise SaverError("Item not found")

            return result[0]

    def delete(self, query: Mapping[str, Any], **kwargs) -> None:
        """
        Deletes data from a SQLite3 database given a query
        """
        with self.wlock:
            if not query:
                raise ValueError("Query dictionary cannot be empty")

            # Turn dictionary into sql query
            sql = "DELETE FROM sessions WHERE "
            params = []

            for key, value in query.items():
                sql += f"{key} = ? AND "
                params.append(value)

            self.cursor.execute(sql[:-5], tuple(params))
            self.conn.commit()


class MongoSaver(SaverProtocol):
    """
    CRUD methods for MongoDB
    """

    def __init__(
        self,
        host: Optional[str] = "mongodb://localhost:27017/",
        database_name: Optional[str] = "spotify",
        collection: Optional[str] = "sessions",
    ) -> None:
        self.conn = pymongo.MongoClient(host)
        self.database = self.conn[database_name]
        self.collection = self.database[collection]

        atexit.register(self.conn.close)

    def save(self, data: List[Mapping[str, Any]], **kwargs) -> None:
        if len(data) == 0:
            raise ValueError("No data to save")

        self.collection.insert_many(data)

    def load(self, query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        result = self.collection.find_one(query)

        if result is None:
            raise SaverError("Item not found")

        return result

    def delete(self, query: Mapping[str, Any], **kwargs) -> None:
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        self.collection.delete_one(query)


class PostgresSaver(SaverProtocol):
    def __init__(self, dsn: str) -> None:
        self.conn = psycopg2.connect(dsn)
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        self._create_table()

        atexit.register(self.conn.close)

    def _create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                identifier TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                cookies JSONB
            )
        """
        )
        self.conn.commit()

    def save(self, data: List[Mapping[str, Any]], **kwargs) -> None:
        if len(data) == 0:
            raise ValueError("No data to save")

        overwrite = kwargs.get("overwrite", False)
        if overwrite:
            self.cursor.execute("DELETE FROM sessions")
            self.conn.commit()

        for item in data:
            self.cursor.execute(
                "INSERT INTO sessions (identifier, password, cookies) VALUES (%s, %s, %s) ON CONFLICT (identifier) DO UPDATE SET password = EXCLUDED.password, cookies = EXCLUDED.cookies",
                (item["identifier"], item["password"], json.dumps(item["cookies"])),
            )

        self.conn.commit()

    def load(self, query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        sql = "SELECT * FROM sessions WHERE "
        params = []
        for key, value in query.items():
            sql += f"{key} = %s AND "
            params.append(value)

        self.cursor.execute(sql[:-5], params)
        result = self.cursor.fetchone()

        if result is None:
            raise SaverError("Item not found")

        return result

    def delete(self, query: Mapping[str, Any], **kwargs) -> None:
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        sql = "DELETE FROM sessions WHERE "
        params = []
        for key, value in query.items():
            sql += f"{key} = %s AND "
            params.append(value)

        self.cursor.execute(sql[:-5], params)
        self.conn.commit()


class RedisSaver(SaverProtocol):
    def __init__(
        self, host: Optional[str] = "localhost", port: int = 6379, db: int = 0
    ) -> None:
        self.client = redis.StrictRedis(host=host, port=port, db=db)
        atexit.register(self.client.close)

    def save(self, data: List[Mapping[str, Any]], **kwargs) -> None:
        if len(data) == 0:
            raise ValueError("No data to save")

        for item in data:
            self.client.set(item["identifier"], json.dumps(item))

    def load(self, query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        """
        Loads data from a Redis database given a query.

        Due to the nature of Redis, the query must be a singular identifier.
        """
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        identifier = query.get("identifier")
        if not identifier:
            raise ValueError("Identifier is required for Redis lookup")

        result = self.client.get(identifier)
        if not result:
            raise SaverError("Item not found")

        return json.loads(result)

    def delete(self, query: Mapping[str, Any], **kwargs) -> None:
        if not query:
            raise ValueError("Query dictionary cannot be empty")

        identifier = query.get("identifier")
        if not identifier:
            raise ValueError("Identifier is required for Redis lookup")

        self.client.delete(identifier)
