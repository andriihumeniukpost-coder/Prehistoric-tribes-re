#!/usr/bin/env python3

import csv
import zipfile
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
OUTPUT_DIR = Path("analysis/sprites")
TABLE_DIR = Path("analysis/pd0_tables")
COMMANDS_CSV = Path("analysis/pd0_sprite_commands.csv")

# Число записей, используемое загрузчиком оригинальной игры.
RESOURCE_COUNTS = {
    "pi0": 31,
    "pi9": 6,
    "pi8": 12,
}

# Оригинальный загрузчик f.d() создаёт Image только для индексов 0–26.
GAME_IMAGE_LIMITS = {
    "pi0": 27,
    "pi9": 27,
    "pi8": 1,
}


def parse_resource(data, expected_count):
    """Разобрать ресурс по формату загрузчика Java ME.

    Запись:
      1 байт — старшая часть длины;
      0xFF — конец последовательности;
      1 байт — младшая часть длины;
      N байт — данные изображения.
    """
    records = []
    pos = 0

    for index in range(expected_count):
        if pos >= len(data):
            print(f"WARNING: ресурс закончился перед записью #{index}")
            break

        high = data[pos]
        pos += 1

        if high == 0xFF:
            print(f"Маркер конца найден перед записью #{index}")
            break

        if pos >= len(data):
            print(f"WARNING: отсутствует младший байт длины #{index}")
            break

        low = data[pos]
        pos += 1

        length = (high << 8) | low

        if length == 0:
            print(f"WARNING: запись #{index} имеет нулевую длину")
            records.append((index, b"", pos))
            continue

        end = pos + length

        if end > len(data):
            print(
                f"WARNING: запись #{index} выходит за границы ресурса: "
                f"offset={pos}, length={length}, size={len(data)}"
            )
            break

        records.append((index, data[pos:end], pos))
        pos = end

    return records, pos


def decode_image(raw_data):
    """Попытаться декодировать изображение через Pillow."""
    try:
        with Image.open(BytesIO(raw_data)) as source:
            source.load()
            return source.convert("RGBA"), source.format
    except Exception:
        return None, None


def create_contact_sheet(image_paths, output_path):
    """Создать нумерованный лист изображений."""
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
            f"{path.stem} {original_size[0]}x{original_size[1]}",
            fill=(255, 255, 255),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def extract_resources():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}

    with zipfile.ZipFile(JAR, "r") as jar:
        available = set(jar.namelist())

        for resource, expected_count in RESOURCE_COUNTS.items():
            if resource not in available:
                print(f"WARNING: resource /{resource} not found in JAR")
                summary[resource] = {
                    "records": 0,
                    "decoded": 0,
                    "missing": True,
                }
                continue

            data = jar.read(resource)
            records, consumed = parse_resource(data, expected_count)

            resource_dir = OUTPUT_DIR / resource
            resource_dir.mkdir(parents=True, exist_ok=True)

            decoded_paths = []
            manifest_path = resource_dir / "manifest.csv"

            with manifest_path.open(
                "w", encoding="utf-8", newline=""
            ) as file:
                writer = csv.writer(file)
                writer.writerow([
                    "index",
                    "offset",
                    "length",
                    "detected_format",
                    "decoded",
                    "used_by_original_loader",
                    "raw_file",
                    "png_file",
                ])

                decoded_count = 0

                for index, raw_data, offset in records:
                    stem = f"image_{index:03d}"
                    raw_path = resource_dir / f"{stem}.bin"

                    # Сохраняем исходные байты без изменений.
                    raw_path.write_bytes(raw_data)

                    image, image_format = decode_image(raw_data)
                    png_path = ""

                    if image is not None:
                        png_file = f"{stem}.png"
                        png_path_obj = resource_dir / png_file
                        image.save(png_path_obj, format="PNG")
                        decoded_paths.append(png_path_obj)
                        png_path = png_file
                        decoded_count += 1

                    writer.writerow([
                        index,
                        offset,
                        len(raw_data),
                        image_format or "unknown",
                        image is not None,
                        index < GAME_IMAGE_LIMITS[resource],
                        raw_path.name,
                        png_path,
                    ])

                    print(
                        f"/{resource} #{index}: "
                        f"{len(raw_data)} bytes, "
                        f"format={image_format or 'unknown'}, "
                        f"decoded={image is not None}, "
                        f"game_uses_index="
                        f"{index < GAME_IMAGE_LIMITS[resource]}"
                    )

            if decoded_paths:
                create_contact_sheet(
                    decoded_paths,
                    OUTPUT_DIR / f"{resource}_contact_sheet.png",
                )

            summary[resource] = {
                "records": len(records),
                "decoded": decoded_count,
                "missing": False,
            }

            print(
                f"/{resource}: {len(data)} bytes; "
                f"{len(records)} records; "
                f"{decoded_count} decoded; "
                f"parsed through byte {consumed}"
            )

    return summary


def export_command_mapping():
    table_names = [
        "j_20.csv",
        "j_21.csv",
        "j_22.csv",
        "j_23.csv",
        "j_24.csv",
    ]

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

    if len({len(table) for table in tables}) != 1:
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

        for index, raw_kind in enumerate(command_type):
            kind = raw_kind & 31

            if kind < 27:
                image_index = kind
                x = source_x[index] & 127
            else:
                image_index = ""
                x = source_x[index]

            writer.writerow([
                index,
                kind,
                image_index,
                x,
                source_y[index],
                width[index],
                height[index],
            ])

    print(f"Created: {COMMANDS_CSV}")
    print(f"Commands exported: {len(command_type)}")


def main():
    if not JAR.is_file():
        raise SystemExit(f"ERROR: JAR not found: {JAR}")

    summary = extract_resources()
    export_command_mapping()

    print("\n=== Extraction summary ===")
    for resource, result in summary.items():
        if result["missing"]:
            print(f"/{resource}: MISSING")
        else:
            print(
                f"/{resource}: records={result['records']}, "
                f"decoded={result['decoded']}"
            )

    print("\nExtraction and command mapping completed.")


if __name__ == "__main__":
    main()
