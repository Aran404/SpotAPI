"""Protobuf bounds, repeated fields and unknown-field compatibility."""

import pytest

from spotapi.v2.protobuf import ProtoMessage, encode_field
from spotapi.v2.types import BaseClientError


def test_wire_roundtrip_preserves_repeated_and_nested_fields() -> None:
    nested = encode_field(1, "spotify:track:example")
    wire = encode_field(1, nested) + encode_field(1, nested) + encode_field(700, (1 << 64) - 1)
    message = ProtoMessage.decode(wire)

    assert len(message.messages(1)) == 2
    assert message.messages(1)[0].string(1) == "spotify:track:example"
    assert message.integer(700) == (1 << 64) - 1


@pytest.mark.parametrize("wire", [b"\x00", b"\x80", b"\x0a\x05a", b"\x0b", b"\x08" + b"\xff" * 10])
def test_malformed_wire_is_rejected(wire: bytes) -> None:
    with pytest.raises(BaseClientError):
        ProtoMessage.decode(wire)


def test_oversized_message_and_invalid_text_fail_explicitly() -> None:
    with pytest.raises(BaseClientError, match="8 MiB"):
        ProtoMessage.decode(b"x" * (8 * 1024 * 1024 + 1))
    with pytest.raises(BaseClientError, match="UTF-8"):
        ProtoMessage.decode(encode_field(1, b"\xff")).string(1)


def test_unknown_fixed_width_fields_do_not_hide_known_fields() -> None:
    wire = b"\x15\x01\x00\x00\x00" + encode_field(1, "known")
    message = ProtoMessage.decode(wire)
    assert message.string(1) == "known" and message.integer(2) == 1
