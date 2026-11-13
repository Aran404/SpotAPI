"""Launch the installed application; prefer ``spotapi studio``."""

from spotapi.cli import main

raise SystemExit(main(["studio"]))
