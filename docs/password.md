# Password Class

The `Password` class handles password recovery for Spotify accounts. It allows users to initiate the password reset process by providing either an email or username and handling the necessary captcha solving.

## Parameters

- **cfg**: `Config`  
  A configuration object containing the solver, client, and logger instances.

- **email**: `Optional[str]`  
  The email address to use for recovery. Defaults to `None`.

- **username**: `Optional[str]`  
  The username to use for recovery. Defaults to `None`.

  **Note:** Either `email` or `username` must be provided.

## Methods

### `__init__(self, cfg: Config, *, email: Optional[str] = None, username: Optional[str] = None) -> None`
Initializes the `Password` class with configuration settings and recovery credentials.

- **Args:**
  - `cfg`: `Config`  
    Configuration object containing the `solver`, `client`, and `logger`.
  - `email`: `Optional[str]`  
    The email address to use for recovery (optional).
  - `username`: `Optional[str]`  
    The username to use for recovery (optional).

- **Raises:**  
  `ValueError` if neither `email` nor `username` is provided.

### `reset(self) -> None`
Performs the complete password reset process, including captcha solving.

- **Raises:**  
  `PasswordError` if the captcha solver is not set, or if solving the captcha or resetting the password fails.