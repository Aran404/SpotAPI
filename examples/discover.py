"""Launch the installed terminal browser: python -m examples.discover QUERY."""

from spotapi.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["discover", *sys.argv[1:]]))
