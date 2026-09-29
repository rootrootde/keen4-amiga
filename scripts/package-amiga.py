#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import sys
import os
import shutil
import subprocess
from datetime import datetime, timezone
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.1.0"
HARDWARE_TESTED_SHA256 = "4588697409bcfc67daaa886b1e39269ba48c6b533a5711e03864a10cd6bf945c"
ARCHIVE_ROOT = "keen4-amiga"
SUPPORT_FILES = (
    "ACTION.CK4", "AUDINFOE.CK4", "AUDIODCT.CK4", "AUDIOHHD.CK4",
    "EGADICT.CK4", "EGAHEAD.CK4", "EPISODE.CK4", "GFXCHUNK.CK4",
    "GFXINFOE.CK4", "MAPHEAD.CK4", "STRINGS.CK4", "TILEINFO.CK4",
)
GAME_FILES = ("AUDIO.CK4", "EGAGRAPH.CK4", "GAMEMAPS.CK4")
BUILD_README = """Keen 4 Amiga source snapshot

This drawer contains the port source, support files, build scripts and SDL
1.2 source. The original SDL source is in third_party. Its matching archive
was built from AmigaPorts/SDL_old commit eb484f4a1b70257f962c295647ad262c8257c1dd.
The pinned toolchain image and compiler hashes are in ../build.json.

To rebuild or change the linked SDL library, use a host with Docker and run:

  sh scripts/build-sdl.sh
  sh scripts/relink-amiga.sh build/sdl-source/build/libSDL.a

On its first run, build-sdl.sh extracts SDL into build/sdl-source. Edit that
tree, run the script again, then relink. The extracted tree is kept between
runs. The original archive is left untouched. The relinked executable is at
build/amiga/relinked/omnispeak. Game data is supplied separately.

The source snapshot has no Git history. The normal build script's recorded
source_diff_sha256 therefore applies to the repository checkout, not a new
repository made from this drawer. See ../README for installation.
"""
LAUNCHER = "Stack 262144\nomnispeak /EPISODE 4 /NOBORDER /NOCOPY\n"
SILENT_LAUNCHER = "Stack 262144\nomnispeak /EPISODE 4 /NOBORDER /NOCOPY /NOSOUND\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"missing regular input: {relative}")
    return path.read_bytes()


def source_input_paths(root):
    paths = [Path("Makefile"), Path("scripts/build-amiga.sh")]
    paths.extend(sorted(path.relative_to(root) for path in (root / "src").rglob("*")
                        if path.is_file() and not path.is_symlink() and
                        (path.suffix.lower() in (".c", ".h", ".cpp", ".hpp", ".s",
                                                 ".rc", ".frag", ".vert")
                         or path.name.startswith("Makefile")
                         or path.name == "NUKEDOPL3-LICENSE")))
    paths.extend(Path("data/keen4") / name for name in SUPPORT_FILES)
    return paths


def package_payload(root):
    build = json.loads(read_file(root, "build/amiga/build.json"))
    recorded = build.get("source_inputs")
    if not isinstance(recorded, dict):
        raise ValueError("build.json lacks source input hashes")
    current = {path.as_posix(): digest(read_file(root, path))
               for path in source_input_paths(root)}
    if current != recorded:
        raise ValueError("source inputs differ from build.json")
    files = {
        "omnispeak": read_file(root, "build/amiga/release/omnispeak"),
        "build.json": read_file(root, "build/amiga/build.json"),
        "LICENSE": read_file(root, "LICENSE"),
        "AUTHORS": read_file(root, "AUTHORS"),
        "README": read_file(root, "README.md"),
        "upstream/README": read_file(root, "upstream/README"),
        "licenses/LGPL-2.1.txt": read_file(root, "src/opl/NUKEDOPL3-LICENSE"),
        "licenses/SDL-README.txt": read_file(root, "licenses/SDL-README.txt"),
        "Install": read_file(root, "packaging/Install"),
        "Install.info": read_file(root, "packaging/Install.info"),
        "Start-Keen4.info": read_file(root, "packaging/Start-Keen4.info"),
        "Start-Keen4": LAUNCHER.encode("ascii"),
        "Start-Keen4-NoSound": SILENT_LAUNCHER.encode("ascii"),
        "source/README-BUILD.txt": BUILD_README.encode("utf-8"),
        "source/LICENSE": read_file(root, "LICENSE"),
        "source/AUTHORS": read_file(root, "AUTHORS"),
        "source/upstream/README": read_file(root, "upstream/README"),
        "source/Makefile": read_file(root, "Makefile"),
        "source/scripts/build-amiga.sh": read_file(root, "scripts/build-amiga.sh"),
        "source/scripts/build-sdl.sh": read_file(root, "scripts/build-sdl.sh"),
        "source/scripts/relink-amiga.sh": read_file(root, "scripts/relink-amiga.sh"),
        "source/third_party/SDL-1.2.16-source.tar.gz": read_file(root, "third_party/SDL-1.2.16-source.tar.gz"),
    }
    for name in SUPPORT_FILES:
        files[name] = read_file(root, f"data/keen4/{name}")
        files[f"source/data/keen4/{name}"] = files[name]
    for path in source_input_paths(root):
        if path.parts[0] != "src" or ".." in path.parts:
            continue
        files[f"source/{path.as_posix()}"] = read_file(root, path)
    release = build["variants"]["release"]
    if release["sha256"] != digest(files["omnispeak"]) or \
       release["bytes"] != len(files["omnispeak"]):
        raise ValueError("release binary differs from build.json")
    return files


def zip_info(name, executable=False):
    info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{name}", (2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    return info


def lha_tool(command=None):
    tool = command or os.environ.get("LHA_COMMAND") or "lha"
    resolved = shutil.which(tool)
    if not resolved:
        raise ValueError(f"LHA compressor not found: {tool}; set --lha-command")
    result = subprocess.run([resolved, "--help"], capture_output=True, text=True)
    if "Add(or replace)" not in result.stdout:
        raise ValueError(f"{resolved} cannot create LHA archives; set --lha-command to LHa for UNIX")
    return str(Path(resolved).resolve())


def write_lha(path, files, command=None):
    tool = lha_tool(command)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    with tempfile.TemporaryDirectory(dir=path.parent) as staging_name:
        staging = Path(staging_name)
        for name, data in sorted(files.items()):
            target = staging / ARCHIVE_ROOT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if name in ("omnispeak", "source/scripts/build-amiga.sh",
                                         "source/scripts/build-sdl.sh",
                                         "source/scripts/relink-amiga.sh") else 0o644)
            os.utime(target, (timestamp, timestamp))
        environment = dict(os.environ, TZ="UTC")
        result = subprocess.run([tool, "ao5g0", str(path), ARCHIVE_ROOT],
                                cwd=staging, env=environment, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"LHA creation failed: {result.stderr or result.stdout}")


def read_lha(path, command=None):
    tool = shutil.which(command or os.environ.get("LHA_COMMAND") or "lha")
    if not tool:
        raise ValueError("LHA extractor not found; set --lha-command")
    tool = str(Path(tool).resolve())
    with tempfile.TemporaryDirectory(dir=path.parent) as extraction_name:
        extraction = Path(extraction_name)
        result = subprocess.run([tool, f"xw={extraction}", str(path)],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"LHA extraction failed: {result.stderr or result.stdout}")
        members = {}
        for member in extraction.rglob("*"):
            if member.is_symlink():
                raise ValueError("LHA contains a symlink")
            if member.is_file():
                members[member.relative_to(extraction).as_posix()] = member.read_bytes()
        return members


def create_package(root, output, lha_command=None):
    if output.suffix.lower() not in (".lha", ".zip"):
        raise ValueError("output must end in .lha or .zip")
    output = output.resolve()
    files = package_payload(root)
    manifest = {
        "version": VERSION,
        "kind": "release_candidate",
        "hardware_status": ("gameplay_sound_joystick_saveload_verified_a1200_pistorm32lite_cm4"
                            if digest(files["omnispeak"]) == HARDWARE_TESTED_SHA256
                            else "current_binary_not_hardware_verified"),
        "license_review": "corresponding_source_and_relink_verified",
        "publication_status": "not_published",
        "files": {name: {"sha256": digest(data), "bytes": len(data)}
                  for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=output.suffix, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        if output.suffix.lower() == ".lha":
            write_lha(temporary, files, lha_command)
        else:
            with zipfile.ZipFile(temporary, "w") as archive:
                for name, data in sorted(files.items()):
                    archive.writestr(zip_info(name, name in (
                        "omnispeak", "source/scripts/build-amiga.sh",
                        "source/scripts/build-sdl.sh",
                        "source/scripts/relink-amiga.sh")), data)
        verify_package(temporary, lha_command)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def verify_package(path, lha_command=None):
    if path.suffix.lower() == ".lha":
        members = read_lha(path, lha_command)
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate ZIP member")
            members = {name: archive.read(name) for name in names}
    else:
        raise ValueError("archive must end in .lha or .zip")
    prefix = f"{ARCHIVE_ROOT}/"
    if any(not name.startswith(prefix) or name.endswith("/") or
           any(part in ("", ".", "..") for part in name.split("/"))
           for name in members):
        raise ValueError("invalid archive members")
    manifest = json.loads(members[prefix + "manifest.json"])
    expected = {prefix + name for name in manifest["files"]}
    if set(members) != expected | {prefix + "manifest.json"}:
        raise ValueError("archive members differ from manifest")
    for name, item in manifest["files"].items():
        data = members[prefix + name]
        if digest(data) != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError(f"archive hash mismatch: {name}")
    if any(prefix + name in members for name in GAME_FILES):
        raise ValueError("game data in archive")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local" / "packages" / f"keen4-{VERSION}.lha")
    parser.add_argument("--lha-command", help="path to an LHa for UNIX compressor")
    args = parser.parse_args()
    try:
        manifest = create_package(ROOT, args.output, args.lha_command)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{args.output}: {len(manifest['files'])} files, release candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
