import inspect
import functools
from collections.abc import Iterable, Sequence, Mapping, Generator
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    ParamSpec,
    get_args,
    get_origin,
    Type,
    Union,
)

__all__ = ["enforce_types", "EnforceMeta", "enforce"]

_EnforceType = TypeVar("_EnforceType", bound=type)
R = TypeVar("R")
P = ParamSpec("P")


def enforce_types(func: Callable[P, R]) -> Callable[P, R]:
    """
    Wrapper function to enforce type annotations on a function's arguments and return value.
    """
    type_hints: Dict[str, Any] = func.__annotations__
    return_type: Optional[Any] = type_hints.get("return")

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Get the function's signature
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        for arg_name, arg_value in bound_args.arguments.items():
            if arg_name in type_hints:
                expected_type: Any = type_hints[arg_name]
                if not is_instance_of(arg_value, expected_type):
                    raise TypeError(
                        f"Argument '{arg_name}' must be of type {format_type(expected_type)}, "
                        f"but got {format_type(type(arg_value))}"
                    )

        result: R = func(*args, **kwargs)

        if return_type is not None and not is_instance_of(result, return_type):
            raise TypeError(
                f"Return value must be of type {format_type(return_type)}, "
                f"but got {format_type(type(result))}"
            )

        return result

    return wrapper


def is_instance_of(value: Any, expected_type: Any) -> bool:
    """
    Check if a value is an instance of a given type, considering generics and unions.
    """
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    match origin:
        case None:
            try:
                return isinstance(value, expected_type)
            except:
                # Some type we don't know how to handle
                return True

        case _ if origin is Union:
            return any(is_instance_of(value, t) for t in args)

        case _ if origin is list:
            return isinstance(value, list) and all(
                is_instance_of(item, args[0]) for item in value
            )

        case _ if origin is tuple:
            return (
                isinstance(value, tuple)
                and len(value) == len(args)
                and all(is_instance_of(v, t) for v, t in zip(value, args))
            )

        case _ if origin is dict:
            return isinstance(value, dict) and all(
                is_instance_of(k, args[0]) and is_instance_of(v, args[1])
                for k, v in value.items()
            )

        case _ if origin is Sequence:
            return isinstance(value, (list, tuple))

        case _ if origin is Iterable:
            return isinstance(value, Iterable)

        case _ if origin is Mapping:
            return isinstance(value, Mapping)

        case _ if origin is Generator:
            return isinstance(value, Generator)

        case _:
            return isinstance(value, expected_type)


def format_type(t: Any) -> str:
    """
    Format the type for display in error messages.
    """
    origin = get_origin(t)
    args = get_args(t)

    match origin:
        case _ if origin is Union:
            return f"Union[{', '.join(format_type(arg) for arg in args)}]"

        case _ if origin is list:
            [item_type] = args
            return f"List[{format_type(item_type)}]"

        case _ if origin is tuple:
            return f"Tuple[{', '.join(format_type(arg) for arg in args)}]"

        case _ if origin is dict:
            key_type, value_type = args
            return f"Dict[{format_type(key_type)}, {format_type(value_type)}]"

        case _ if origin is Sequence:
            [item_type] = args
            return f"Sequence[{format_type(item_type)}]"

        case _ if origin is Iterable:
            [item_type] = args
            return f"Iterable[{format_type(item_type)}]"

        case _ if origin is Mapping:
            key_type, value_type = args
            return f"Mapping[{format_type(key_type)}, {format_type(value_type)}]"

        case _ if origin is Generator:
            yield_type, send_type, return_type = args
            return f"Generator[{format_type(yield_type)}, {format_type(send_type)}, {format_type(return_type)}]"

        case _:
            return str(t)


def enforce(cls: _EnforceType) -> _EnforceType:
    """
    Enforces type annotations on all methods of a class.

    This decorator iterates over all attributes of the class `cls` and applies the
    `@enforce_types` decorator to each method. This ensures that type annotations
    on method arguments and return values are enforced at runtime.

    In effect, using `@enforce` on a class is equivalent to applying the `@enforce_types`
    decorator to each individual method of the class manually. The decorator skips
    over properties and any attributes that are not callable or are special methods
    (e.g., those starting with '__').

    Args:
        cls (_EnforceType): The class whose methods will be wrapped with type enforcement.

    Returns:
        _EnforceType: The same class with type enforcement applied to its methods.
    """

    for attr_name in dir(cls):
        attr_value = getattr(cls, attr_name)

        if isinstance(attr_value, property):
            continue

        if callable(attr_value) and not attr_name.startswith("__"):
            wrapped = enforce_types(attr_value)
            setattr(cls, attr_name, wrapped)

    return cls


class EnforceMeta(type):
    """
    Left it here if I need it in future.

    I have came to the conclusion that this is not needed due to its complexity with inheritance.
    """

    def __new__(
        cls: Type[type], name: str, bases: tuple[type, ...], dct: Dict[str, Any]
    ) -> type:
        for attr_name, attr_value in dct.items():
            if callable(attr_value) and not attr_name.startswith("__"):
                dct[attr_name] = enforce_types(attr_value)

        return super().__new__(cls, name, bases, dct)  # type: ignore
