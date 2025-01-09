# type: ignore
from spotapi.types.annotations import enforce

import pytest
from typing import List, Dict, Tuple, Sequence, Iterable, Mapping, Generator


@enforce
class _TCLASS:
    def test_int(self, _: int) -> None:
        pass

    def test_str(self, _: str) -> None:
        pass

    def test_list(self, _: List[int]) -> None:
        pass

    def test_tuple(self, _: Tuple[int, str]) -> None:
        pass

    def test_dict(self, _: Dict[str, int]) -> None:
        pass

    def test_sequence(self, _: Sequence[int]) -> None:
        pass

    def test_iterable(self, _: Iterable[int]) -> None:
        pass

    def test_mapping(self, _: Mapping[str, int]) -> None:
        pass

    def test_generator(self, _: Generator[int, None, None]) -> None:
        pass

    def test_int_or_str(self, _: int | str) -> None:
        pass

    def test_list_or_none(self, _: List[int] | None) -> None:
        pass

    def test_dict_or_empty(self, _: Dict[str, int] | None) -> None:
        pass

    def test_tuple_or_none(self, _: Tuple[int, str] | None) -> None:
        pass

    def test_sequence_or_generator(
        self, _: Sequence[int] | Generator[int, None, None]
    ) -> None:
        pass


def test_int_pass():
    instance = _TCLASS()
    instance.test_int(10)


def test_int_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_int("string")


def test_str_pass():
    instance = _TCLASS()
    instance.test_str("hello")


def test_str_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_str(123)


def test_list_pass():
    instance = _TCLASS()
    instance.test_list([1, 2, 3])


def test_list_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_list([1, "string"])


def test_tuple_pass():
    instance = _TCLASS()
    instance.test_tuple((1, "string"))


def test_tuple_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_tuple((1, 2))


def test_dict_pass():
    instance = _TCLASS()
    instance.test_dict({"key": 1})


def test_dict_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_dict({"key": "value"})


def test_sequence_pass():
    instance = _TCLASS()
    instance.test_sequence([1, 2, 3])


def test_sequence_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_sequence([1, "string"])


def test_iterable_pass():
    instance = _TCLASS()
    instance.test_iterable(iter([1, 2, 3]))


def test_iterable_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_iterable(iter([1, "string"]))


def test_mapping_pass():
    instance = _TCLASS()
    instance.test_mapping({"key": 1})


def test_mapping_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_mapping({"key": "value"})


def test_generator_pass():
    def gen() -> Generator[int, None, None]:
        yield 1
        yield 2

    instance = _TCLASS()
    instance.test_generator(gen())


def test_generator_fail():
    def gen() -> Generator[int, None, None]:
        yield 1
        yield "string"

    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_generator(gen())


def test_int_or_str_pass():
    instance = _TCLASS()
    instance.test_int_or_str(10)
    instance.test_int_or_str("hello")


def test_int_or_str_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_int_or_str(3.14)


def test_list_or_none_pass():
    instance = _TCLASS()
    instance.test_list_or_none([1, 2, 3])
    instance.test_list_or_none(None)


def test_list_or_none_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_list_or_none("string")


def test_dict_or_empty_pass():
    instance = _TCLASS()
    instance.test_dict_or_empty({"key": 1})
    instance.test_dict_or_empty({})


def test_dict_or_empty_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_dict_or_empty("string")


def test_tuple_or_none_pass():
    instance = _TCLASS()
    instance.test_tuple_or_none((1, "string"))
    instance.test_tuple_or_none(None)


def test_tuple_or_none_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_tuple_or_none((1, 2))


def test_sequence_or_generator_pass():
    instance = _TCLASS()
    instance.test_sequence_or_generator([1, 2, 3])

    def gen() -> Generator[int, None, None]:
        yield 1
        yield 2

    instance.test_sequence_or_generator(gen())


def test_sequence_or_generator_fail():
    instance = _TCLASS()
    with pytest.raises(TypeError):
        instance.test_sequence_or_generator(iter([1, "string"]))
