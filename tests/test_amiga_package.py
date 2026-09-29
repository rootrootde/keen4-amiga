import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package-amiga.py"
INSTALL = Path(__file__).resolve().parents[1] / "packaging" / "Install"
ICON = Path(__file__).resolve().parents[1] / "packaging" / "Install.info"
GAME_ICON = Path(__file__).resolve().parents[1] / "packaging" / "Start-Keen4.info"
SPEC = importlib.util.spec_from_file_location("amiga_package", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output" / "hardware.zip"
        self.binary = b"amiga binary"
        self.write("build/amiga/release/omnispeak", self.binary)
        for path in ("LICENSE", "AUTHORS", "README.md", "upstream/README", "Makefile",
                     "licenses/SDL-README.txt",
                     "third_party/SDL-1.2.16-source.tar.gz",
                     "scripts/build-sdl.sh", "scripts/relink-amiga.sh",
                     "scripts/build-amiga.sh", "packaging/Install",
                     "packaging/Install.info", "packaging/Start-Keen4.info",
                     "src/opl/NUKEDOPL3-LICENSE",
                     "src/example.c"):
            self.write(path, {"packaging/Install": INSTALL,
                              "packaging/Install.info": ICON,
                              "packaging/Start-Keen4.info": GAME_ICON,
                              }[path].read_bytes()
                       if path.endswith(".info") or path == "packaging/Install"
                       else path.encode())
        for name in MODULE.SUPPORT_FILES:
            self.write(f"data/keen4/{name}", name.encode())
        self.write("data/keen4/AUDIO.CK4", b"private game data")
        self.write("config/amiga.json", b"private config")
        build = {
            "variants": {"release": {
                "sha256": hashlib.sha256(self.binary).hexdigest(),
                "bytes": len(self.binary),
            }},
            "source_inputs": {
                path.as_posix(): hashlib.sha256((self.root / path).read_bytes()).hexdigest()
                for path in MODULE.source_input_paths(self.root)
            },
        }
        self.write("build/amiga/build.json", json.dumps(build).encode())

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def create(self):
        return MODULE.create_package(self.root, self.output)

    def test_archive_membership_and_hashes(self):
        manifest = self.create()
        self.assertEqual(manifest["kind"], "release_candidate")
        self.assertEqual(manifest["publication_status"], "not_published")
        self.assertEqual(MODULE.verify_package(self.output), manifest)
        with zipfile.ZipFile(self.output) as archive:
            names = set(archive.namelist())
            prefix = MODULE.ARCHIVE_ROOT + "/"
            self.assertEqual(archive.read(prefix + "build.json"),
                             (self.root / "build/amiga/build.json").read_bytes())
            self.assertEqual(archive.read(prefix + "source/src/example.c"),
                             b"src/example.c")
            self.assertIn(prefix + "source/scripts/build-amiga.sh", names)
            self.assertEqual(archive.read(prefix + "README"), b"README.md")
            self.assertEqual(archive.read(prefix + "upstream/README"), b"upstream/README")
            self.assertIn(prefix + "licenses/SDL-README.txt", names)
            self.assertIn(prefix + "source/third_party/SDL-1.2.16-source.tar.gz", names)
            self.assertIn(prefix + "source/scripts/build-sdl.sh", names)
            self.assertIn(prefix + "source/scripts/relink-amiga.sh", names)
            self.assertIn(prefix + "source/LICENSE", names)
            self.assertIn(prefix + "source/AUTHORS", names)
            self.assertIn(prefix + "source/upstream/README", names)
            self.assertNotIn(prefix + "README-HARDWARE.txt", names)
            self.assertIn(prefix + "licenses/LGPL-2.1.txt", names)
            self.assertEqual(archive.read(prefix + "Install"),
                             (self.root / "packaging/Install").read_bytes())
            installer = archive.read(prefix + "Install")
            self.assertIn(b'"README" "LICENSE" "AUTHORS"', installer)
            self.assertIn(b'(delete (tackon #target "README-HARDWARE.txt"))', installer)
            self.assertEqual(archive.read(prefix + "Install.info"), ICON.read_bytes())
            self.assertEqual(archive.read(prefix + "Start-Keen4.info"), GAME_ICON.read_bytes())
            self.assertNotIn(prefix + "Keen4.info", names)
            self.assertIn(b"Stack 262144\n",
                          archive.read(prefix + "Start-Keen4"))
            self.assertIn(b"/NOSOUND",
                          archive.read(prefix + "Start-Keen4-NoSound"))
            self.assertEqual(archive.getinfo(prefix + "omnispeak").external_attr >> 16,
                             0o100755)
            self.assertNotIn(prefix + "AUDIO.CK4", names)
            self.assertNotIn(prefix + "config/amiga.json", names)
            self.assertFalse(any("local/" in name for name in names))

    def test_lha_archive_extracts_with_matching_hashes(self):
        compressor = (os.environ.get("LHA_COMMAND") or
                      str(SCRIPT.parents[1] / "work/installer/lha-release-20211125/src/lha"))
        if not Path(compressor).is_file() or not shutil.which("lha"):
            self.skipTest("LHa compressor or Lhasa extractor unavailable")
        output = self.root / "output" / "keen4-0.1.0.lha"
        manifest = MODULE.create_package(self.root, output, compressor)
        self.assertEqual(manifest["version"], MODULE.VERSION)
        self.assertEqual(MODULE.verify_package(output, compressor), manifest)
        subprocess.run(["lha", "t", str(output)], check=True, capture_output=True)
        if shutil.which("7zz"):
            extracted = self.root / "independent"
            subprocess.run(["7zz", "x", f"-o{extracted}", str(output)],
                           check=True, capture_output=True)
            for name, record in manifest["files"].items():
                data = (extracted / MODULE.ARCHIVE_ROOT / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            self.assertFalse((extracted / MODULE.ARCHIVE_ROOT / "AUDIO.CK4").exists())

    def test_hardware_status_requires_tested_binary_hash(self):
        self.assertEqual(self.create()["hardware_status"],
                         "current_binary_not_hardware_verified")
        with patch.object(MODULE, "HARDWARE_TESTED_SHA256",
                          hashlib.sha256(self.binary).hexdigest()):
            self.assertEqual(self.create()["hardware_status"],
                             "gameplay_sound_joystick_saveload_verified_a1200_pistorm32lite_cm4")

    def test_unsupported_extension_fails_before_output(self):
        output = self.root / "output" / "hardware.tar"
        with self.assertRaisesRegex(ValueError, r"\.lha or \.zip"):
            MODULE.create_package(self.root, output)
        self.assertFalse(output.exists())

    def check_icon(self, path, default_tool, stack, tooltypes, height,
                   glow=False):
        import struct

        data = path.read_bytes()
        self.assertEqual(struct.unpack_from(">HH", data, 0), (0xE310, 1))
        self.assertEqual(data[48], 4)
        self.assertEqual(struct.unpack_from(">hh", data, 12), (64, height))
        self.assertEqual(struct.unpack_from(">ii", data, 58),
                         (-2147483648, -2147483648))
        self.assertEqual(struct.unpack_from(">I", data, 74)[0], stack)
        self.assertEqual(struct.unpack_from(">hhh", data, 82), (64, height, 2))
        offset = 78 + 20 + 64 // 8 * height * 2
        fields = []
        for _ in range(1):
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            fields.append(data[offset:offset + length - 1].decode("ascii"))
            offset += length
        self.assertEqual(fields, [default_tool])
        self.assertEqual(struct.unpack_from(">I", data, offset)[0],
                         4 * (len(tooltypes) + 1))
        offset += 4
        for expected in tooltypes:
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            self.assertEqual(data[offset:offset + length], expected.encode() + b"\0")
            offset += length
        if glow:
            self.assertEqual(data[offset:offset + 4], b"FORM")
            form_size = struct.unpack_from(">I", data, offset + 4)[0]
            self.assertEqual(data[offset + 8:offset + 12], b"ICON")
            form = data[offset + 12:offset + 8 + form_size]
            chunks = []
            chunk_offset = 0
            while chunk_offset < len(form):
                name = form[chunk_offset:chunk_offset + 4]
                size = struct.unpack_from(">I", form, chunk_offset + 4)[0]
                payload = form[chunk_offset + 8:chunk_offset + 8 + size]
                chunks.append((name, payload))
                chunk_offset += 8 + size + (size & 1)
            self.assertEqual(chunk_offset, len(form))
            self.assertEqual([name for name, _ in chunks],
                             [b"FACE", b"IMAG", b"IMAG"])
            self.assertEqual(struct.unpack(">BBBBH", chunks[0][1]),
                             (63, 55, 0, 0, 92))
            for (_, payload), colors in zip(chunks[1:], (29, 31)):
                transparent, color_max, flags, image_format, palette_format, depth, \
                    image_size, palette_size = struct.unpack_from(">BBBBBBHH", payload)
                self.assertEqual((transparent, color_max, flags, image_format,
                                  palette_format, depth),
                                 (0, colors - 1, 3, 0, 0, 5))
                self.assertEqual(image_size + 1, 64 * 56)
                self.assertEqual(palette_size + 1, colors * 3)
                self.assertEqual(len(payload), 10 + 64 * 56 + colors * 3)
            self.assertEqual(offset + 8 + form_size, len(data))
        else:
            self.assertEqual(offset, len(data))

    def test_install_icon(self):
        self.check_icon(ICON, "C:Installer", 65536,
                        ("MINUSER=AVERAGE", "DEFUSER=AVERAGE", "APPNAME=Keen4"), 40)

    def test_game_icon(self):
        self.check_icon(GAME_ICON, "C:IconX", 262144,
                        ("WINDOW=CON:0/0/640/100/Keen4/AUTO/CLOSE",), 56,
                        glow=True)

    def test_missing_input_fails_without_archive(self):
        (self.root / "data/keen4/ACTION.CK4").unlink()
        with self.assertRaises(FileNotFoundError):
            self.create()
        self.assertFalse(self.output.exists())

    def test_binary_must_match_build_record(self):
        self.write("build/amiga/release/omnispeak", b"changed")
        with self.assertRaisesRegex(ValueError, "release binary differs"):
            self.create()
        self.assertFalse(self.output.exists())

    def test_changed_source_fails_without_archive(self):
        self.write("src/example.c", b"changed")
        with self.assertRaisesRegex(ValueError, "source inputs differ"):
            self.create()
        self.assertFalse(self.output.exists())

    def test_new_source_fails_without_archive(self):
        self.write("src/ck_amiga_test.c", b"new source")
        with self.assertRaisesRegex(ValueError, "source inputs differ"):
            self.create()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
