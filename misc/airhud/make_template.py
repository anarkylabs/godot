#!/usr/bin/env python3
"""Make the AirHUD Android source template: the stock template with only the
arm64 engine libraries replaced by the ones built from this branch.

Every other entry of the stock template, and of the engine AARs inside it, is
copied byte for byte and checked afterwards, so the result differs from the
stock template only in the engines.
"""

import argparse
import copy
import hashlib
import io
import json
import shutil
import struct
import zipfile
from pathlib import Path

LIBRARY = "jni/arm64-v8a/libgodot_android.so"
AARS = {
    "release": "libs/release/godot-lib.template_release.aar",
    "debug": "libs/debug/godot-lib.template_debug.aar",
}


def check_engine(data: bytes, name: str) -> None:
    # 64-bit little-endian ELF for AArch64 (machine 183).
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise SystemExit(f"{name} is not an arm64 ELF library")


def replace_library(aar: bytes, engine: bytes) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(aar)) as source, zipfile.ZipFile(out, "w") as dest:
        if LIBRARY not in source.namelist():
            raise SystemExit(f"{LIBRARY} not found in the engine AAR")
        for info in source.infolist():
            dest.writestr(copy.copy(info), engine if info.filename == LIBRARY else source.read(info))
    return out.getvalue()


def make_template(stock: Path, engines: dict[str, bytes], output: Path) -> None:
    if stock.resolve() == output.resolve():
        raise SystemExit("The stock template must stay untouched")
    replaced = {}
    with zipfile.ZipFile(stock) as source:
        for kind, aar_name in AARS.items():
            replaced[aar_name] = replace_library(source.read(aar_name), engines[kind])
        with zipfile.ZipFile(output, "w") as dest:
            for info in source.infolist():
                if info.filename in replaced:
                    dest.writestr(copy.copy(info), replaced[info.filename])
                else:
                    with source.open(info) as reader, dest.open(copy.copy(info), "w") as writer:
                        shutil.copyfileobj(reader, writer)

    # Compare everything once more: only the two engine libraries may differ.
    with zipfile.ZipFile(stock) as before, zipfile.ZipFile(output) as after:
        if before.namelist() != after.namelist():
            raise SystemExit("Template entries differ from the stock template")
        for name in before.namelist():
            if name not in replaced and before.read(name) != after.read(name):
                raise SystemExit(f"{name} differs from the stock template")
        for kind, aar_name in AARS.items():
            with zipfile.ZipFile(io.BytesIO(before.read(aar_name))) as first, \
                    zipfile.ZipFile(io.BytesIO(after.read(aar_name))) as second:
                if first.namelist() != second.namelist():
                    raise SystemExit(f"{aar_name} entries differ from the stock template")
                for name in first.namelist():
                    expected = engines[kind] if name == LIBRARY else first.read(name)
                    if second.read(name) != expected:
                        raise SystemExit(f"{aar_name}:{name} is not as expected")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path, help="stock android_source.zip of the same Godot version")
    parser.add_argument("release", type=Path, help="stripped arm64 template_release libgodot_android.so")
    parser.add_argument("debug", type=Path, help="stripped arm64 template_debug libgodot_android.so")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    engines = {"release": args.release.read_bytes(), "debug": args.debug.read_bytes()}
    for kind, data in engines.items():
        check_engine(data, kind)
    make_template(args.stock, engines, args.output)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    print(json.dumps({
        "template": str(args.output),
        "template_sha256": sha(args.output.read_bytes()),
        "stock_template_sha256": sha(args.stock.read_bytes()),
        "release_engine_sha256": sha(engines["release"]),
        "debug_engine_sha256": sha(engines["debug"]),
    }, indent=2))


if __name__ == "__main__":
    main()
