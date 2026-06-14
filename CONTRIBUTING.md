# Contributing to SpotAPI

Thank you for your interest in contributing to SpotAPI! This document covers
everything you need to get set up, the conventions used in v2, and the
tasks that are open for contribution right now.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Quick setup](#quick-setup)
- [Branch layout](#branch-layout)
- [What needs doing](#what-needs-doing)
- [Good first issues](#good-first-issues)
- [Conventions](#conventions)
- [Submitting a pull request](#submitting-a-pull-request)
- [Running tests](#running-tests)
- [Running the linter](#running-the-linter)

---

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Please
read it before participating.

---

## Quick setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/Aran404/SpotAPI
cd SpotAPI

# 2. Check out the active development branch
git checkout async-v2

# 3. Install the package in editable mode with dev extras
pip install -e ".[dev]"
```

Python **3.11 or later** is required. We recommend using
[`pyenv`](https://github.com/pyenv/pyenv) to manage versions.

---

## Branch layout

| Branch | Purpose |
|---|---|
| `main` | Stable v1 releases — do not target PRs here for v2 work |
| `async-v2` | Active v2 development — **target all v2 PRs here** |

---

## What needs doing

The async rewrite is in progress. The public search layer is complete. The 
following items are not exhaustive but represent the next areas to tackle, roughly in priority order:

### High priority

#### Many of these will be coded by me in the coming few days-weeks.

- [ ] **Private playlist management** — `create_playlist`, `add_track`,
      `remove_track`, `edit_playlist`
- [ ] **Player control** — `play`, `pause`, `skip`, `seek`, `set_volume`,
      `set_repeat`, `set_shuffle`
- [ ] **Websocket Handler** - `current_state`, `next_state`, `prev_state`


### Medium priority

- [ ] **async test suite** — `pytest-asyncio` tests for public search,
      `Pool`, `ObjectDict`, `EventDispatcher`, `timed_cache`
- [ ] **Additional search methods** in `public.py` — see
      [good first issues](#good-first-issues) below
- [ ] **User profile** — `get_profile`, `follow_artist`, `follow_user`
- [ ] **MkDocs documentation site** — docstrings already exist, just needs
      the `mkdocs.yml` + `docs/` pages wired up 

### Lower priority

- [ ] **Family plan management** (`Family`) async port
- [ ] **Password reset** (`Password`) async port

---

## Good first issues

These are self-contained additions that follow an established pattern in the
codebase. Each one is approximately 8–12 lines of code.

The existing `search_tracks`, `search_artists`, `search_albums`,
`search_podcasts`, and `search_playlists` methods in `v2/public.py` all follow
this pattern:

```python
@staticmethod
async def search_tracks(query: str, /) -> AsyncGenerator[Sequence[Track]]:
    """Search for tracks matching *query*.

    Parameters
    ----------
    query : str
        Free-text search query.

    Yields
    ------
    Sequence[Track]
        One page of :class:`~spotapi.v2.specialized.data_wrappers.track.Track` results.
    """
    async for page in Public.search(Track, Operations.SEARCH_TRACKS, query):
        yield page
```

The following methods still need implementation following the existing pattern. Each issue identifies the operation enum value 
and the data wrapper type to use. The list below is not exhaustive, and additional methods may need to be implemented.

| GitHub issue | Method to add | `Operations` enum | Return type |
|---|---|---|---|
| [#GFI-1] | `search_users` | `SEARCH_USERS` | Needs a `User` data wrapper |
| [#GFI-2] | `search_audiobooks` | `SEARCH_AUDIOBOOKS` | Needs an `Audiobook` data wrapper |
| [#GFI-3] | `search_episodes` | `SEARCH_EPISODES` | Needs an `Episode` data wrapper |
| [#GFI-4] | `search_top_results` | `SEARCH_TOP_RESULTS` | `ObjectDict` (raw) |

**To contribute one of these:**

1. Create the data wrapper in `v2/specialized/data_wrappers/<type>.py`
   following the existing wrappers as a template. Include `__repr__`.
2. Import it in `v2/specialized/data_wrappers/__init__.py` and add it to
   `__all__`.
3. Add the static method to `Public` in `v2/public.py` with a NumPy-style
   docstring.
4. Add it to `__all__` in `v2/public.py`.
5. Open a PR targeting `async-v2`.

---

## Conventions

### Style

SpotAPI v2 is formatted with **Black** (formatter) and **Pyright** (strict). Run it before
committing:

```bash
black ./
pyright --strict
```

### Type annotations

- All public functions and methods must be fully annotated.
- `from __future__ import annotations` at the top of every file.
- No `Any` in public API signatures unless unavoidable.
- Run `mypy v2/` to verify.

### Docstrings

Use **NumPy-style** docstrings (same as discord.py and NumPy itself):

```python
def my_function(param: str, /, *, flag: bool = False) -> list[str]:
    """One-line summary ending with a period.

    Optional extended description. May span multiple paragraphs.

    Parameters
    ----------
    param : str
        Description of *param*.
    flag : bool
        Description of *flag*. Defaults to ``False``.

    Returns
    -------
    list[str]
        Description of the return value.

    Raises
    ------
    ValueError
        If *param* is empty.

    Examples
    --------
    ::

        result = my_function("hello", flag=True)
    """
```

### `__all__`

Every module must define `__all__` as an explicit `tuple[str, ...]`. Star
imports from modules without `__all__` are not permitted.

### `__repr__`

All public data classes must implement `__repr__`. Use angle-bracket format:

```python
def __repr__(self) -> str:
    return f"<Track id={self.id!r} name={self.name!r}>"
```

### Dataclasses

Use `@dataclass(slots=True)` for all data wrappers. Use `frozen=True` for
immutable value objects (e.g. `ResponseSuccess`, `LogRecord`).

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(public): add search_users method
fix(pool): replace deprecated get_event_loop with get_running_loop
docs(contributing): add good first issue table
refactor(data_wrappers): extract shared color structs to _common.py
```

---

## Submitting a pull request

1. Fork the repo and create a branch off `async-v2`:
   ```bash
   git checkout -b feat/search-users async-v2
   ```
2. Make your changes following the conventions above.
3. Run the linter and tests:
   ```bash
    black ./
    pyright --strict    
   ```
4. Push and open a PR against `async-v2` (not `main`).
5. Fill in the PR template — include a short description of what you changed
   and why, and reference the issue number if applicable.

PRs that do not pass one of: `pyright`, `ruff`, or `mypy` will not be reviewed until
they do.

---