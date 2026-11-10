"""Bounded protobuf wire decoding for Spotify's profile-view messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .types import BaseClientError

WireValue: TypeAlias = int | bytes


def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer using protobuf varint representation."""
    output = bytearray()
    while value > 127:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


def encode_field(number: int, value: int | str | bytes) -> bytes:
    """Encode a nonnegative integer or length-delimited protobuf field."""
    if type(number) is not int or not 0 < number < 1 << 29:
        raise ValueError("Invalid protobuf field number")
    if isinstance(value, int):
        if not 0 <= value < 1 << 64:
            raise ValueError("Protobuf integers must fit an unsigned 64-bit value")
        return _encode_varint(number << 3) + _encode_varint(value)
    content = value.encode("utf-8") if isinstance(value, str) else value
    return _encode_varint((number << 3) | 2) + _encode_varint(len(content)) + content


def _varint(data: bytes, offset: int) -> tuple[int, int]:
    """Read a bounded 64-bit varint or reject truncation and overflow."""
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            break
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            if value >= 1 << 64:
                break
            return value, offset
    raise BaseClientError("Invalid protobuf varint")


@dataclass(frozen=True, slots=True)
class ProtoMessage:
    fields: dict[int, tuple[WireValue, ...]]

    @classmethod
    def decode(cls, data: bytes) -> ProtoMessage:
        """Decode bounded protobuf wire fields, skipping supported unknown fields."""
        if len(data) > 8 * 1024 * 1024:
            raise BaseClientError("Spotify protobuf message exceeds 8 MiB")
        fields: dict[int, list[WireValue]] = {}
        offset = 0
        count = 0

        while offset < len(data):
            tag, offset = _varint(data, offset)
            number, wire = tag >> 3, tag & 7
            count += 1
            if not 0 < number < 1 << 29 or count > 100_000:
                raise BaseClientError("Invalid protobuf field count or number")

            if wire == 0:
                value, offset = _varint(data, offset)
            elif wire in {1, 2, 5}:
                if wire == 2:
                    size, offset = _varint(data, offset)
                else:
                    size = 8 if wire == 1 else 4
                end = offset + size
                if end > len(data):
                    raise BaseClientError("Truncated protobuf field")
                content = data[offset:end]
                value = content if wire == 2 else int.from_bytes(content, "little")
                offset = end
            else:
                raise BaseClientError("Unsupported protobuf wire type")
            fields.setdefault(number, []).append(value)

        return cls({number: tuple(values) for number, values in fields.items()})

    def string(self, number: int) -> str:
        """Read the last UTF-8 string field; reject invalid text encoding."""
        values = self.fields.get(number)
        if not values:
            return ""
        value = values[-1]
        if not isinstance(value, bytes):
            raise BaseClientError("Expected a protobuf string")
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BaseClientError("Invalid protobuf UTF-8 string") from error

    def integer(self, number: int) -> int:
        """Read the last varint field, or zero when the field is absent."""
        values = self.fields.get(number)
        if not values:
            return 0
        value = values[-1]
        if not isinstance(value, int):
            raise BaseClientError("Expected a protobuf integer")
        return value

    def messages(self, number: int) -> tuple[ProtoMessage, ...]:
        """Decode all length-delimited records for a repeated message field."""
        result: list[ProtoMessage] = []
        for value in self.fields.get(number, ()):
            if not isinstance(value, bytes):
                raise BaseClientError("Expected a nested protobuf message")
            result.append(self.decode(value))
        return tuple(result)
