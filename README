# Keen 4 for AmigaOS 68k

Version 0.1.0 runs Commander Keen 4 on AmigaOS with a PiStorm/Emu68 setup. It uses a 68040 with FPU, a 256-color RTG display (such as Picasso96), and AHI Unit 0 for sound. This is an RTG port; OCS and AGA screen modes are not supported. The engine is based on [Omnispeak](https://github.com/sulix/omnispeak). This build supports Keen 4 v1.4 EGA only.

## Install

You need Installer 43.3 or newer, UnZip, IconX, and a writable drawer. Keep about 700 KiB free in T: for extraction. Get the Keen 4 v1.4 EGA shareware archive [4keen14.zip](https://davidgow.net/keen/4keen14.zip) separately; game data is not in this package.

1. Extract **keen4-0.1.0.lha** into a drawer on your Amiga.
2. Double-click **Install** and choose **Intermediate User**. Select the parent drawer where **Keen4** should be created, then select **4keen14.zip**. The installer finds **UnZip** in C:, SYS:Utilities or SYS:System, or asks where it is.
3. Open the installed **Keen4** drawer and double-click **Start-Keen4**. The launcher uses IconX and sets the required stack size. The drawer receives your system's default drawer icon.

The installer extracts only **AUDIO.CK4**, **EGAGRAPH.CK4**, and **GAMEMAPS.CK4** from the ZIP, checks their sizes, and leaves the ZIP untouched. If installing by hand, copy those three files beside **omnispeak** along with the package's Keen 4 support files. The expected sizes are 33,325, 520,581, and 99,040 bytes respectively. GT retail files are incompatible. From a Shell in the game drawer, run **Execute Start-Keen4**. **Execute Start-Keen4-NoSound** starts without audio.

If an interrupted install leaves **T:Keen4InstallData**, inspect and remove that temporary drawer before retrying. Existing saves and **OMNISPK.CFG** in the destination are preserved by the installer.

## Play and settings

Arrow keys move. Ctrl jumps, Alt uses the pogo stick, and Space fires. Enter opens the status screen. F5 quick-saves and F9 quick-loads; these bindings can be changed in the game's keyboard settings. Joystick buttons and directions are supported by the SDL input code, but the latest direction fix still needs a physical hardware retest.

The game writes saves and **OMNISPK.CFG** to the current game drawer by default. Keep that drawer writable. The **/USERPATH** option selects another save and config drawer; **/GAMEPATH** selects another game-data drawer. The default audio stream is 22050 Hz, signed 16-bit mono, with 512 samples per SDL block. AHI Unit 0 and the final output mode depend on your AHI settings. **OMNISPK.CFG** can set sampleRate, audioChannels and audioBufferSamples.

## Scope and credits

An earlier build started and played with sound on an A1200 with PiStorm32-Lite and CM4. The current binary includes a joystick-axis fix that has not yet been retested on that hardware. Complete level play, physical save/load, and long-session stability have not been confirmed. Installer 44.10 worked in Intermediate mode; its Expert mode stalled. Use Intermediate mode.

Omnispeak's authors and license are in **AUTHORS** and **LICENSE**. The original upstream README is in **upstream/README**; its other episode and platform instructions do not describe this Amiga build. The release archive contains the engine source and SDL source in its **source** drawer; the installer does not copy that drawer to the game installation. Keen 4 game files are supplied separately by the player. Release and build evidence is recorded in the source repository under docs/.
