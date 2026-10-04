# Keen 4 for AmigaOS 68k

Commander Keen 4 v1.4 EGA for AmigaOS 68k
> [!NOTE]
> currently built only for **68040/FPU, RTG and AHI**. Tested on Pistorm, other accelerators **may** work.

0.1.0: gameplay, sound, joystick and save/load work on an A1200 with PiStorm32-Lite and CM4.

Reports and feedback welcome, please include your hardware and any problems you encounter

You can join the [Emu68 Hatcher Discord](https://discord.com/invite/ApTbasXJPE) for that :)

## Required game files

> [!IMPORTANT]
> **Game data is not included in the Amiga package.** Download the [Commander Keen 4 v1.4 EGA shareware archive (4keen14.zip)](https://davidgow.net/keen/4keen14.zip) separately. This build requires that version; the GT software version is NOT compatible

Only these three files are needed from the ZIP:

| File | Size in bytes |
| --- | ---: |
| AUDIO.CK4 | 33,325 |
| EGAGRAPH.CK4 | 520,581 |
| GAMEMAPS.CK4 | 99,040 |

With the installer, select the 4keen14.zip as downloaded. It extracts these files and checks their sizes. For a manual installation you can extract them yourself and copy them into  the game drawer, beside **omnispeak**. The other support files are already included in the Amiga package.

## Install

Choose either method below

### Installer

Requires [Installer 43.3+](https://aminet.net/package/util/misc/Installer-43_3), Unzip and IconX on the Amiga, plus about 700 kB free in T:

1. Extract **keen4-0.1.0.lha**
2. Doubleblick **Install** and choose **Intermediate User**. Select a parent drawer; the installer creates **Keen4** inside it.
3. Select the downloaded **4keen14.zip**, without extracting it first. Unzip is detected automatically, or you will be asked for its location
4. Open **Keen4** and double-click **Start-Keen4**.

### Manual

Requires tools to extract LHA and ZIP archives, either on the Amiga or another computer. Installer is not needed. IconX is only needed to start the game by doubleclicking its icon

1. Extract **keen4-0.1.0.lha** into a writable drawer on your Amiga, or extract it elsewhere and copy the drawer over. Keep the program and its support files together.
2. Extract **AUDIO.CK4**, **EGAGRAPH.CK4** and **GAMEMAPS.CK4** from **4keen14.zip** and copy them beside **omnispeak**.
3. Double-click **Start-Keen4**, or open a Shell in the game drawer and run **Execute Start-Keen4**. Use **Execute Start-Keen4-NoSound** to start without audio.

## Controls

| Action     | Keyboard   | Joystick |
| ---------- | ---------- | -------- |
| Move       | Arrow keys | Joystick |
| Jump       | Ctrl       | Button 0 |
| Pogo       | Alt        | Button 1 |
| Fire       | Space      | Button 2 |
| Menu       | Esc        | Button 3 |
| Status     | Enter      | Button 4 |
| Quick-save | F5         | Button 5 |
| Quick-load | F9         | Button 6 |

For two-button firing, open Main Menu > Configure > Options and set **Two-Button Firing** to **ON**.

Joysticks and gamepads with more than two buttons have not been tested.

## Sound settings

Sound uses **AHI Unit 0** by default, at 22050 Hz in mono. Audio settings can be changed in **OMNISPK.CFG**:

```ini
sampleRate = 22050 # sample rate in Hz
audioChannels = 1 # no. of channels (1 = mono  2 = stereo)
audioBufferSamples = 512 # buffer size
```

The buffer size is measured in samples. A larger buffer may reduce audio dropouts but increases latency.

## Credits

Based on [Omnispeak](https://github.com/sulix/omnispeak). See **AUTHORS** and **LICENSE** for credits and licensing, and **upstream/README** for original documentation.

The release archive includes engine and SDL source in **source/**.
