from __future__ import annotations

import zipfile
from io import BytesIO

import requests

from settings import DART_API_BASE, DART_API_KEY


def main() -> None:
    # 여기 테스트할 접수번호 넣기
    rcept_no = "20260220002549"

    url = f"{DART_API_BASE.rstrip('/')}/document.xml"
    resp = requests.get(
        url,
        params={
            "crtfc_key": DART_API_KEY,
            "rcept_no": rcept_no,
        },
        timeout=60,
    )

    print("status_code:", resp.status_code)
    print("content-type:", resp.headers.get("content-type"))
    print("content-length:", resp.headers.get("content-length"))

    content = resp.content
    print("first_100_bytes:", content[:100])
    print("is_zip_signature:", content.startswith(b"PK"))

    if not content.startswith(b"PK"):
        preview = content[:1000].decode("utf-8", errors="ignore")
        print("\n===== NOT ZIP PREVIEW START =====")
        print(preview)
        print("===== NOT ZIP PREVIEW END =====")
        return

    zf = zipfile.ZipFile(BytesIO(content))
    names = zf.namelist()

    print("\nzip file list:")
    for name in names:
        print("-", name)

    for name in names[:5]:
        data = zf.read(name)
        preview = data[:500].decode("utf-8", errors="ignore")
        print(f"\n===== FILE PREVIEW: {name} =====")
        print(preview)
        print("===== END PREVIEW =====")


if __name__ == "__main__":
    main()