"""Crea un archivio di soli sorgenti: nessun dato privato o cronologia Git."""

import hashlib
import json
import stat
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
NAME = f"{json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))['asset_prefix']}-{VERSION}"
FOLDERS = {
    "traccia",
    "web",
    "istruzioni",
    "conoscenza",
    "tests",
    "demo",
    "docs",
    "packaging",
    "tools",
    ".github",
    ".claude",
}
SUFFIXES = {".py", ".html", ".css", ".js", ".md", ".yml", ".json", ".png", ".svg", ".gif", ".iss"}
FILES = {
    "README.md",
    "LICENSE",
    "CLAUDE.md",
    "requirements.txt",
    "pyproject.toml",
    "Avvia.bat",
    "Avvia.command",
    "avvia.sh",
    ".gitignore",
    ".gitattributes",
    ".nojekyll",
    "tools/package_release.py",
    "avvia.py",
    "release.json",
}


def main():
    paths = {ROOT / path for path in FILES}
    for folder in FOLDERS:
        paths.update(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and p.suffix in SUFFIXES
            and "__pycache__" not in p.parts
            and not p.name.endswith(".local.json")
        )
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"{NAME}.zip"
    hashes = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(paths):
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            if path.suffix in {".bat", ".sh", ".command"}:
                data = data.replace(b"\r\n", b"\n")
                if path.suffix == ".bat":
                    data = data.replace(b"\n", b"\r\n")
            item = zipfile.ZipInfo(f"{NAME}/{relative}")
            item.create_system = 3
            mode = 0o755 if path.suffix in {".sh", ".command"} else 0o644
            item.external_attr = (stat.S_IFREG | mode) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(item, data)
            hashes.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
        output.writestr(f"{NAME}/MANIFEST.sha256", "\n".join(hashes) + "\n")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"{archive}\n{len(paths)} file sorgente\nSHA256: {checksum}")


if __name__ == "__main__":
    main()
