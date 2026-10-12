
#!/usr/bin/env python3

import csv
import struct
import zipfile
from pathlib import Path

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
OUTPUT = Path("analysis/pd0_graphics.txt")
CSV_DIR = Path("analysis/pd0_tables")

SIZES = [
    119, 1292, 162, 162, 2782, 146, 1071, 6903, 823, 1731, 5559,
    119, 1292, 1292, 1292, 162, 162, 162, 2782, 2782, 146,
    1071, 1071, 6903, 6903, 6903, 823, 1731, 42, 5559, 5559,
    1832, 1832, 1832, 1832, 1832,
]


def signed_byte(value):
    return value if value < 128 else value - 256


def main():
    if not JAR.exists():
        raise SystemExit(f"JAR not found: {JAR}")

    with zipfile.ZipFile(JAR) as jar:
        data = jar.read("pd0")

    if len(data) != 97417:
        raise SystemExit(
            f"Unexpected /pd0 size: {len(data)} bytes; expected 97417"
        )

    # f.b() skips the first byte of /pd0.
    pos = 1
    short_tables = []
    byte_tables = []

    for row in range(11):
        count = SIZES[row]
        length = count * 2
        chunk = data[pos:pos + length]
        if len(chunk) != length:
            raise SystemExit(f"Truncated short table {row}")
        values = list(struct.unpack(f">{count}h", chunk))
        short_tables.append(values)
        pos += length

    for row in range(25):
        count = SIZES[11 + row]
        chunk = data[pos:pos + count]
        if len(chunk) != count:
            raise SystemExit(f"Truncated byte table {row}")
        byte_tables.append([signed_byte(x) for x in chunk])
        pos += count

    if pos != len(data):
        raise SystemExit(
            f"Parser consumed {pos} of {len(data)} bytes"
        )

    CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Export every table as a CSV: index,value.
    for row, values in enumerate(short_tables):
        with (CSV_DIR / f"b_{row}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["index", "signed_value", "unsigned_value"])
            for i, value in enumerate(values):
                writer.writerow([i, value, value & 0xFFFF])

    for row, values in enumerate(byte_tables):
        with (CSV_DIR / f"j_{row}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["index", "signed_value", "unsigned_value"])
            for i, value in enumerate(values):
                writer.writerow([i, value, value & 0xFF])

    b9 = short_tables[9]
    b10 = short_tables[10]
    j16 = byte_tables[16]
    j18 = byte_tables[18]
    j19 = byte_tables[19]
    j20 = byte_tables[20]
    j21 = byte_tables[21]
    j22 = byte_tables[22]
    j23 = byte_tables[23]
    j24 = byte_tables[24]

    with OUTPUT.open("w", encoding="utf-8") as out:
        out.write("PREHISTORIC TRIBES — /pd0 GRAPHICS DUMP\n")
        out.write("=" * 64 + "\n\n")
        out.write(f"Resource size: {len(data)} bytes\n")
        out.write(f"Parser consumed: {pos} bytes\n\n")

        out.write("TABLE SIZES\n")
        out.write("-" * 64 + "\n")
        for i, values in enumerate(short_tables):
            out.write(f"b[{i}]: {len(values)} shorts\n")
        for i, values in enumerate(byte_tables):
            out.write(f"j[{i}]: {len(values)} bytes\n")

        out.write("\nMAIN TABLE: b[9] AND j[16]\n")
        out.write("-" * 64 + "\n")
        out.write(
            "record,b9_raw,b9_index,b9_flags,"
            "j16_signed,j16_unsigned,count_low6\n"
        )

        for i, raw in enumerate(b9):
            out.write(
                f"{i},{raw},{raw & 8191},"
                f"{(raw & 0xFFFF) >> 14},"
                f"{j16[i]},{j16[i] & 255},{(j16[i] & 255) & 63}\n"
            )

        out.write("\nSECONDARY TABLE: b[10]\n")
        out.write("-" * 64 + "\n")
        out.write(
            "record,b10_raw,index_low13,bit13,upper2,extra_128,"
            "j18_offset,j19_offset\n"
        )

        for i, raw in enumerate(b10):
            unsigned = raw & 0xFFFF
            out.write(
                f"{i},{raw},{unsigned & 8191},"
                f"{(unsigned >> 13) & 1},"
                f"{(unsigned >> 14) & 3},"
                f"{((unsigned >> 14) & 3) * 128},"
                f"{j18[i]},{j19[i]}\n"
            )

        out.write("\nDRAW COMMAND TABLE: j[20]–j[24]\n")
        out.write("-" * 64 + "\n")
        out.write(
            "record,j20_signed,j20_unsigned,type_low5,"
            "j21_signed,j21_unsigned,j22,j23,j24\n"
        )

        for i in range(len(j20)):
            j20u = j20[i] & 255
            j21u = j21[i] & 255
            out.write(
                f"{i},{j20[i]},{j20u},{j20u & 31},"
                f"{j21[i]},{j21u},{j22[i]},{j23[i]},{j24[i]}\n"
            )

    print(f"Created: {OUTPUT}")
    print(f"Created CSV tables in: {CSV_DIR}")


if __name__ == "__main__":
    main()
