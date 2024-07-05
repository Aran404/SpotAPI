from spotify.exceptions import SaverError
from spotify.interfaces import SaverProtocol
from readerwriterlock import rwlock
from typing import Any, List, Optional
import atexit
import sqlite3
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

    def save(self, data: List[dict[str, Any]], **kwargs) -> None:
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

    def load(self, query: dict[str, Any], **kwargs) -> dict[str, Any]:
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
            matches: List[dict[str, Any]] = []

            for item in data:
                if all(item[key] == query[key] for key in query):
                    matches.append(item)
                    # Save time by checking for collisions each iteration
                    if allow_collisions and len(matches) > 1:
                        raise SaverError("Collision found")

            if len(matches) >= 1:
                return matches[0]

            raise SaverError("Item not found")

    def delete(self, query: dict[str, Any], **kwargs) -> None:
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
        self.client = sqlite3.connect(self.path, check_same_thread=False)
        self.cursor = self.client.cursor()
        
        # Create table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                identifier TEXT PRIMARY KEY NOT NULL,
                password TEXT NOT NULL, 
                cookies TEXT
            )
        ''')
        
        # Cleanup
        atexit.register(self.cursor.close())
        atexit.register(self.client.close())
        
        # Sqlite may not behave as intended under multi-threaded environments
        self.rwlock = rwlock.RWLockFairD()
        self.rlock = self.rwlock.gen_rlock()
        self.wlock = self.rwlock.gen_wlock()
        

    def save(self, data: List[dict[str, Any]], **kwargs) -> None:
        """ 
        Saves data to a SQLite3 database
        
        Kwargs
        -------
        overwrite (bool, optional): Defaults to False.
            Overwrites the entire database instead of appending.
        """
        with self.wlock:
            if len(data) == 0:
                raise ValueError("No data to save")

            if kwargs.get("overwrite", False):
                self.cursor.execute("DELETE FROM sessions")
                self.client.commit()
            
            for item in data:
                self.cursor.execute(
                    "INSERT INTO sessions VALUES (?, ?, ?)",
                    (item["identifier"], item["password"], json.dumps(item["cookies"])),
                )

            self.client.commit()
            
    def load(self, query: dict[str, Any], **kwargs) -> dict[str, Any]:
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
        
    def delete(self, query: dict[str, Any], **kwargs) -> None:
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
            self.client.commit()