
import csv
import json
import zipfile
from pathlib import Path

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
RESOURCE = "a"

OUT_DIR = Path("analysis/a_dump")
RECORD_COUNT = 312
EXPECTED_BLOB_SIZE = 17770


def read_u16(data, pos):
    """Read an unsigned 16-bit little-endian integer."""
    if pos + 2 > len(data):
        raise ValueError(
            f"Unexpected end of resource at offset {pos}"
        )

    return data[pos] | (data[pos + 1] << 8), pos + 2


def parse_resource(data):
    pos = 0
    blob = bytearray()
    records = []

    # Parse 312 records: 2-byte length followed by payload.
    for index in range(RECORD_COUNT):
        length, pos = read_u16(data, pos)
        offset = len(blob)

        if pos + length > len(data):
            raise ValueError(
                f"Record {index}: length {length} exceeds "
                f"resource bounds (offset={pos}, "
                f"resource_size={len(data)})"
            )

        payload = data[pos:pos + length]
        blob.extend(payload)

        records.append({
            "index": index,
            "offset": offset,
            "length": length,
            "hex": payload.hex(),
            "bytes": list(payload),
        })

        pos += length

    if len(blob) != EXPECTED_BLOB_SIZE:
        raise ValueError(
            f"Blob size mismatch: got {len(blob)}, "
            f"expected {EXPECTED_BLOB_SIZE}. "
            "The resource format may need further analysis."
        )

    # Parse five additional groups.
    groups = []
    cumulative = 0

    for group_index in range(5):
        count, pos = read_u16(data, pos)
        values = []

        for _ in range(count):
            value, pos = read_u16(data, pos)
            values.append(value)

        groups.append({
            "index": group_index,
            "offset": cumulative,
            "count": count,
            "values": values,
        })

        cumulative += count

    if pos != len(data):
        raise ValueError(
            f"Parser consumed {pos} of {len(data)} bytes; "
            f"{len(data) - pos} trailing bytes remain"
        )

    return bytes(blob), records, groups


def main():
    if not JAR.is_file():
        raise FileNotFoundError(
            f"JAR not found: {JAR}\n"
            "Run this script from the repository root."
        )

    with zipfile.ZipFile(JAR) as jar:
        try:
            data = jar.read(RESOURCE)
        except KeyError:
            raise FileNotFoundError(
                "Resource '/a' was not found in the original JAR"
            )

    print(f"JAR: {JAR}")
    print(f"Resource size: {len(data)} bytes")
    print(f"First 32 bytes: {data[:32].hex(' ')}")

    blob, records, groups = parse_resource(data)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "a_blob.bin").write_bytes(blob)

    with (OUT_DIR / "a_records.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "offset", "length", "hex"],
        )
        writer.writeheader()

        for record in records:
            writer.writerow({
                "index": record["index"],
                "offset": record["offset"],
                "length": record["length"],
                "hex": record["hex"],
            })

    result = {
        "resource_size": len(data),
        "blob_size": len(blob),
        "records": records,
        "groups": groups,
        "record_154": records[154],
        "offset_154": records[154]["offset"],
    }

    (OUT_DIR / "a_dump.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    record = records[154]

    print()
    print("=== Record 154 ===")
    print(f"Offset: {record['offset']}")
    print(f"Length: {record['length']}")
    print(f"Bytes: {record['hex']}")

    print()
    print("=== Additional groups ===")
    print(f"Group sizes: {[g['count'] for g in groups]}")
    print(f"Output directory: {OUT_DIR}")


if __name__ == "__main__":
    main()
