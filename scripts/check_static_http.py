"""Check the built static server without executing a model or uploading media."""

import argparse
from urllib.error import HTTPError
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    base = parser.parse_args().base_url.rstrip("/")
    for filename, mime in (
        ("ort-wasm-simd-threaded.jsep.mjs", "application/javascript"),
        ("ort-wasm-simd-threaded.mjs", "application/javascript"),
        ("ort-wasm-simd-threaded.jsep.wasm", "application/wasm"),
        ("ort-wasm-simd-threaded.wasm", "application/wasm"),
    ):
        with urlopen(f"{base}/ort/{filename}", timeout=10) as response:
            assert response.status == 200, filename
            assert response.headers.get_content_type() == mime, filename
            prefix = response.read(32)
            assert prefix and b"<!doctype" not in prefix.lower(), filename
            if filename.endswith(".wasm"):
                assert prefix.startswith(b"\x00asm"), filename
    for folder in ("ort", "models"):
        try:
            with urlopen(f"{base}/{folder}/missing-smoke-asset", timeout=10):
                raise AssertionError(f"{folder} incorrectly returned SPA content")
        except HTTPError as error:
            assert error.code == 404, folder
    print("PASS: runtime MIME, WASM magic bytes and missing-asset HTTP 404")


if __name__ == "__main__":
    main()
