#!/usr/bin/env python3
from pathlib import Path
import struct


WIDTH = 64
HEIGHT = 40
INSTALL_TYPES = ("MINUSER=AVERAGE", "DEFUSER=AVERAGE", "APPNAME=Keen4")
GAME_TYPES = ("WINDOW=CON:0/0/640/100/Keen4/AUTO/CLOSE",)


def icon_pixels(install=False):
    pixels = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]

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


def create_icon(install=False):
    tooltypes = INSTALL_TYPES if install else GAME_TYPES
    default_tool = "C:Installer" if install else "C:IconX"
    stack = 65536 if install else 262144
    gadget = struct.pack(">IhhhhHHHIIIIIHI", 0, 0, 0, WIDTH, HEIGHT,
                         0x0005, 0x0003, 0x0001, 1, 0, 0, 0, 0, 0, 0)
    assert len(gadget) == 44
    header = (struct.pack(">HH", 0xE310, 1) + gadget +
              struct.pack(">BBIIiiIII", 4, 0, 1, 1,
                          -2147483648, -2147483648, 0, 0, stack))
    assert len(header) == 78
    image = struct.pack(">hhhhhIBBI", 0, 0, WIDTH, HEIGHT, 2, 1, 3, 0, 0)
    data = header + image + image_data(icon_pixels(install))
    data += text_field(default_tool)
    data += (struct.pack(">I", 4 * (len(tooltypes) + 1)) +
             b"".join(text_field(value) for value in tooltypes))
    return data


if __name__ == "__main__":
    Path(__file__).with_name("Install.info").write_bytes(create_icon(True))
    Path(__file__).with_name("Start-Keen4.info").write_bytes(create_icon())
