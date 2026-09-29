#!/usr/bin/env python3
import base64
from pathlib import Path
import struct
import zlib


WIDTH = 64
INSTALL_HEIGHT = 40
GAME_HEIGHT = 56
GAME_NUMBER = (
    "   ##  ",
    "  ###  ",
    " ## #  ",
    "##  #  ",
    "#   #  ",
    "#######",
    "    #  ",
    "    #  ",
    "    #  ",
)
GAME_NUMBER_X = 18
GAME_NUMBER_Y = 40
INSTALL_TYPES = ("MINUSER=AVERAGE", "DEFUSER=AVERAGE", "APPNAME=Keen4")
GAME_TYPES = ("WINDOW=CON:0/0/640/100/Keen4/AUTO/CLOSE",)
GLOW_PALETTE = (
    (0, 0, 0), (0, 0, 0), (252, 252, 84), (255, 255, 85),
    (0, 168, 0), (96, 200, 75), (255, 255, 255), (229, 240, 100),
    (239, 239, 239), (168, 84, 0), (168, 168, 168), (168, 168, 167),
    (152, 147, 145), (242, 249, 242), (84, 84, 253), (33, 32, 47),
    (172, 172, 176), (84, 84, 84), (4, 2, 4), (94, 94, 103),
    (92, 72, 78), (216, 216, 186), (98, 126, 153), (168, 0, 168),
    (167, 0, 167), (181, 17, 181), (252, 84, 252), (166, 0, 166),
    (254, 85, 254),
)
GLOW_PIXELS = (
    "c-qaE?UJJ)5Jl6*!Pq(q8W%(6{hxEY0TG=<aHqCv`bT1=Jh#8aTrR)VU~8x8;#!h@2r|"
    "Anr9d><HRg*VU%}F3)mET@bNDwtPaxoyFK;IWR@@0}__RQbzu=PsKjfiI@CgAZ%b)NN-T0"
    "sQLxDZN-Jv{wfv>Q)`V<d<u?2xV{_1d>y%2R>V<sP>$EGE$_6o=Xb)C(#`?^7FJ}r$6*5"
    "`OeI?;EGcLF-Zv%J6#EKlG6z)N;4UGiNgQDyO=dni`p>%b33{6{hN_l3W;ErHWCSq*SJB"
    "(`6<Ib~k9DvBY8@2i*}Z|&sUPqF0i6hO=qCPy-MKV<T)YAruXG5sNdX=*8dIa<6b2ASZi"
    "sv`Uj3dwoP#^u94%YAr$0w@)Akelb$Cy%FO2Ze5UghW(J_QPk+0l?=qMX;>CQr7)IBA7m"
    "a2D*=RR0u!_#re<=`A7JmX@lgNK1~vwd-u@u!}Gj)Jc%R#S+r&&0j(c~&FZlLq=WGEY&7"
    "(q2b%%66Ovgt+GsNy^H?6-b`tnA$%BKniEZ`*wiu9s?<|DCxPi0y-Bu13{y+d;;pW~%k1"
    "{w2;5BaJ-zdOA>CJ0fBwQikefG=!b4(A*93#H(L0mkr{a^WT7W)S(yba$9@a&rBw;u9Jx"
    ")9#-+K)aB@YlSrLG&_k@WSu#=gz+k;fRO*0<HdMGk<BG8#r>mjf5lc#eC4klSClIcsb_"
    "1hWGynRr!s7v;G3596&4"
)
GAME_ROWS = (
    "                        #################                       ",
    "                      ##++#####+     ######                     ",
    "                    ##+++++####+     ####++##                   ",
    "                   #++++++++####+     ####+++#                  ",
    "                  #+++++++++####+     ####++++#.                ",
    "                .#++++++++++######     ####++++##               ",
    "               .#++++++++++++#####     ####++++++#              ",
    "              ##+++++++++++++#####     ####+++++++#             ",
    "              ##+++++++++++++#####     ####+++++++#             ",
    "             #+++++++++++++++#####     ####+++++++##            ",
    "             ##++++++++++++++#####     ####++++++++#            ",
    "             ###+++++++++++++#####     ####++++++++#            ",
    "            ######+++++++++++#####     ####++++++++#            ",
    "            ######+++++++++++#####     ####+++++++++#           ",
    "            ######+++++++++++################+++++++#           ",
    "            ####++++++++++###################+++++++#           ",
    "            ####+++++++++##...............####++++++#           ",
    "            ####++++++++##......       +++.###++++++#           ",
    "            ###+++++++++#...++++++       .+.##++++++#           ",
    "            ###++++++++##..+......     ....+##++++++#           ",
    "            ###++++++++#....+ ##+     + #+..##++++++#           ",
    "            ###++++++++#.. .+###+    .+##+..##++++++#           ",
    "            ###++++++++#..   +++      .++..###++++++#           ",
    "            ##+++++++++#.             .   .###++++++#           ",
    "            ##++##.++++#.          ...    .###+++++#            ",
    "            #+++###++++#.   ##            .###+++++#            ",
    "            #+++###++++#.  # #            .###+++++#            ",
    "            .#++###++++#.  # .###        .####+++++#            ",
    "             #++###++++#.  #  ###.....   .####+++++#            ",
    "             #++###++++##. #.   .#####  .#####+++++#            ",
    "             #++##.++++##.  #       .   .####+++++#             ",
    "             #++++++++###.   #######    .####+++++#             ",
    "              ##++++++####.            .#####+++++#             ",
    "              ##+++++#####..        ...#####+++++#              ",
    "               .#+++### ###..........############.              ",
    "                .####   ###..          #######..                ",
    "                       #+#...         .###  #                   ",
    "                    #####+++.        ..###   #  ##              ",
    "                  ##+++++#++++++++++++#####   #####             ",
    "               .##++++++++##+++++++++#  .##.   ##  #            ",
    "              ##++++++++++++##########.    #.  ##  #            ",
    "             ##+++++++++++++++++++++++#.    #      #            ",
    "            #++++++++++++++++++++++++####.       ##+#           ",
    "           #++++++++++++++++++++++++#   ###      ##++#          ",
    "           #++++++++++++++++++++++++#.           ###+#          ",
    "          #++++++++++++++++++++++++++###            ###         ",
    "         #++++++++++++++++++++++++++++++###     ..  ..##        ",
    "         #++++++++++++++++++++++++++++#....   ....    ##        ",
    "         #++++++++++++#+++++++++++++++#       ....     #        ",
    "        #++++++++++++#++++++++++++++++###.......##      #       ",
    "        #++++++++++++#+++++++++++++++++++########....   #       ",
    "        #+++++++++++#+++++++++++++++++++++++#...........#       ",
    "        #########++#++++++++++++++++++++++++##..........#       ",
    "       #        .##+++++++++++++++++++++++++# ##.......#        ",
    "       #           ####+++++++++++++++++++++#  ########         ",
    "       #               ###++++++++++++++++++#                   ",
)


def add_game_number(pixels, foreground, outline):
    marks = set()
    for row, line in enumerate(GAME_NUMBER):
        for column, pixel in enumerate(line):
            if pixel == "#":
                marks.add((GAME_NUMBER_X + column, GAME_NUMBER_Y + row))
    for x, y in marks:
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                px = x + dx
                py = y + dy
                if (px, py) not in marks and pixels[py][px]:
                    pixels[py][px] = outline
    for x, y in marks:
        pixels[y][x] = foreground


def icon_pixels(install=False):
    if not install:
        colors = {" ": 0, "#": 1, ".": 2, "+": 3}
        pixels = [[colors[pixel] for pixel in row] for row in GAME_ROWS]
        add_game_number(pixels, 2, 1)
        return pixels

    pixels = [[0 for _ in range(WIDTH)] for _ in range(INSTALL_HEIGHT)]

    def rect(x0, y0, x1, y1, color):
        for y in range(y0, y1):
            for x in range(x0, x1):
                pixels[y][x] = color

    shell = ((18, 29), (15, 33), (13, 36), (11, 38), (10, 40),
             (9, 41), (8, 42), (7, 43), (7, 43), (6, 44),
             (6, 44), (6, 43), (7, 43), (8, 42), (9, 41),
             (10, 39), (12, 37), (14, 34), (16, 31))
    for y, (left, right) in enumerate(shell, 2):
        rect(left, y, right, y + 1, 1)
        if y > 3:
            rect(left + 2, y, right - 2, y + 1, 3)

    rect(22, 3, 26, 8, 2)
    rect(23, 8, 27, 17, 2)
    rect(24, 17, 28, 20, 2)
    rect(7, 15, 12, 20, 1)
    rect(8, 16, 12, 18, 2)

    face = ((32, 42), (30, 44), (29, 45), (28, 47),
            (28, 49), (28, 49), (28, 46), (28, 44),
            (29, 43), (30, 42), (31, 41), (32, 40))
    for y, (left, right) in enumerate(face, 18):
        rect(left, y, right, y + 1, 1)
        rect(left + 1, y, right - 1, y + 1, 2)
    rect(40, 20, 43, 23, 1)
    rect(43, 25, 47, 26, 1)
    rect(32, 18, 36, 20, 1)

    rect(10, 17, 24, 29, 1)
    rect(12, 19, 22, 27, 3)
    rect(15, 21, 20, 25, 2)
    rect(19, 27, 23, 34, 1)
    rect(21, 29, 32, 32, 1)
    rect(30, 29, 36, 36, 1)
    rect(31, 30, 34, 35, 2)
    rect(17, 33, 38, 40, 1)
    rect(15, 35, 40, 40, 1)
    rect(18, 35, 37, 40, 3)
    rect(29, 34, 37, 38, 2)
    rect(30, 34, 35, 35, 1)

    rect(57, 4, 63, 27 if install else 36, 1)
    rect(54, 10, 59, 15, 1)
    rect(52, 15, 57, 20, 1)
    rect(50, 20, 55, 26, 1)
    rect(50, 24, 63, 29, 1)
    rect(59, 5, 61, 23, 3)
    rect(55, 12, 57, 15, 3)
    rect(53, 17, 55, 20, 3)
    rect(51, 22, 53, 24, 3)
    rect(52, 25, 61, 27, 3)
    if not install:
        rect(59, 29, 61, 34, 3)

    if install:
        rect(49, 29, 64, 40, 1)
        rect(50, 30, 63, 39, 2)
        rect(55, 30, 58, 33, 3)
        rect(51, 33, 62, 34, 3)
        rect(52, 34, 61, 35, 3)
        rect(53, 35, 60, 36, 3)
        rect(54, 36, 59, 37, 3)
        rect(55, 37, 58, 38, 3)
        rect(56, 38, 57, 39, 3)
    return pixels


def image_data(pixels):
    data = bytearray()
    for plane in (0, 1):
        for row in pixels:
            for start in range(0, WIDTH, 16):
                word = sum(((color >> plane) & 1) << (15 - offset)
                           for offset, color in enumerate(row[start:start + 16]))
                data.extend(struct.pack(">H", word))
    return bytes(data)


def text_field(value):
    encoded = value.encode("ascii") + b"\0"
    return struct.pack(">I", len(encoded)) + encoded


def iff_chunk(name, data):
    chunk = name + struct.pack(">I", len(data)) + data
    return chunk + (b"\0" if len(data) & 1 else b"")


def glow_image(pixels, palette):
    palette_data = b"".join(bytes(color) for color in palette)
    depth = (len(palette) - 1).bit_length()
    header = struct.pack(">BBBBBBHH", 0, len(palette) - 1, 3, 0, 0,
                         depth, len(pixels) - 1, len(palette_data) - 1)
    return iff_chunk(b"IMAG", header + pixels + palette_data)


def glow_icon():
    decoded = zlib.decompress(base64.b85decode(GLOW_PIXELS))
    assert len(decoded) == WIDTH * GAME_HEIGHT
    rows = [list(decoded[y * WIDTH:(y + 1) * WIDTH])
            for y in range(GAME_HEIGHT)]
    add_game_number(rows, 2, 1)
    normal = bytes(pixel for row in rows for pixel in row)
    selected = bytearray(normal)
    selected_palette = GLOW_PALETTE + ((255, 184, 0), (255, 240, 96))
    outer = len(GLOW_PALETTE)
    inner = outer + 1
    for y in range(GAME_HEIGHT):
        for x in range(WIDTH):
            offset = y * WIDTH + x
            if normal[offset]:
                continue
            near_inner = any(
                0 <= x + dx < WIDTH and 0 <= y + dy < GAME_HEIGHT and
                normal[(y + dy) * WIDTH + x + dx]
                for dy in range(-1, 2) for dx in range(-1, 2)
            )
            near_outer = any(
                0 <= x + dx < WIDTH and 0 <= y + dy < GAME_HEIGHT and
                normal[(y + dy) * WIDTH + x + dx]
                for dy in range(-2, 3) for dx in range(-2, 3)
            )
            if near_inner:
                selected[offset] = inner
            elif near_outer:
                selected[offset] = outer
    face = struct.pack(">BBBBH", WIDTH - 1, GAME_HEIGHT - 1, 0, 0,
                       len(selected_palette) * 3 - 1)
    body = (b"ICON" + iff_chunk(b"FACE", face) +
            glow_image(normal, GLOW_PALETTE) +
            glow_image(selected, selected_palette))
    return b"FORM" + struct.pack(">I", len(body)) + body


def create_icon(install=False):
    tooltypes = INSTALL_TYPES if install else GAME_TYPES
    default_tool = "C:Installer" if install else "C:IconX"
    stack = 65536 if install else 262144
    height = INSTALL_HEIGHT if install else GAME_HEIGHT
    gadget = struct.pack(">IhhhhHHHIIIIIHI", 0, 0, 0, WIDTH, height,
                         0x0005, 0x0003, 0x0001, 1, 0, 0, 0, 0, 0, 0)
    assert len(gadget) == 44
    header = (struct.pack(">HH", 0xE310, 1) + gadget +
              struct.pack(">BBIIiiIII", 4, 0, 1, 1,
                          -2147483648, -2147483648, 0, 0, stack))
    assert len(header) == 78
    image = struct.pack(">hhhhhIBBI", 0, 0, WIDTH, height, 2, 1, 3, 0, 0)
    data = header + image + image_data(icon_pixels(install))
    data += text_field(default_tool)
    data += (struct.pack(">I", 4 * (len(tooltypes) + 1)) +
             b"".join(text_field(value) for value in tooltypes))
    if not install:
        data += glow_icon()
    return data


if __name__ == "__main__":
    Path(__file__).with_name("Install.info").write_bytes(create_icon(True))
    Path(__file__).with_name("Start-Keen4.info").write_bytes(create_icon())
