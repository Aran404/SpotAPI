# Creator Class

The `Creator` class is responsible for creating new Spotify accounts.

## Parameters

- **cfg**: `Config`  
  The configuration object.

- **email**: `str`, optional  
  The email address to use for the account. Defaults to a randomly generated email.

- **display_name**: `str`, optional  
  The display name to use for the account. Defaults to a randomly generated string.

- **password**: `str`, optional  
  The password to use for the account. Defaults to a randomly generated string.

## Methods

### `__init__(self, cfg: Config, email: str = random_email(), display_name: str = random_string(10), password: str = random_string(10, True)) -> None`
Initializes the `Creator` class with the given configuration and optional parameters for email, display name, and password.

### `register(self) -> None`
Registers a new Spotify account by solving a CAPTCHA and processing the registration.

- **Raises:**  
  `GeneratorError` if no CAPTCHA solver is set.

---

# AccountChallenge Class

The `AccountChallenge` class handles challenges encountered during account creation.

## Parameters

- **client**: `TLSClient`  
  The client used for making requests to the API.

- **raw_response**: `str`  
  The raw response containing challenge details.

- **cfg**: `Config`  
  The configuration object.

## Methods

### `__init__(self, client: TLSClient, raw_response: str, cfg: Config) -> None`
Initializes the `AccountChallenge` class with the client, raw response, and configuration.

### `defeat_challenge(self) -> None`
Solves and defeats the challenge, completing the account creation process.

- **Raises:**  
  `GeneratorError` if no CAPTCHA solver is set.