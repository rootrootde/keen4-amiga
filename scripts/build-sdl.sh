#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
image=sha256:369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de
source_archive=third_party/SDL-1.2.16-source.tar.gz
source_dir=build/sdl-source

if [ ! -f "$source_archive" ]; then
  printf 'missing %s\n' "$source_archive" >&2
  exit 1
fi
if [ ! -d "$source_dir" ]; then
  mkdir -p "$source_dir"
  tar -xzf "$source_archive" -C "$source_dir" --strip-components=1
  cat > "$source_dir/CMake/git.cmake" <<'CMAKE'
function(get_git_tag output_var)
  set(${output_var} 1.2.16 PARENT_SCOPE)
endfunction()
function(get_git_commit_hash output_var)
  set(${output_var} -eb484f4 PARENT_SCOPE)
endfunction()
CMAKE
fi

docker run --rm --network none --platform linux/arm64 \
  --user "$(id -u):$(id -g)" --entrypoint /bin/sh \
  -e SOURCE_DATE_EPOCH=1762646400 \
  -v "$PWD/$source_dir:/work/sdl" -w /work/sdl "$image" -ec '
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/m68k-amigaos/usr \
      -DM68K_CPU=68040 -DM68K_FPU=hard \
      "-DM68K_COMMON=-s -ffast-math -fomit-frame-pointer -O3 -fno-exceptions -w -DBIG_ENDIAN -DAMIGA -fpermissive -std=c++14"
    cmake --build build -j4
  '
sha256sum "$source_dir/build/libSDL.a"
