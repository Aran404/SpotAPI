# JoinFamily Class

The `JoinFamily` class provides functionality for a user to join a Spotify family plan hosted by another user.

## Parameters

- **user_login**: `Login`  
  The user's login object.

- **host**: `Family`  
  The host user's family object.

- **country**: `str`  
  The country to restrict the autocomplete to.

## Methods

### `__init__(self, user_login: Login, host: "Family", country: str) -> None`
Initializes the `JoinFamily` class with the user's login, host family object, and country.

### `add_to_family(self) -> None`
Adds the user to the host's family plan by retrieving the address and making the necessary API calls.

- **Raises:**  
  `FamilyError` if unable to add the user to the family.

---

# Family Class

The `Family` class provides methods for interacting with Spotify's family plan features.

## Parameters

- **login**: `Login`  
  A logged-in `Login` object.

## Methods

### `__init__(self, login: Login) -> None`
Initializes the `Family` class with the provided `Login` object. Raises a `ValueError` if the user does not have a premium subscription.

### `get_family_home(self) -> Mapping[str, Any]`
Retrieves the family home information for the user.

- **Returns:**  
  A mapping of the family home information.

- **Raises:**  
  `FamilyError` if unable to get user plan info or if the response is not valid JSON.

### `members(self) -> List[Mapping[str, Any]]`
Gets the list of family members.

- **Returns:**  
  A list of mappings, each representing a family member.

### `enough_space(self) -> bool`
Checks if there is enough space in the family plan.

- **Returns:**  
  `True` if there are fewer than 6 members in the family plan, otherwise `False`.