import msgpack
from typing import Any

def encode(data: Any) -> bytes:
    return msgpack.packb(data, use_bin_type=True)

def decode(data: bytes) -> Any:
    return msgpack.unpackb(data, raw=False)
