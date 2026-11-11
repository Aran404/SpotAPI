"""Structured logging utilities and logger protocols."""

from __future__ import annotations

import inspect
import json as _json
import logging
import sys
import threading
import time
import traceback
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
from types import TracebackType
from typing import (
    Any,
    ClassVar,
    Final,
    Generic,
    Never,
    ParamSpec,
    Protocol,
    Self,
    TypeAlias,
    TypeVar,
    cast,
    runtime_checkable,
)

__all__ = (
    "LoggerProtocol",
    "LoggerColour",
    "JsonLogger",
    "MultiLogger",
    "NoopLogger",
    "InbuiltLogger",
    "StandardLogger",
    "LoggerMixin",
    "Level",
)

P = ParamSpec("P")
R = TypeVar("R")
ExcT = TypeVar("ExcT", bound=BaseException)
LoggerT = TypeVar("LoggerT", bound="LoggerProtocol")

ExtraFields: TypeAlias = dict[str, Any]
LogCallable: TypeAlias = Callable[..., None]


class Level(StrEnum):
    """Logging severity levels, comparable by numeric value."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """Return the standard numeric logging level."""
        return logging.getLevelNamesMapping()[self.value]

    def __lt__(self, other: str) -> bool:
        """Compare logging levels by their numeric severity."""
        return self.numeric < Level(other).numeric

    def __le__(self, other: str) -> bool:
        """Compare logging levels by their numeric severity."""
        return self.numeric <= Level(other).numeric

    def __gt__(self, other: str) -> bool:
        """Compare logging levels by their numeric severity."""
        return self.numeric > Level(other).numeric

    def __ge__(self, other: str) -> bool:
        """Compare logging levels by their numeric severity."""
        return self.numeric >= Level(other).numeric


@dataclass(frozen=True, slots=True)
class LogRecord:
    """An immutable snapshot of a single log event."""

    level: Level
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    logger_name: str = "root"
    extra: ExtraFields = field(default_factory=dict[str, Any])
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | None = None

    def with_extra(self, **kwargs: Any) -> LogRecord:
        """Return a new :class:`LogRecord` with additional extra fields merged in."""
        return LogRecord(
            level=self.level,
            message=self.message,
            timestamp=self.timestamp,
            logger_name=self.logger_name,
            extra={**self.extra, **kwargs},
            exc_info=self.exc_info,
        )

    @property
    def iso_timestamp(self) -> str:
        """Format the record timestamp with millisecond precision."""
        return self.timestamp.isoformat(timespec="milliseconds")


@runtime_checkable
class LoggerProtocol(Protocol):
    """Structural protocol satisfied by all SpotAPI loggers.

    Any object implementing these methods is accepted wherever a
    :class:`LoggerProtocol` is expected, including third-party loggers.
    """

    def debug(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a debug-level record when enabled."""
        ...

    def info(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit an informational record when enabled."""
        ...

    def warning(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a warning record when enabled."""
        ...

    def error(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit an error record with optional exception context."""
        ...

    def critical(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a critical record with optional exception context."""
        ...

    def log(
        self,
        level: Level,
        message: str,
        /,
        *args: object,
        **extra: Any,
    ) -> None:
        """Emit a record at the supplied level with structured context."""
        ...

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        ...

    def is_enabled(self, level: Level) -> bool:
        """Check whether this logger accepts the requested level."""
        ...


class _MissingLogger:
    def __getattr__(self, name: str) -> Never:
        """Raise an explicit configuration error when no logger was injected."""
        raise RuntimeError("No logger was injected. Pass a concrete logger or NoopLogger().")


MISSING: Final[_MissingLogger] = _MissingLogger()


class _BaseLogger:
    __slots__ = (
        "_name",
        "_min_level",
        "_context",
        "_lock",
    )

    def __init__(
        self,
        name: str = "root",
        min_level: Level = Level.DEBUG,
        context: ExtraFields | None = None,
        thread_safe: bool = True,
    ) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        self._name: str = name
        self._min_level: Level = min_level
        self._context: ExtraFields = context or {}
        self._lock: threading.Lock | None = threading.Lock() if thread_safe else None

    def _emit(self, record: LogRecord) -> None:  # pragma: no cover
        """Write one prepared record through this logger's configured sink."""
        raise NotImplementedError

    def _build_record(
        self,
        level: Level,
        message: str,
        args: tuple[object, ...],
        extra: ExtraFields,
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | None = None,
    ) -> LogRecord:
        """Build a timestamped record and merge bound and per-call context."""
        msg = message % args if args else message
        merged = {**self._context, **extra}

        return LogRecord(
            level=level,
            message=msg,
            logger_name=self._name,
            extra=merged,
            exc_info=exc_info,
        )

    def log(
        self,
        level: Level,
        message: str,
        /,
        *args: Any,
        **extra: Any,
    ) -> None:
        """Emit a record at the supplied level with structured context."""
        if not self.is_enabled(level):
            return

        with self._lock if self._lock is not None else nullcontext():
            self._emit(self._build_record(level, message, args, extra))

    def debug(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a debug-level record when enabled."""
        self.log(Level.DEBUG, message, *args, **extra)

    def info(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit an informational record when enabled."""
        self.log(Level.INFO, message, *args, **extra)

    def warning(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a warning record when enabled."""
        self.log(Level.WARNING, message, *args, **extra)

    def error(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit an error record with optional exception context."""
        self.log(Level.ERROR, message, *args, **extra)

    def critical(self, message: str, /, *args: object, **extra: Any) -> None:
        """Emit a critical record with optional exception context."""
        self.log(Level.CRITICAL, message, *args, **extra)

    def is_enabled(self, level: Level) -> bool:
        """Check whether this logger accepts the requested level."""
        return level >= self._min_level

    def bind(self, **context: Any) -> Self:
        """Return a child logger with additional bound context fields."""
        clone = self.__class__.__new__(self.__class__)
        clone._name = self._name
        clone._min_level = self._min_level
        clone._context = {**self._context, **context}
        clone._lock = self._lock

        return clone

    @contextmanager
    def timed(self, operation: str) -> Generator[None, None, None]:
        """Emit a ``DEBUG`` record with elapsed milliseconds after the block exits.

        Example:
            >>> with logger.timed("bundle fetch"):
            ...     bundles = await session.load()
        """
        start = time.perf_counter()

        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1_000

            self.debug("%s completed in %.2f ms", operation, elapsed_ms)

    @contextmanager
    def catch(
        self,
        *exc_types: type[ExcT],
        level: Level = Level.ERROR,
        reraise: bool = True,
    ) -> Generator[None, None, None]:
        """Log any matching exception, then optionally re-raise it.

        Args:
            *exc_types: Exception types to catch.
            level: Severity of the emitted record.
            reraise: Re-raise the exception after logging when true.
        """
        try:
            yield
        except exc_types as exc:
            record = self._build_record(
                level,
                str(exc),
                (),
                {},
                exc_info=(type(exc), exc, exc.__traceback__),
            )

            self._emit(record)

            if reraise:
                raise


class _ANSI:
    RESET: Final = "\033[0m"
    BOLD: Final = "\033[1m"
    DIM: Final = "\033[2m"
    ITALIC: Final = "\033[3m"

    BLACK: Final = "\033[30m"
    RED: Final = "\033[31m"
    GREEN: Final = "\033[32m"
    YELLOW: Final = "\033[33m"
    BLUE: Final = "\033[34m"
    MAGENTA: Final = "\033[35m"
    CYAN: Final = "\033[36m"
    WHITE: Final = "\033[37m"

    BRIGHT_RED: Final = "\033[91m"
    BRIGHT_GREEN: Final = "\033[92m"
    BRIGHT_YELLOW: Final = "\033[93m"
    BRIGHT_BLUE: Final = "\033[94m"
    BRIGHT_MAGENTA: Final = "\033[95m"
    BRIGHT_CYAN: Final = "\033[96m"
    BRIGHT_WHITE: Final = "\033[97m"

    BG_RED: Final = "\033[41m"
    BG_YELLOW: Final = "\033[43m"
    BG_BLUE: Final = "\033[44m"

    @staticmethod
    def wrap(text: str, *codes: str) -> str:
        """Wrap text in ANSI escape sequences and terminate with a reset."""
        return "".join(codes) + text + _ANSI.RESET

    @staticmethod
    def supports_colour(stream: object = sys.stderr) -> bool:
        """Check whether the configured output supports terminal colours."""
        isatty = getattr(stream, "isatty", None)

        return callable(isatty) and bool(isatty())


@dataclass(frozen=True, slots=True)
class _LevelStyle:
    label: str
    label_colour: str
    msg_colour: str


_LEVEL_STYLES: Final[dict[Level, _LevelStyle]] = {
    Level.DEBUG: _LevelStyle(
        label="  DEBUG ",
        label_colour=_ANSI.DIM + _ANSI.CYAN,
        msg_colour=_ANSI.DIM,
    ),
    Level.INFO: _LevelStyle(
        label="  INFO  ",
        label_colour=_ANSI.BRIGHT_GREEN,
        msg_colour=_ANSI.BRIGHT_WHITE,
    ),
    Level.WARNING: _LevelStyle(
        label=" WARNING",
        label_colour=_ANSI.BRIGHT_YELLOW + _ANSI.BOLD,
        msg_colour=_ANSI.BRIGHT_YELLOW,
    ),
    Level.ERROR: _LevelStyle(
        label="  ERROR ",
        label_colour=_ANSI.BRIGHT_RED + _ANSI.BOLD,
        msg_colour=_ANSI.BRIGHT_RED,
    ),
    Level.CRITICAL: _LevelStyle(
        label="CRITICAL",
        label_colour=_ANSI.BG_RED + _ANSI.BRIGHT_WHITE + _ANSI.BOLD,
        msg_colour=_ANSI.BRIGHT_RED + _ANSI.BOLD,
    ),
}


class LoggerColour(_BaseLogger):
    """A pretty-printed, ANSI-coloured logger that writes to *stderr*.

    Falls back to plain text automatically when the output stream does not
    support colour (e.g. in CI environments or when piped to a file).

    Args:
        name: Logger name shown in every record. Defaults to ``"root"``.
        thread_safe: Protect ``_emit`` with a threading lock. Defaults to ``True``.
        min_level: Records below this level are silently discarded.
        stream: Output stream. Defaults to ``sys.stderr``.
        force_colour: Override auto-detection for ANSI output.
        context: Default extra fields merged into every record.
    """

    __slots__ = (
        "_stream",
        "_colour",
    )

    _separator: ClassVar[str] = " │ "

    def __init__(
        self,
        name: str = "root",
        thread_safe: bool = True,
        min_level: Level = Level.DEBUG,
        stream: Any = sys.stderr,
        force_colour: bool | None = None,
        context: ExtraFields | None = None,
    ) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)

        self._stream = stream
        self._colour: bool = (
            force_colour if force_colour is not None else _ANSI.supports_colour(stream)
        )

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        clone: Self = super().bind(**context)
        clone._stream = self._stream
        clone._colour = self._colour

        return clone

    def _format_extra(self, extra: ExtraFields) -> str:
        """Format structured fields for the human-readable output."""
        if not extra:
            return ""

        pairs = "  ".join(
            (
                f"{_ANSI.wrap(k, _ANSI.DIM + _ANSI.CYAN)}="
                f"{_ANSI.wrap(repr(v), _ANSI.BRIGHT_MAGENTA)}"
                if self._colour
                else f"{k}={v!r}"
            )
            for k, v in extra.items()
        )

        return f"  {pairs}"

    def _format_record(self, record: LogRecord) -> str:
        """Render one record using the configured text format."""
        style = _LEVEL_STYLES[record.level]
        sep = self._separator

        if self._colour:
            ts = _ANSI.wrap(record.iso_timestamp, _ANSI.DIM)
            label = _ANSI.wrap(style.label, style.label_colour)
            name = _ANSI.wrap(f"{record.logger_name:<10}", _ANSI.BOLD + _ANSI.BLUE)
            msg = _ANSI.wrap(record.message, style.msg_colour)
        else:
            ts = record.iso_timestamp
            label = style.label
            name = f"{record.logger_name:<10}"
            msg = record.message

        extra_str = self._format_extra(record.extra)
        line = f"{ts}{sep}{label}{sep}{name}{sep}{msg}{extra_str}"

        if record.exc_info is not None:
            tb = "".join(traceback.format_exception(*record.exc_info))

            if self._colour:
                tb = _ANSI.wrap(tb, _ANSI.RED)

            line = f"{line}\n{tb.rstrip()}"

        return line

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        print(self._format_record(record), file=self._stream)


class StandardLogger(_BaseLogger):
    """Plain-text logger writing to *stdout*.

    Args:
        name: Logger name. Defaults to ``"root"``.
        thread_safe: Protect ``_emit`` with a threading lock.
        min_level: Minimum level for records to be emitted.
        stream: Output stream. Defaults to ``sys.stdout``.
        context: Default extra fields merged into every record.
    """

    __slots__ = ("_stream",)

    def __init__(
        self,
        name: str = "root",
        thread_safe: bool = True,
        min_level: Level = Level.DEBUG,
        stream: Any = sys.stdout,
        context: ExtraFields | None = None,
    ) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)

        self._stream = stream

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        clone: Self = super().bind(**context)
        clone._stream = self._stream

        return clone

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        extra_str = (
            "  " + "  ".join(f"{k}={v!r}" for k, v in record.extra.items()) if record.extra else ""
        )
        line = (
            f"[{record.iso_timestamp}]"
            f" [{record.level.value:<8}]"
            f" [{record.logger_name:<12}]"
            f" {record.message}"
            f"{extra_str}"
        )

        if record.exc_info is not None:
            tb = "".join(traceback.format_exception(*record.exc_info))
            line = f"{line}\n{tb.rstrip()}"

        print(line, file=self._stream)


class NoopLogger(_BaseLogger):
    """A no-op logger that discards all records.

    Pass this when you want to silence SpotAPI's internal logging entirely.
    """

    __slots__ = ()

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        pass

    def is_enabled(self, level: Level) -> bool:
        """Check whether this logger accepts the requested level."""
        return False


class InbuiltLogger(_BaseLogger):
    """Adapter that bridges SpotAPI's logging to the stdlib :mod:`logging` module.

    Args:
        logger: Stdlib logger to receive records. Defaults to a new logger
            named after ``name``.
        thread_safe: Protect ``_emit`` with a threading lock.
        name: Used when creating a default stdlib logger.
        context: Default extra fields merged into every record.
    """

    __slots__ = ("_logger",)

    _STDLIB_LEVEL: ClassVar[dict[Level, int]] = {
        Level.DEBUG: logging.DEBUG,
        Level.INFO: logging.INFO,
        Level.WARNING: logging.WARNING,
        Level.ERROR: logging.ERROR,
        Level.CRITICAL: logging.CRITICAL,
    }

    def __init__(
        self,
        logger: logging.Logger | None = None,
        thread_safe: bool = True,
        name: str = "root",
        context: ExtraFields | None = None,
    ) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        super().__init__(name=name, context=context, thread_safe=thread_safe)

        self._logger: logging.Logger = logger or logging.getLogger(name)

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        clone: Self = super().bind(**context)
        clone._logger = self._logger

        return clone

    def is_enabled(self, level: Level) -> bool:
        """Check whether this logger accepts the requested level."""
        return self._logger.isEnabledFor(self._STDLIB_LEVEL[level])

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        stdlib_level = self._STDLIB_LEVEL[record.level]

        self._logger.log(
            stdlib_level,
            record.message,
            exc_info=record.exc_info,
            extra={"_ctx": record.extra},
            stacklevel=6,
        )


class JsonLogger(_BaseLogger):
    """Structured JSON logger — one JSON object per line.

    Ideal for log aggregation pipelines (Datadog, Loki, CloudWatch, etc.).

    Args:
        name: Logger name. Defaults to ``"root"``.
        thread_safe: Protect ``_emit`` with a threading lock.
        min_level: Minimum level for records to be emitted.
        stream: Output stream. Defaults to ``sys.stdout``.
        context: Default extra fields merged into every record.
        indent: JSON indentation, or ``None`` for compact output.
    """

    __slots__ = (
        "_stream",
        "_indent",
    )

    def __init__(
        self,
        name: str = "root",
        thread_safe: bool = True,
        min_level: Level = Level.DEBUG,
        stream: Any = sys.stdout,
        context: ExtraFields | None = None,
        indent: int | None = None,
    ) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)

        self._stream = stream
        self._indent = indent

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        clone: Self = super().bind(**context)
        clone._stream = self._stream
        clone._indent = self._indent

        return clone

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        payload: dict[str, Any] = {
            "ts": record.iso_timestamp,
            "level": record.level.value,
            "logger": record.logger_name,
            "msg": record.message,
            **record.extra,
        }

        if record.exc_info is not None:
            payload["traceback"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()

        print(_json.dumps(payload, indent=self._indent, default=str), file=self._stream)


class MultiLogger(_BaseLogger):
    """Fan-out logger that forwards every record to multiple child loggers.

    Args:
        *loggers: Loggers to receive every emitted record. The effective
            level is the lowest minimum level among the children.

    Example:

        logger = MultiLogger(
            LoggerColour(min_level=Level.DEBUG),
            JsonLogger(min_level=Level.WARNING, stream=open("errors.jsonl", "a")),
        )
    """

    __slots__ = ("_children",)

    def __init__(self, *loggers: _BaseLogger) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        combined_min = min((lg._min_level for lg in loggers), default=Level.DEBUG)

        super().__init__(min_level=combined_min)

        self._children: tuple[_BaseLogger, ...] = loggers

    def _emit(self, record: LogRecord) -> None:
        """Write one prepared record through this logger's configured sink."""
        for child in self._children:
            if child.is_enabled(record.level):
                child_record = (
                    replace(record, extra={**child._context, **record.extra})
                    if child._context
                    else record
                )

                child._emit(child_record)

    def bind(self, **context: Any) -> Self:
        """Return a logger carrying additional structured context."""
        clone = super().bind(**context)
        clone._children = self._children

        return clone


def log_calls(
    logger: LoggerProtocol,
    *,
    level: Level = Level.DEBUG,
    log_args: bool = True,
    log_result: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log calls to a synchronous or asynchronous function.

    Async results are logged after awaiting; raised exceptions and task
    cancellation propagate unchanged.

    Args:
        logger: Destination logger.
        level: Severity of the emitted records.
        log_args: Include arguments in the call record.
        log_result: Include the returned result in a second record.

    Returns:
        A decorator preserving the callable's public signature.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        """Wrap a callable with the configured entry, completion and failure logging."""

        def before(args: tuple[object, ...], kwargs: dict[str, object]) -> None:
            """Log the callable's invocation before execution."""
            if log_args:
                logger.log(
                    level,
                    "Calling %s",
                    fn.__qualname__,
                    args=repr(args),
                    kwargs=repr(kwargs),
                )
            else:
                logger.log(level, "Calling %s", fn.__qualname__)

        def after(result: object) -> None:
            """Log completion or failure without changing the callable's result."""
            if log_result:
                logger.log(level, "%s returned %r", fn.__qualname__, result)

        if inspect.iscoroutinefunction(fn):
            async_fn = cast(Callable[P, Awaitable[object]], fn)

            @wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
                """Await a callable with the configured logging hooks."""
                before(args, kwargs)

                result = await async_fn(*args, **kwargs)

                after(result)

                return result

            return cast(Callable[P, R], async_wrapper)

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Run a synchronous callable with the configured logging hooks."""
            before(args, kwargs)

            result = fn(*args, **kwargs)

            after(result)

            return result

        return wrapper

    return decorator


class LoggerMixin(Generic[LoggerT]):
    """Base mixin for service classes that own a :class:`LoggerProtocol` instance.

    Args:
        logger: The logger instance this service will use.
    """

    def __init__(self, logger: LoggerT) -> None:
        """Configure the logger's explicit sinks, level and structured context."""
        self.logger: LoggerT = logger
