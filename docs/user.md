# User Class

The `User` class represents a Spotify user and provides methods for retrieving and editing user information.

## Parameters

- **login**: `Login`  
  The `Login` instance for the user. The user must be logged in for this class to function.

## Methods

### `__init__(self, login: Login) -> None`
Initializes the `User` class with a `Login` instance.

- **Raises:**  
  `ValueError` if the user is not logged in.

### `has_premium(self) -> bool`
Property indicating whether the user has a premium subscription.

- **Returns:**  
  `bool`  
  `True` if the user has a premium subscription, otherwise `False`.

### `username(self) -> str`
Property that returns the username of the user.

- **Returns:**  
  `str`  
  The user's username.

### `get_plan_info(self) -> Mapping[str, Any]`
Retrieves the user's plan information.

- **Returns:**  
  `Mapping[str, Any]`  
  A dictionary containing the user's plan information.

- **Raises:**  
  `UserError` if there is an issue retrieving the plan information or if the response is not in the expected format.

### `verify_login(self) -> bool`
Verifies whether the user is logged in by attempting to retrieve the plan information.

- **Returns:**  
  `bool`  
  `True` if the login is verified, otherwise `False`.

### `get_user_info(self) -> Mapping[str, Any]`
Retrieves the user's account information.

- **Returns:**  
  `Mapping[str, Any]`  
  A dictionary containing the user's account information.

- **Raises:**  
  `UserError` if there is an issue retrieving the user information or if the response is not in the expected format.

### `edit_user_info(self, dump: Mapping[str, Any]) -> None`
Edits the user's account information.

- **Args:**
  - `dump`: `Mapping[str, Any]`  
    The profile dump containing user information. This should include the entire profile dump retrieved from `get_user_info`.

- **Raises:**  
  `UserError` if there is an issue solving the captcha or editing the user information.
