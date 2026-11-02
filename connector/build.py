#!/usr/bin/env python3
"""Packs the extension into dist/cortex-chat-<version>.mcpb and the skill into dist/cortex-chat-skill.zip.

Standard library only; downloads nothing. Only the listed files go in. Run: python3 connector/build.py
"""
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # same input, same file


def add(archive: zipfile.ZipFile, source: Path, name: str) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, source.read_bytes())


def main() -> None:
    version = json.loads((HERE / "manifest.json").read_text())["version"]
    DIST.mkdir(exist_ok=True)
    bundle = DIST / f"cortex-chat-{version}.mcpb"
    with zipfile.ZipFile(bundle, "w") as z:
        add(z, HERE / "manifest.json", "manifest.json")
        for f in sorted((HERE / "server").glob("*.js")):
            add(z, f, f"server/{f.name}")
        for f in sorted((HERE / "server" / "templates").iterdir()):
            if f.is_file():
                add(z, f, f"server/templates/{f.name}")
    skill = DIST / "cortex-chat-skill.zip"
    with zipfile.ZipFile(skill, "w") as z:
        add(z, HERE / "skill" / "cortex-chat" / "SKILL.md", "cortex-chat/SKILL.md")
    print(f"Built {bundle}\nBuilt {skill}")


if __name__ == "__main__":
    main()
