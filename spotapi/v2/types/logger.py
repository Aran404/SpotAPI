from __future__ import annotations

import json as _json
import logging
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Final,
    Generator,
    Generic,
    Never,
    ParamSpec,
    TypeAlias,
    Protocol,
    Self,
    TypeVar,
    runtime_checkable,
)

if TYPE_CHECKING:
    from types import TracebackType

__all__: tuple[str, ...] = (
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
        return logging.getLevelName(self.value)  # type: ignore[return-value]

    def __lt__(self, other: Level) -> bool:  # type: ignore[override]
        return self.numeric < other.numeric

    def __le__(self, other: Level) -> bool:  # type: ignore[override]
        return self.numeric <= other.numeric

    def __gt__(self, other: Level) -> bool:  # type: ignore[override]
        return self.numeric > other.numeric

    def __ge__(self, other: Level) -> bool:  # type: ignore[override]
        return self.numeric >= other.numeric


@dataclass(frozen=True, slots=True)
class LogRecord:
    """An immutable snapshot of a single log event."""

    level: Level
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    logger_name: str = "root"
    extra: ExtraFields = field(default_factory=dict)  # type: ignore[reportUnknownArgumentType]
    exc_info: tuple[type[BaseException], BaseException, "TracebackType"] | None = None

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
        return self.timestamp.isoformat(timespec="milliseconds")


@runtime_checkable
class LoggerProtocol(Protocol):
    """Structural protocol satisfied by all SpotAPI loggers.

    Any object implementing these methods is accepted wherever a
    :class:`LoggerProtocol` is expected, including third-party loggers.
    """

    def debug(self, message: str, /, *args: object, **extra: Any) -> None: ...
    def info(self, message: str, /, *args: object, **extra: Any) -> None: ...
    def warning(self, message: str, /, *args: object, **extra: Any) -> None: ...
    def error(self, message: str, /, *args: object, **extra: Any) -> None: ...
    def critical(self, message: str, /, *args: object, **extra: Any) -> None: ...

    def log(
        self,
        level: Level,
        message: str,
        /,
        *args: object,
        **extra: Any,
    ) -> None: ...

    def bind(self, **context: Any) -> Self: ...
    def is_enabled(self, level: Level) -> bool: ...


class _MissingLogger:
    def __getattr__(self, name: str) -> Never:
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
        self._name: str = name
        self._min_level: Level = min_level
        self._context: ExtraFields = context or {}
        self._lock: threading.Lock | None = threading.Lock() if thread_safe else None

    def _emit(self, record: LogRecord) -> None:  # pragma: no cover
        raise NotImplementedError

    def _build_record(
        self,
        level: Level,
        message: str,
        args: tuple[object, ...],
        extra: ExtraFields,
        exc_info: tuple[type[BaseException], BaseException, "TracebackType"] | None = None,
    ) -> LogRecord:
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
        # FIX: use the lock as a context manager so it is always released,
        # even when is_enabled() returns False early or _emit() raises.
        with self._lock if self._lock is not None else _nullcontext():
            if not self.is_enabled(level):
                return

            if extra:
                extra = {
                    k: (v[:50] if hasattr(v, "__len__") and len(v) > 50 else v)
                    for k, v in extra.items()
                }

            if args:
                args = tuple(v[:50] if hasattr(v, "__len__") and len(v) > 50 else v for v in args)

            record = self._build_record(level, message, args, extra)
            self._emit(record)

    def debug(self, message: str, /, *args: object, **extra: Any) -> None:
        self.log(Level.DEBUG, message, *args, **extra)

    def info(self, message: str, /, *args: object, **extra: Any) -> None:
        self.log(Level.INFO, message, *args, **extra)

    def warning(self, message: str, /, *args: object, **extra: Any) -> None:
        self.log(Level.WARNING, message, *args, **extra)

    def error(self, message: str, /, *args: object, **extra: Any) -> None:
        self.log(Level.ERROR, message, *args, **extra)

    def critical(self, message: str, /, *args: object, **extra: Any) -> None:
        self.log(Level.CRITICAL, message, *args, **extra)

    def is_enabled(self, level: Level) -> bool:
        return level >= self._min_level

    def bind(self, **context: Any) -> Self:
        """Return a child logger with additional bound context fields."""
        clone = self.__class__.__new__(self.__class__)
        clone._name = self._name
        clone._min_level = self._min_level
        clone._context = {**self._context, **context}
        clone._lock = self._lock
        return clone  # type: ignore[return-value]

    @contextmanager
    def timed(self, operation: str) -> Generator[None, None, None]:
        """Emit a ``DEBUG`` record with elapsed milliseconds after the block exits.

        Examples
        --------
        ::

            with logger.timed("bundle fetch"):
                bundles = await session.load()
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

        Parameters
        ----------
        *exc_types : type[BaseException]
            Exception types to catch.
        level : Level
            Severity used when emitting the record. Defaults to ``ERROR``.
        reraise : bool
            If ``True`` (the default) the exception is re-raised after logging.
        """
        try:
            yield
        except exc_types as exc:  # type: ignore[misc]
            ei = sys.exc_info()
            record = self._build_record(
                level,
                str(exc),
                (),
                {},
                exc_info=ei,  # type: ignore[arg-type]
            )
            self._emit(record)
            if reraise:
                raise


# ---------------------------------------------------------------------------
# Inline null-context so we can use `with _nullcontext()` on Python < 3.10
# without importing contextlib.nullcontext (which exists but avoids an extra
# import for a trivial utility).
# ---------------------------------------------------------------------------
from contextlib import nullcontext as _nullcontext  # noqa: E402


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
        return "".join(codes) + text + _ANSI.RESET

    @staticmethod
    def supports_colour(stream: object = sys.stderr) -> bool:
        return hasattr(stream, "isatty") and stream.isatty()  # type: ignore[union-attr]


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

    Parameters
    ----------
    name : str
        Logger name shown in every record. Defaults to ``"root"``.
    thread_safe : bool
        Protect ``_emit`` with a threading lock. Defaults to ``True``.
    min_level : Level
        Records below this level are silently discarded.
    stream : file-like
        Output stream. Defaults to ``sys.stderr``.
    force_colour : bool, optional
        Override auto-detection. ``True`` always enables colour,
        ``False`` always disables it.
    context : dict, optional
        Default extra fields merged into every record.
    """

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
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)
        self._stream = stream
        self._colour: bool = (
            force_colour if force_colour is not None else _ANSI.supports_colour(stream)
        )

    def bind(self, **context: Any) -> Self:
        clone: Self = super().bind(**context)
        clone._stream = self._stream
        clone._colour = self._colour
        return clone

    def _format_extra(self, extra: ExtraFields) -> str:
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
        print(self._format_record(record), file=self._stream)


class StandardLogger(_BaseLogger):
    """Plain-text logger writing to *stdout*.

    Parameters
    ----------
    name : str
        Logger name. Defaults to ``"root"``.
    thread_safe : bool
        Protect ``_emit`` with a threading lock.
    min_level : Level
        Minimum level for records to be emitted.
    stream : file-like
        Output stream. Defaults to ``sys.stdout``.
    context : dict, optional
        Default extra fields merged into every record.
    """

    def __init__(
        self,
        name: str = "root",
        thread_safe: bool = True,
        min_level: Level = Level.DEBUG,
        stream: Any = sys.stdout,
        context: ExtraFields | None = None,
    ) -> None:
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)
        self._stream = stream

    def bind(self, **context: Any) -> Self:
        clone: Self = super().bind(**context)
        clone._stream = self._stream
        return clone

    def _emit(self, record: LogRecord) -> None:
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

    def _emit(self, record: LogRecord) -> None:
        pass

    def is_enabled(self, level: Level) -> bool:
        return False


class InbuiltLogger(_BaseLogger):
    """Adapter that bridges SpotAPI's logging to the stdlib :mod:`logging` module.

    Parameters
    ----------
    logger : logging.Logger, optional
        The stdlib logger to forward records to. If omitted a new logger
        named *name* is created.
    thread_safe : bool
        Protect ``_emit`` with a threading lock.
    name : str
        Used when creating a default stdlib logger.
    context : dict, optional
        Default extra fields merged into every record.
    """

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
        super().__init__(name=name, context=context, thread_safe=thread_safe)
        self._logger: logging.Logger = logger or logging.getLogger(name)

    def bind(self, **context: Any) -> Self:
        clone: Self = super().bind(**context)
        clone._logger = self._logger
        return clone

    def is_enabled(self, level: Level) -> bool:
        return self._logger.isEnabledFor(self._STDLIB_LEVEL[level])

    def _emit(self, record: LogRecord) -> None:
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

    Parameters
    ----------
    name : str
        Logger name. Defaults to ``"root"``.
    thread_safe : bool
        Protect ``_emit`` with a threading lock.
    min_level : Level
        Minimum level for records to be emitted.
    stream : file-like
        Output stream. Defaults to ``sys.stdout``.
    context : dict, optional
        Default extra fields merged into every record.
    indent : int, optional
        JSON indentation. ``None`` (default) produces compact single-line output.
    """

    def __init__(
        self,
        name: str = "root",
        thread_safe: bool = True,
        min_level: Level = Level.DEBUG,
        stream: Any = sys.stdout,
        context: ExtraFields | None = None,
        indent: int | None = None,
    ) -> None:
        super().__init__(name=name, min_level=min_level, context=context, thread_safe=thread_safe)
        self._stream = stream
        self._indent = indent

    def bind(self, **context: Any) -> Self:
        clone: Self = super().bind(**context)
        clone._stream = self._stream
        clone._indent = self._indent
        return clone

    def _emit(self, record: LogRecord) -> None:
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

    Parameters
    ----------
    *loggers : _BaseLogger
        One or more loggers to receive every emitted record. The effective
        minimum level is the lowest ``min_level`` across all children.

    Examples
    --------
    ::

        logger = MultiLogger(
            LoggerColour(min_level=Level.DEBUG),
            JsonLogger(min_level=Level.WARNING, stream=open("errors.jsonl", "a")),
        )
    """

    def __init__(self, *loggers: _BaseLogger) -> None:
        combined_min = min((lg._min_level for lg in loggers), default=Level.DEBUG)
        super().__init__(min_level=combined_min)
        self._children: tuple[_BaseLogger, ...] = loggers

    def _emit(self, record: LogRecord) -> None:
        for child in self._children:
            if child.is_enabled(record.level):
                child._emit(record)

    def bind(self, **context: Any) -> Self:
        bound_children = tuple(child.bind(**context) for child in self._children)
        clone = self.__class__(*bound_children)  # type: ignore[return-value]
        return clone  # type: ignore[return-value]


def log_calls(
    logger: LoggerProtocol,
    *,
    level: Level = Level.DEBUG,
    log_args: bool = True,
    log_result: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that emits a log record on every call to the wrapped function.

    Parameters
    ----------
    logger : LoggerProtocol
        The logger to emit to.
    level : Level
        Severity of each record. Defaults to ``DEBUG``.
    log_args : bool
        Include ``args`` and ``kwargs`` in the record. Defaults to ``True``.
    log_result : bool
        Include the return value in a second record. Defaults to ``False``.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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

            result = fn(*args, **kwargs)

            if log_result:
                logger.log(
                    level,
                    "%s returned %r",
                    fn.__qualname__,
                    result,
                )
            return result

        return wrapper

    return decorator


class LoggerMixin(Generic[LoggerT]):
    """Base mixin for service classes that own a :class:`LoggerProtocol` instance.

    Parameters
    ----------
    logger : LoggerProtocol
        The logger instance this service will use.
    """

    def __init__(self, logger: LoggerT) -> None:
        self.logger: LoggerT = logger
