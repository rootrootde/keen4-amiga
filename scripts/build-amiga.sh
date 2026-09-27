#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
image=sha256:369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de
compiler_sha256=a419431077b167d69c9be40ed6d2adf8ff77f77ce721fff6c9658c21420db7b0
sdl_sha256=0e5af159ddb3d7d8a39636fbab2818dd1e94d9746e85a33b1d682d81780feed9
sdl_header_sha256=7dcd342424ce3f57bb9b55ffe110fc1184b4c9a9cade82117afbfd571f71ed92
sysflags='-m68040 -mhard-float -noixemul -I/opt/m68k-amigaos/usr/include/SDL -DKEEN_AMIGA_RTG=1 -DCK_ENABLE_PLAYLOOP_DUMPER=1 -DFS_NO_OMNI_EXEDIR_FALLBACK=1 -DFS_NO_USER_XDG_FALLBACK=1'
sdl_cflags=-DWITH_SDL
sdl_libs='-L/opt/m68k-amigaos/usr/lib -lSDL'

version_output=$(docker run --rm --platform linux/arm64 "$image" sh -ec '
  test "$(sha256sum /opt/m68k-amigaos/bin/m68k-amigaos-gcc | cut -d" " -f1)" = "a419431077b167d69c9be40ed6d2adf8ff77f77ce721fff6c9658c21420db7b0"
  test "$(sha256sum /opt/m68k-amigaos/usr/lib/libSDL.a | cut -d" " -f1)" = "0e5af159ddb3d7d8a39636fbab2818dd1e94d9746e85a33b1d682d81780feed9"
  test "$(sha256sum /opt/m68k-amigaos/usr/include/SDL/SDL.h | cut -d" " -f1)" = "7dcd342424ce3f57bb9b55ffe110fc1184b4c9a9cade82117afbfd571f71ed92"
  /opt/m68k-amigaos/bin/m68k-amigaos-gcc --version
')
compiler_version=$(printf '%s\n' "$version_output" | sed -n '1p')
export compiler_version compiler_sha256 sdl_sha256 sdl_header_sha256 sysflags sdl_cflags sdl_libs

for variant in release debug; do
  if [ "$variant" = debug ]; then
    debug=1
  else
    debug=0
  fi
  docker run --rm --platform linux/arm64 \
    --user "$(id -u):$(id -g)" \
    --volume "$PWD:/work" --workdir /work "$image" \
    make -C src -B -j2 all PLATFORM=amiga RENDERER=sdl1 BUILDASCPP=0 \
    WITH_KEEN4=1 WITH_KEEN5=0 WITH_KEEN6=0 DEBUG="$debug" \
    COMPILER=/opt/m68k-amigaos/bin/m68k-amigaos-gcc \
    BINDIR="../build/amiga/$variant" \
    OBJDIR="../build/amiga/$variant/obj" \
    SYSFLAGS="$sysflags" \
    SDL_CFLAGS="$sdl_cflags" \
    SDL_LIBS="$sdl_libs"
done

python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path('build/amiga')
source_paths = [Path('Makefile'), Path('scripts/build-amiga.sh')]
source_paths.extend(sorted(path for path in Path('src').rglob('*')
                           if path.is_file() and not path.is_symlink() and
                           (path.suffix.lower() in ('.c', '.h', '.cpp', '.hpp', '.s', '.rc', '.frag', '.vert')
                            or path.name.startswith('Makefile')
                            or path.name == 'NUKEDOPL3-LICENSE')))
source_paths.extend(Path('data/keen4') / name for name in (
    'ACTION.CK4', 'AUDINFOE.CK4', 'AUDIODCT.CK4', 'AUDIOHHD.CK4',
    'EGADICT.CK4', 'EGAHEAD.CK4', 'EPISODE.CK4', 'GFXCHUNK.CK4',
    'GFXINFOE.CK4', 'MAPHEAD.CK4', 'STRINGS.CK4', 'TILEINFO.CK4'))
details = {
    'upstream_commit': '144f21e9891cd3df194df44bb0f2531c5dbc6bcb',
    'image_sha256': '369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de',
    'compiler_path': '/opt/m68k-amigaos/bin/m68k-amigaos-gcc',
    'compiler_version': os.environ['compiler_version'],
    'compiler_sha256': os.environ['compiler_sha256'],
    'sdl_archive_sha256': os.environ['sdl_sha256'],
    'sdl_header_sha256': os.environ['sdl_header_sha256'],
    'verified_toolchain': True,
    'sysflags': os.environ['sysflags'].split(),
    'sdl_cflags': os.environ['sdl_cflags'].split(),
    'sdl_libs': os.environ['sdl_libs'].split(),
    'make_options': {
        'platform': 'amiga', 'renderer': 'sdl1', 'build_as_cpp': 0,
        'keen4': 1, 'keen5': 0, 'keen6': 0,
    },
    'variant_flags': {
        'release': {'compile': ['-std=gnu99', '-O2', '-DWITH_KEEN4'], 'link': []},
        'debug': {'compile': ['-std=gnu99', '-g', '-O0', '-DCK_DEBUG', '-DWITH_KEEN4'], 'link': ['-g']},
    },
    'cpu_flags': ['-m68040', '-mhard-float', '-noixemul'],
    'compile_defines': [
        'KEEN_AMIGA_RTG=1', 'CK_ENABLE_PLAYLOOP_DUMPER=1',
        'FS_NO_OMNI_EXEDIR_FALLBACK=1', 'FS_NO_USER_XDG_FALLBACK=1',
        'WITH_KEEN4', 'WITH_SDL',
    ],
    'episode': 'keen4',
    'renderer': 'sdl1',
    'variants': {},
    'source_inputs': {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in source_paths},
}
diff = subprocess.run(['git', 'diff', '--binary', '--', 'src'],
                      capture_output=True, check=True).stdout
details['source_diff_sha256'] = hashlib.sha256(diff).hexdigest()
for variant in ('release', 'debug'):
    path = root / variant / 'omnispeak'
    details['variants'][variant] = {
        'path': str(path),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes': path.stat().st_size,
    }
(root / 'build.json').write_text(json.dumps(details, indent=2) + '\n')
PY
