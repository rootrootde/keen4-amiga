# Amiga test runs

The source starts at Omnispeak commit
**144f21e9891cd3df194df44bb0f2531c5dbc6bcb**. Its original **README** is in **upstream/README**.
**AUTHORS** and **LICENSE** remain at the repository root. The Amiga build
uses the locally pinned arm64 cross-toolchain image, SDL 1.2, 68040 code
generation, hard float, and libnix. The image digest is
**sha256:369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de**.
The cross-compiler is GCC 15.2.0. **make build** checks the compiler, SDL
archive, and SDL header hashes inside that image before compiling. Its
**build.json** records those hashes, the compiler version, flags, and both
binary hashes.

Run **make build** for release and debug Keen 4 binaries. They are written to
**build/amiga/release** and **build/amiga/debug** with the repository's Keen 4
support files. **build/amiga/build.json** records the toolchain, flags, source
diff, and binary hashes. The game files are supplied separately and are not
part of either build. The SDL renderer requests a fullscreen 320 by 200
8-bit screen with its own palette.

The engine accepts **/NOSOUND** for unattended runs. It keeps the SDL timer
fallback active without opening an audio device. Leave that option out when
checking sound interactively. Manual run **game-855102ff9ea3454e** started a
new game, moved on the world map by keyboard, saved with F5, moved again, and
restored the position with F9. It entered Border Village, used the named menu
Save/Load flow, and quit through the regular menu with a passing guest result
after 368.69 seconds. Jump and pogo through modifier-key automation remain
unverified because the UI tool could not reliably hold those keys. A complete
level and longer physical PiStorm session remain unchecked.

The fullscreen probe at binary hash **ec1f293c464367b4** passed ten serial
cold boots in the emulator. The silent probe at **0f68023a17bdd634** passed
an automatic run without JIT, an automatic run with effective JIT, and an
interactive keyboard run (**probe-6085856351ee4b69**). A later probe build
at hash prefix **265d750** passed ten more serial silent cold boots, with
median start time 11.5965 seconds and total time 16.0206 seconds. File I/O,
FPU, graphics, timer, and callback progress were observed. Audible output
remains unverified. All five Keen 4 demos passed an
exact dump comparison without game audio or JIT on release binary
**672d457ed567d03d**.
An audio-enabled demo 0 run on release **44801a12a7950486** passed all 812
reference frames without JIT. It recorded 1,592 completed audio callbacks,
774,997 nonzero samples, and no invalid callback. The later release
**ad3415bb7602da24** passed all 20 cases of the five-demo JIT/audio replay
matrix. The current stress-test release is
**4588697409bcfc67daaa886b1e39269ba48c6b533a5711e03864a10cd6bf945c**;
its debug counterpart is
**fde11fc46318a244ee97f170bc2436cd3130756958f0698dfef3fb660fb593ae**.
A planned 52-cycle audio stress run was stopped at the user's request after
24 complete cycles and 856.25 seconds of demo playback. It is not a 52-cycle
pass or a 30-minute endurance result. The user
confirmed that the earlier **keen4-rtg-ad3415bb.zip** package, with release
binary SHA-256 **ad3415bb7602da248653c77c7583349676868f6234a0bb4c89b5cd08856132c6**,
starts and is playable on an Amiga 1200 with PiStorm32-Lite and CM4. The user
reported subjectively fluid play with sound. This is an initial physical test
of that older binary, not the current stress-test build. On the older package,
gamepad buttons work but directions do not. The current **45886974** release
normalizes the SDL backend's digital axis values of ±257 to full range; its
directional input still needs a physical retest. Physical save/load, device
versions, measured frame/audio behavior, a 30-minute session, and a full level
or playthrough remain open.

Copy **config/amiga.example.json** to **config/amiga.json** and set every path.
The configuration file is ignored by Git. The ROM and system base are read
from those paths. Each run gets its own copy of the system and its own test,
result, and home directories under **local/runs**. The harness copies
validated game files into each engine run and leaves their source untouched.

Prepare **system_base** from an existing, licensed AmigaOS installation. It
needs **C**, **S**, **L**, **Libs**, **Fonts**, **Classes**, **System**, and
**Devs** with the installed system's command, library, and device files. For
RTG, retain **Devs/Monitors/Uaegfx** and its icon. For audio runs, retain
**Devs/ahi.device**, **Devs/AHI/paula.audio**, and
**Devs/AudioModes/PAULA**. The tested minimal base uses this
**S/Startup-Sequence**:

```
FailAt 21
Assign T: RAM:
MakeDir RAM:ENV
Assign ENV: RAM:ENV
Assign ENVARC: SYS:Prefs/Env-Archive
Assign LIBS: SYS:Classes ADD
Assign KEYMAPS: DEVS:Keymaps
C:LoadMonDrvs
C:IPrefs
C:LoadWB
Echo "booted" >RESULT:boot.ok
If EXISTS TEST:run-test
 Execute TEST:run-test
EndIf
```

The harness requires that **TEST:run-test** hook and copies the system base
for each run. It mounts the copy as **System:**, a fresh test directory as
**TEST:**, and a fresh result directory as **RESULT:**. The ROM, OS files,
game files, and per-run copies remain outside Git; none are bundled with the
build. The emulator configuration requests 68040 with FPU, 64 MB Z3 RAM,
8 MB RTG memory, and either a disabled JIT or an 8192 KB JIT cache.

Build and run the probe with:

```
make build-probe
make test-amiga
make test-amiga ARGS='--repeat10 --jit'
make run-probe
make build
make replay ARGS='--demo 0'
make replay ARGS='--demo 0 --audio'
make regression
make regression ARGS='--repeat 2 --both-jit --both-audio'
make stress ARGS='--demo 0 --cycles 20 --audio'
make run
make run ARGS='--run-timeout-seconds 1800'
make validate-data
```

**make run-probe** starts the probe in interactive mode for fifteen seconds.
Press a key or mouse button while it is open. **make run** starts the game and
waits for a normal guest quit by default. **--run-timeout-seconds N** limits
an interactive game run; Ctrl-C stops the emulator process started by the
harness. **make replay** runs one built-in demo with **/NOSOUND** and compares its dump
byte for byte with the unchanged **tests/demoN.dump4** reference. Select
**--demo 0** through **--demo 4** and **--variant release** or **debug**.
Replay and regression runs pass **/AUTOTEST** to the guest. It ignores live
keyboard, mouse, and joystick input during the demo, while a window close
event still exits. Interactive game and probe runs keep normal input.
The comparator reports the first differing frame and its tick, game-state,
or object offset; missing or truncated dumps fail. **--jit** uses an 8192 KB JIT cache;
without it, the cache is disabled. Repeated runs report start and total times
for comparison. Each run writes **launch.json** with the exact command and
binary hashes, **status.json**, guest result files, host stdout and stderr,
and the emulator's own log under **home**.
The launch record also includes the emulator binary hash and app version. If
the host-wide Amiberry ini exists, the harness copies it into the run folder
and records its hash. Amiberry may still read that host-wide file even when a
per-run home and command-line configuration are set.

The harness waits up to 120 seconds for the guest start record. Replay runs
have a ten-minute total deadline; interactive game runs wait until guest quit
unless a timeout is requested. Probe runs have 45 seconds for an automatic
result or 70 seconds for an interactive result. Stress runs allow up to ten
minutes per cycle, resetting the deadline only after its completion record. It
requires the start, final result, and shell return marker to agree on run ID
and build ID. A missing result, stale ID, guest failure, or timeout fails the
host run. The harness terminates only the process it started. The emulator's
IPC socket is shared, so screenshots are omitted unless **lsof** confirms
that the launched process owns the socket. With confirmed ownership, the
harness captures status and a screenshot. It never sends an IPC quit command.
Automatic runs request normal guest audio processing with host volume muted.
Interactive runs are muted too unless **--audible** is supplied explicitly.
The probe generates a test tone only when both interactive mode and
**--audible** are requested. Callback progress alone does not establish that
sound was audible.
**--audio** on a replay leaves the guest sound engine active while keeping
host output muted. It requires the SDL audio device to open, callbacks to
run, and nonzero samples to be generated. The guest records callback and
sample counts, elapsed real milliseconds, and the span of simulation ticks
written to the dump. The Amiga build defaults to 22050 Hz mono with a
512-sample SDL buffer; **OMNISPK.CFG** can override these settings. The guest
result records the audio settings used. These checks do not verify audible
output.

**make regression** runs demos 0 through 4 in order and compares each dump
with its reference. **--repeat N** repeats each demo N times. **--jit** selects
the JIT profile, while **--both-jit** runs both profiles. **--audio** keeps
guest sound active, while **--both-audio** runs with and without guest sound.
Every run is serial. The run directory gets its own **launch.json** and
**status.json**. A **regression-*.json** file under **local/runs** records each
run ID, build ID, profile, binary and input hashes, dump hash, comparison,
audio metrics, and pass or failure result. Failed comparisons do not stop the
remaining cases. The matrix pins the binary and all five reference hashes
before the first run and stops if any changes. Automatic runs keep host output
muted, including audio cases.

**make stress** replays one demo 2 to 100 times in a single process. It checks
the first dump against the unchanged reference. Later dumps must complete
with a whole number of frames and the recorded frame count; inactive object
slots retain their contents between plays, so those dumps are not compared
against a cold-start reference. Each cycle uses the real save and load path,
checks persisted game-state fields, all three map planes, and object order and
fields, and keeps its save file. The loader rebuilds draw pointers, visibility,
scorebox cache values, and platform/stunned draw handles; these are excluded
from the field comparison. The run records frame and tick counts, elapsed
time, audio callback deltas, manager usage, and available memory after each
save/load boundary. **status.json** reports memory change from cycle 2 to the
last cycle without purging to mask growth. A stress pass establishes repeated
demo and core save/load behavior, not menu or full-game acceptance.

The three-cycle audio smoke run **game-ba47863280be4a71** passed on the
current release. Each cycle recorded 812 frames and 2,436 ticks; the first
dump matched the unchanged reference byte for byte. All three saved games
had SHA-256 **ace7145323a6fc9a4eaad20ca35a431e0c45e36e958e4d9db4d1caf139b5495e**.
At each post-load boundary, MM used 573,221 bytes in 917 blocks and VL used
287,616 bytes in four surfaces. Available OS memory was 64,814,240 bytes
for cycles 1 and 2 and 64,814,256 bytes for cycle 3. The run establishes
three successful repetitions; it does not establish long-run stability.

Before an engine run, set **game_data** to the supported Keen 4 v1.4
shareware directory and run **make validate-data**. The check requires the
three game data files and compares their SHA-256 hashes. The existing
**CKeen4** directory is left untouched; its GT v1.4 files do not pass this
check. The compatible v1.4 shareware files used for local checks came from
the original shareware archive and remain under ignored **local** storage.
Game data stays outside Git and is never bundled with a probe run. The replay
references are read only; the harness never rewrites them.

## Amiga package and installation checks

**make package-amiga** writes **local/packages/keen4-0.1.0.lha**. Pass
**--output path/to/file.zip** to **scripts/package-amiga.py** for a ZIP archive.
Building an LHA requires LHa for UNIX with archive creation support; Lhasa's
**lha** command only extracts. Set **LHA_COMMAND** to the compressor path:

```
LHA_COMMAND=/path/to/lha make package-amiga
```

The archive contains the release binary, twelve Keen 4 support files,
**build.json**, the root **README**, licenses and source. The upstream README
is kept separately as **upstream/README**. **manifest.json** records version,
SHA-256 and size for each file, plus hardware and publication status. ROM,
AmigaOS, drivers, local configuration and the three game files are excluded.
The user installation steps are in the root **README**.

The earlier **keen4-rtg-ad3415bb.zip** ran with picture and sound on an A1200,
but gamepad buttons worked without directional input. The newer axis fix still
needs a physical hardware retest.

Installer 44.10 completed interactively in **Intermediate** mode. **Expert**
stalled for an unknown reason. Installer 43.3 opened the first drawer chooser
in both modes, but a full interactive run was not checked. A scripted guest
run with 43.3 found **C:UnZip**, installed to **TEST:Install Parent/Keen4**,
preserved saves and **OMNISPK.CFG**, and launched the intro through IconX
(**run-1cb752dd**). The fallback UnZip selection also worked with a path
containing spaces (**run-96d2a3ca**). A separate run confirmed that
**Keen4.info** appeared beside the drawer and preserved an existing icon
(**run-2058bae3**). That run used the earlier package icon. The current
installer asks Installer to write the system's default drawer icon and
replaces only the icon shipped in the earlier package. Other drawer icons
are left in place. In **run-c72e7317**, the earlier package icon was replaced
by the configured default, while a positioned custom icon stayed unchanged
on reinstall. Both new tool icons loaded through the Amiga icon library as
64x40, two-plane icons with the intended default tools and stack sizes.

With Installer 43.3 and UnZip 5.52, scripted responses produced three game
files matching the selected ZIP by SHA-256, while saves and configuration
remained unchanged (**run-a1c89bb0**). The interactive file selection was
not checked in that run. A GT archive failed the **EGAGRAPH.CK4** size check
and left only the pre-existing save and configuration files (**run-a0fa3e4d**).

SDL 1.2 is linked statically under the LGPL. The release archive includes
its matching source tarball, SDL notice and LGPL text, plus scripts to rebuild
the library and relink a modified version. The unmodified rebuild and relink
matched the pinned library and game hashes byte for byte. See
[release.md](release.md) for the source commit and checksums.
