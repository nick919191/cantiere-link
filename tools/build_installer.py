"""Compila il pacchetto nativo sulla piattaforma di destinazione. Non pubblica nulla."""

import hashlib
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def icon():
    from PIL import Image, ImageDraw

    pic = Image.new("RGBA", (256, 256), "#101923")
    draw = ImageDraw.Draw(pic)
    draw.rounded_rectangle((40, 36, 157, 153), radius=27, outline="#69e5c5", width=10)
    draw.rounded_rectangle((99, 103, 216, 220), radius=27, outline="#69e5c5", width=10)
    path = ROOT / "packaging/icon.ico"
    pic.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    pic.save(ROOT / "packaging/icon.icns")


def notices():
    folder = ROOT / "build/notices"
    folder.mkdir(parents=True, exist_ok=True)
    catalog = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        catalog.append(name + " " + distribution.version)
        for item in distribution.files or []:
            if any(part.lower().startswith(("license", "copying", "notice")) for part in item.parts):
                source = Path(distribution.locate_file(item))
                if source.is_file() and source.stat().st_size < 3_000_000:
                    target = folder / name / str(item).replace("..", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    license_python = Path(sys.base_prefix) / "LICENSE.txt"
    if license_python.exists():
        shutil.copyfile(license_python, folder / "PYTHON-LICENSE.txt")
    (folder / "DEPENDENCIES.txt").write_text(
        "Componenti dell’ambiente di compilazione; le rispettive licenze restano valide.\n"
        + "\n".join(sorted(catalog)),
        encoding="utf-8",
    )
    return folder


def main():
    icon()
    license_folder = notices()
    native = ROOT / "dist/native"
    native.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "CantiereLink",
        "--distpath",
        str(native),
        "--workpath",
        str(ROOT / "build/pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
        "--paths",
        str(ROOT),
        "--collect-all",
        "pypdfium2",
        "--collect-all",
        "pypdfium2_raw",
        "--collect-submodules",
        "keyring.backends",
        "--collect-all",
        "uvicorn",
        "--collect-all",
        "webview",
        "--copy-metadata",
        "keyring",
        "--hidden-import",
        "traccia.server",
    ]
    args += ["--add-data", f"{license_folder}{os.pathsep}third_party_licenses"]
    for folder in ("web", "docs", "demo", "istruzioni", "conoscenza"):
        args += ["--add-data", f"{ROOT / folder}{os.pathsep}{folder}"]
    for file in ("pyproject.toml", "release.json", "LICENSE"):
        args += ["--add-data", f"{ROOT / file}{os.pathsep}."]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "it.cantierelink.app", "--icon", str(ROOT / "packaging/icon.icns")]
    else:
        args += ["--icon", str(ROOT / "packaging/icon.ico")]
    args.append(str(ROOT / "packaging/entry.py"))
    subprocess.run(args, cwd=ROOT, check=True)
    if sys.platform == "win32":
        compiler = shutil.which("ISCC") or next(
            (
                str(p)
                for p in [
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe",
                    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
                ]
                if p.is_file()
            ),
            None,
        )
        if not compiler:
            raise RuntimeError("Installa Inno Setup 6 per produrre Setup.exe.")
        env = os.environ.copy()
        env["CANTIERELINK_VERSION"] = VERSION
        subprocess.run([compiler, str(ROOT / "packaging/windows.iss")], cwd=ROOT, env=env, check=True)
        target = ROOT / f"dist/CantiereLink-Setup-{VERSION}.exe"
    elif sys.platform == "darwin":
        stage = ROOT / "build/dmg"
        stage.mkdir(parents=True, exist_ok=True)
        destination = stage / "CantiereLink.app"
        if destination.exists():
            raise RuntimeError("Usa una cartella build/dmg nuova per la compilazione.")
        shutil.copytree(native / "CantiereLink.app", destination, symlinks=True)
        (stage / "Applications").symlink_to("/Applications")
        target = ROOT / f"dist/CantiereLink-{VERSION}-macos-{platform.machine()}.dmg"
        subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                "CantiereLink",
                "-srcfolder",
                str(stage),
                "-ov",
                "-format",
                "UDZO",
                str(target),
            ],
            check=True,
        )
    else:
        raise RuntimeError("Compila su Windows per .exe o su macOS per .dmg.")
    target.with_suffix(target.suffix + ".sha256").write_text(
        hashlib.sha256(target.read_bytes()).hexdigest() + "  " + target.name + "\n"
    )
    print(target)


if __name__ == "__main__":
    main()
