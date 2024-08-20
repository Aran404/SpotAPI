# Login Class

The `Login` class handles logging in to Spotify, managing sessions, and saving login information.

## Parameters

- **cfg**: `Config`  
  Configuration object.

- **password**: `str`  
  User's password.

- **email**: `Optional[str]`, optional  
  User's email. Defaults to `None`.

- **username**: `Optional[str]`, optional  
  User's username. Defaults to `None`.

  Either an email or username must be provided.

## Methods

### `__init__(self, cfg: Config, password: str, *, email: str | None = None, username: str | None = None) -> None`
Initializes the `Login` class with configuration, password, and either email or username.

### `save(self, saver: SaverProtocol) -> None`
Saves the session with the provided `Saver`.

- **Args:**
  - `saver`: `SaverProtocol`  
    The saver to save the session to.

- **Raises:**  
  `ValueError` if the session is not logged in.

### `from_cookies(cls, dump: Mapping[str, Any], cfg: Config) -> Login`
Constructs a `Login` instance using cookie data and configuration.

- **Args:**
  - `dump`: `Mapping[str, Any]`  
    The session dump.

  - `cfg`: `Config`  
    The configuration object.

- **Returns:**  
  `Login` instance.

- **Raises:**  
  `ValueError` if the dump format is invalid.

### `from_saver(cls, saver: SaverProtocol, cfg: Config, identifier: str, **kwargs) -> Login`
Loads a session from a `Saver` class.

- **Args:**
  - `saver`: `SaverProtocol`  
    The saver to load the session from.

  - `cfg`: `Config`  
    The configuration object.

  - `identifier`: `str`  
    The identifier of the session.

- **Returns:**  
  `Login` instance.

### `logged_in(self) -> bool`
Property indicating whether the user is logged in.

### `__str__(self) -> str`
Returns a string representation of the `Login` instance.

### `login(self) -> None`
Logs the user in, handling captcha if necessary.

- **Raises:**  
  `LoginError` if login fails or captcha cannot be solved.

---

# LoginChallenge Class

The `LoginChallenge` class handles challenges encountered during login, including solving captchas and completing challenge steps.

## Parameters

- **login**: `Login`  
  The `Login` instance.

- **dump**: `Mapping[str, Any]`  
  The challenge data.

## Methods

### `__init__(self, login: Login, dump: Mapping[str, Any]) -> None`
Initializes the `LoginChallenge` class with the `Login` instance and challenge data.

### `defeat(self) -> None`
Defeats the login challenge by performing the necessary steps.

- **Raises:**  
  `LoginError` if unable to get challenge, submit challenge, or complete challenge.