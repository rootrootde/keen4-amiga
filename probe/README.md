# Amiga qualification probe

This program checks the AmigaOS 68k toolchain and runtime services used by
the game build.

Run **make build-probe** at the repository root. The script uses the local Docker
image pinned by digest and writes **build/amiga/keen-probe**. It mounts only this
repository and does not need the game files. The compiler uses 68040 and hard
float code generation, the libnix C runtime, and the SDL 1.2 archive.

The image and inputs used for the initial build are:

| Input | SHA-256 |
| --- | --- |
| Image | 369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de |
| m68k-amigaos-gcc | a419431077b167d69c9be40ed6d2adf8ff77f77ce721fff6c9658c21420db7b0 |
| libSDL.a | 0e5af159ddb3d7d8a39636fbab2818dd1e94d9746e85a33b1d682d81780feed9 |
| SDL.h | 7dcd342424ce3f57bb9b55ffe110fc1184b4c9a9cade82117afbfd571f71ed92 |

Copy the executable to a guest-accessible test volume. The result directory
must exist and be writable. A run ID must be unique for each invocation.

```
TEST:keen-probe --run-id probe-a1 --build-id ec1f293c464367b4 --result-dir RESULT:
TEST:keen-probe --run-id probe-i1 --build-id ec1f293c464367b4 --result-dir RESULT: --interactive
```

Automatic mode runs for four seconds. Interactive mode runs for fifteen
seconds; press a key or mouse button during that time. Both are silent by
default. Use **--audible** only when an audible check is wanted; it plays a
low-level sine tone for at most 200 ms. Silence still tests SDL/AHI callback
progress, but it does not test audible output. The screen should show
an unscaled 320 by 200 indexed pattern. Each run writes a start file, progress
file, file roundtrip artifact, and final result file under the run ID. For
example, **RESULT:probe-a1.result** contains separate statuses for file I/O,
FPU arithmetic, 8-bit graphics, elapsed timer, human input, and audio callback
progress. A callback proves audio processing advanced; audibility stays
unverified until someone listens on the target. The result file records whether
human input was seen, and only interactive mode requires it for a pass.

The start file and progress lines let a failed or hung run be distinguished
from a run that never launched. Start and final records are published by
renaming completed temporary files. The final result is written only after
SDL cleanup. A missing final result is a failure to complete, regardless of
the last progress line.
