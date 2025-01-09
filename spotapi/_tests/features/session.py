import dotenv
import pytest
import os

from spotapi import JSONSaver, Login, Config, Logger, solver_clients

dotenv.load_dotenv()


class _MainFixtures:
    def __init__(self) -> None:
        email = os.getenv("EMAIL")
        password = os.getenv("PASSWORD")
        api_key = os.getenv("CAPSOLVER_API_KEY")

        self.saver = JSONSaver("./spotapi/_tests/sessions.json")  # From home dir

        if not email:
            return pytest.fail("Missing EMAIL environment variable")

        if not (password and api_key):
            try:
                self.login = Login.from_saver(self.saver, Config(Logger()), email)
            except:
                return pytest.fail("Missing environment variables")

        assert api_key and password
        _cfg = Config(logger=Logger(), solver=solver_clients.Capsolver(api_key))

        if not hasattr(self, "login"):
            self.login = Login(_cfg, password, email=email)
            self.login.login()
            self.login.save(self.saver)


_MainFixture = _MainFixtures()
