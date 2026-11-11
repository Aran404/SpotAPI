# Contributing

Use Python 3.11 or later and the v2 checkout.

```bash
python -m pip install -e ".[dev,demo]"
python -m pytest -q
python -m pyright
python -m ruff check .
python -m black --check .
```

The root Pyright configuration checks the library, examples and tests in
strict mode. Tests may inspect private members to verify lifecycle behavior.
Format with `python -m black .`; Ruff checks imports and code quality.

Tests run offline by default. For read-only Spotify contract checks:

```bash
python -m pytest --live=read -vv
```

The same command runs public and authenticated reads when `SPOTIFY_COOKIE` is set
in the environment or local `.env`. Use `--live=all` to include explicit playback
changes; it is one mode switch, not a second environment flag.
Live tests depend on Spotify and may fail when upstream contracts change.
Never run mutating checks in ordinary CI. Personal playback checks restore their baseline in `finally`.

Use real Spotify JSON key spelling in fixtures, including `items`. Test
ownership, cancellation, partial payloads, and retry safety when changing
network behavior. Keep optional metadata optional. A new background task
needs an owner, a retained reference, observable failures, and shutdown.

The package uses Hatch and `pyproject.toml` as its packaging source of truth.
Keep `requirements.txt` consistent with the tested wreq pin. Check a wheel
with `python -m pip wheel . --no-deps` when changing packaging.

Benchmark with `python benchmarks/review.py --output benchmarks/local.json`.
Add `--live` for network measurements. Publish raw samples and distinguish
new sessions, warm sessions, disk caches, network latency, and model overhead.
Do not infer network speedups from the offline ownership comparison.

See the [API layout](docs/api-layout.md) for module responsibilities and
ownership. Follow the [code of conduct](CODE_OF_CONDUCT.md).
