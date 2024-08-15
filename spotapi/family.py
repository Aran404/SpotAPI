import uuid
from spotapi.user import User
from spotapi.login import Login
from typing import Mapping, Any, List
from spotapi.exceptions.errors import FamilyError
from spotapi.utils.strings import parse_json_string


class JoinFamily:
    """
    Wrapper class for joining a family with a user and a host provided.
    """

    def __init__(self, user_login: Login, host: "Family", country: str) -> None:
        self.user = User(user_login)
        self.host = host
        self.country = country
        self.client = user_login.client

        self.family = self.host.get_family_home()
        self.address = self.family["address"]
        self.invite_token = self.family["inviteToken"]

        self.session_id = str(uuid.uuid4())

    def __get_session(self) -> None:
        url = f"https://www.spotify.com/ca-en/family/join/address/{self.invite_token}/"
        resp = self.client.get(url)


        if resp.fail:
            raise FamilyError("Could not get session", error=resp.error.string)

        self.csrf = parse_json_string(resp.response, "csrfToken")

    def __get_autocomplete(self, address: str) -> None:
        url = "https://www.spotify.com/api/mup/addresses/v1/address/autocomplete/"
        payload = {
            "text": address,
            "country": self.country,
            "sessionToken": self.session_id,
        }
        resp = self.client.post(url, headers={"X-Csrf-Token": self.csrf}, json=payload)


        if resp.fail:
            raise FamilyError("Could not get address", error=resp.error.string)

        self.addresses = resp.response["addresses"]
        self.csrf = resp.raw.headers.get("X-Csrf-Token")

    def __try_address(self, dump: dict) -> bool:
        url = "https://www.spotify.com/api/mup/addresses/v1/user/confirm-user-address/"
        payload = {
            "address_google_place_id": dump["address"]["googlePlaceId"],
            "session_token": self.session_id,
        }
        resp = self.client.post(url, headers={"X-Csrf-Token": self.csrf}, json=payload)


        self.csrf = resp.raw.headers.get("X-Csrf-Token")
        if resp.fail:
            return False

        return True

    def __get_address(self) -> str:
        self.__get_session()
        self.__get_autocomplete(self.address)

        for address in self.addresses:
            if self.__try_address(address):
                return address["address"]["googlePlaceId"]

        raise FamilyError("Could not get address")

    def __add_to_family(self, place_id: str) -> None:
        url = "https://www.spotify.com/api/family/v1/family/member/"
        payload = {
            "address": self.address,
            "placeId": place_id,
            "inviteToken": self.invite_token,
        }
        resp = self.client.post(url, headers={"X-Csrf-Token": self.csrf}, json=payload)


        if resp.fail:
            raise FamilyError("Could not add to family", error=resp.error.string)

    def add_to_family(self) -> None:
        place_id = self.__get_address()
        self.__add_to_family(place_id)


class Family(User):
    """
    Spotify Family generic methods.
    """

    def __init__(self, login: Login) -> None:
        super().__init__(login)

        if not self.has_premium:
            raise ValueError("Must have premium to use this class")

        self._user_family: Mapping[str, Any] | None = None

    def get_family_home(self) -> Mapping[str, Any]:
        url = "https://www.spotify.com/api/family/v1/family/home/"
        resp = self.login.client.get(url)


        if resp.fail:
            raise FamilyError("Could not get user plan info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise FamilyError("Invalid JSON")

        return resp.response

    @property
    def members(self) -> List[Mapping[str, Any]]:
        if self._user_family is None:
            self._user_family = self.get_family_home()

        return self._user_family["members"]

    @property
    def enough_space(self) -> bool:
        return len(self.members) < 6
