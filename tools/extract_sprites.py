#!/usr/bin/env python3

import csv
import struct
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
OUTPUT_DIR = Path("analysis/sprites")
TABLE_DIR = Path("analysis/pd0_tables")
COMMANDS_CSV = Path("analysis/pd0_sprite_commands.csv")

RESOURCES = ["pi0", "pi9", "pi8"]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def extract_pngs(data):
    """Extract PNG images embedded inside a binary resource."""
    images = []
    search_from = 0

    while True:
        start = data.find(PNG_SIGNATURE, search_from)

        if start == -1:
            break

        pos = start + len(PNG_SIGNATURE)
        valid = True

        while pos + 12 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            chunk_type = data[pos + 4:pos + 8]
            chunk_end = pos + 12 + length

            if chunk_end > len(data):
                valid = False
                break

            if chunk_type == b"IEND":
                end = chunk_end
                images.append(data[start:end])
                search_from = end
                break

            pos = chunk_end
        else:
            valid = False

        if not valid:
            search_from = start + 1
        elif not images or search_from <= start:
            search_from = start + 1

    return images


def create_contact_sheet(image_paths, output_path):
    """Create a numbered overview of extracted images."""
    if not image_paths:
        return

    columns = 5
    cell_width = 180
    cell_height = 150
    rows = (len(image_paths) + columns - 1) // columns

    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        (45, 45, 45),
    )
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(image_paths):
        with Image.open(path) as source:
            thumbnail = source.convert("RGBA")
            original_size = thumbnail.size
            thumbnail.thumbnail((cell_width - 12, cell_height - 35))

        x = (index % columns) * cell_width
        y = (index // columns) * cell_height

        background = Image.new(
            "RGBA",
            (cell_width - 8, cell_height - 32),
            (75, 75, 75, 255),
        )
        px = (background.width - thumbnail.width) // 2
        py = (background.height - thumbnail.height) // 2
        background.alpha_composite(thumbnail, (px, py))

        sheet.paste(background.convert("RGB"), (x + 4, y + 4))
        draw.text(
            (x + 5, y + cell_height - 24),
            f"#{index}  {original_size[0]}x{original_size[1]}",
            fill=(255, 255, 255),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def extract_resources():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = {}

    with zipfile.ZipFile(JAR, "r") as jar:
        available = set(jar.namelist())

        for resource in RESOURCES:
            if resource not in available:
                print(f"WARNING: resource /{resource} not found")
                extracted[resource] = []
                continue

            data = jar.read(resource)
            pngs = extract_pngs(data)
            resource_dir = OUTPUT_DIR / resource
            resource_dir.mkdir(parents=True, exist_ok=True)

            paths = []

            for index, png_data in enumerate(pngs):
                path = resource_dir / f"image_{index:03d}.png"
                path.write_bytes(png_data)

                with Image.open(path) as image:
                    image.verify()

                paths.append(path)

            extracted[resource] = paths

            if paths:
                create_contact_sheet(
                    paths,
                    OUTPUT_DIR / f"{resource}_contact_sheet.png",
                )

            print(
                f"/{resource}: {len(data)} bytes, "
                f"{len(paths)} PNG images extracted"
            )

    if not extracted.get("pi0"):
        print(
            "WARNING: No PNG images found in pi0. "
            "The resource format needs further investigation."
        )

    return extracted


def export_command_mapping():
    table_names = ["j_20.csv", "j_21.csv", "j_22.csv",
                   "j_23.csv", "j_24.csv"]
    tables = []

    for name in table_names:
        path = TABLE_DIR / name

        if not path.is_file():
            raise SystemExit(f"ERROR: missing table: {path}")

        with path.open("r", encoding="utf-8", newline="") as file:
            tables.append([
                int(row["unsigned_value"])
                for row in csv.DictReader(file)
            ])

    command_type, source_x, source_y, width, height = tables

    lengths = {len(table) for table in tables}
    if len(lengths) != 1:
        raise SystemExit("ERROR: command tables have different lengths")

    COMMANDS_CSV.parent.mkdir(parents=True, exist_ok=True)

    with COMMANDS_CSV.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "command_index",
            "command_type",
            "image_index",
            "source_x",
            "source_y",
            "width",
            "height",
        ])

        for index in range(len(command_type)):
            kind = command_type[index] & 31

            if kind < 27:
                image_index = kind
                x = source_x[index] & 127
                y = source_y[index]
                w = width[index]
                h = height[index]
            else:
                image_index = ""
                x = source_x[index]
                y = source_y[index]
                w = width[index]
                h = height[index]

            writer.writerow([
                index, kind, image_index, x, y, w, h
            ])

    print(f"Created: {COMMANDS_CSV}")
    print(f"Commands exported: {len(command_type)}")


def main():
    if not JAR.is_file():
        raise SystemExit(f"ERROR: JAR not found: {JAR}")

    extract_resources()
    export_command_mapping()

    print("Sprite extraction and command mapping completed.")


if __name__ == "__main__":
    main()
