from pathlib import Path
import re

INPUT = Path("analysis/field_map.txt")
OUTPUT = Path("analysis/hot_fields.txt")


def parse_fields(text):
    fields = []

    blocks = re.split(r"\n(?=FIELD: )", text)

    for block in blocks:
        field_match = re.search(r"^FIELD: (.+)$", block, re.MULTILINE)
        type_match = re.search(r"^TYPE: (.+)$", block, re.MULTILINE)
        read_match = re.search(r"^READ: (.*)$", block, re.MULTILINE)
        write_match = re.search(r"^WRITE: (.*)$", block, re.MULTILINE)

        if not field_match:
            continue

        field = field_match.group(1).strip()
        field_type = type_match.group(1).strip() if type_match else "?"
        reads = []

        if read_match and read_match.group(1).strip():
            reads = [
                x.strip()
                for x in read_match.group(1).split(",")
                if x.strip()
            ]

        writes = []

        if write_match and write_match.group(1).strip():
            writes = [
                x.strip()
                for x in write_match.group(1).split(",")
                if x.strip()
            ]

        fields.append({
            "field": field,
            "type": field_type,
            "reads": reads,
            "writes": writes,
        })

    return fields


def main():
    if not INPUT.exists():
        raise SystemExit(f"File not found: {INPUT}")

    text = INPUT.read_text(encoding="utf-8")
    fields = parse_fields(text)

    # Уникальные методы, использующие поле
    for item in fields:
        item["read_count"] = len(set(item["reads"]))
        item["write_count"] = len(set(item["writes"]))
        item["method_count"] = len(
            set(item["reads"]) | set(item["writes"])
        )

    # Самые используемые поля
    by_methods = sorted(
        fields,
        key=lambda x: (
            -x["method_count"],
            -x["read_count"],
            -x["write_count"],
        ),
    )

    # Самые часто изменяемые поля
    by_writes = sorted(
        fields,
        key=lambda x: (
            -x["write_count"],
            -x["method_count"],
        ),
    )

    # Большие/сложные массивы
    arrays = [
        x for x in fields
        if x["type"].startswith("[")
    ]

    arrays.sort(
        key=lambda x: -x["method_count"]
    )

    lines = []

    lines.append("PREHISTORIC TRIBES - HOT FIELDS")
    lines.append("Class: c")
    lines.append("")
    lines.append(
        "Fields ranked by number of unique methods using them."
    )
    lines.append("")

    lines.append("=" * 80)
    lines.append("MOST USED FIELDS")
    lines.append("=" * 80)

    for rank, item in enumerate(by_methods[:30], 1):
        lines.append(
            f"{rank:2}. "
            f"{item['field']:8} "
            f"{item['type']:8} "
            f"methods={item['method_count']:3} "
            f"reads={item['read_count']:3} "
            f"writes={item['write_count']:3}"
        )

    lines.append("")
    lines.append("=" * 80)
    lines.append("MOST WRITTEN FIELDS")
    lines.append("=" * 80)

    for rank, item in enumerate(by_writes[:30], 1):
        lines.append(
            f"{rank:2}. "
            f"{item['field']:8} "
            f"{item['type']:8} "
            f"writes={item['write_count']:3} "
            f"methods={item['method_count']:3}"
        )

    lines.append("")
    lines.append("=" * 80)
    lines.append("MOST USED ARRAYS")
    lines.append("=" * 80)

    for rank, item in enumerate(arrays[:30], 1):
        lines.append(
            f"{rank:2}. "
            f"{item['field']:8} "
            f"{item['type']:8} "
            f"methods={item['method_count']:3} "
            f"reads={item['read_count']:3} "
            f"writes={item['write_count']:3}"
        )

    lines.append("")
    lines.append("=" * 80)
    lines.append("IMPORTANT")
    lines.append("=" * 80)
    lines.append(
        "High usage does NOT automatically mean a field's meaning is known."
    )
    lines.append(
        "This report is used to choose which fields to investigate first."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
