from pathlib import Path
import re

INPUT = Path("analysis/field_map.txt")
OUTPUT = Path("analysis/field_usage.txt")


IMPORTANT_FIELDS = [
    ("v", "I"),
    ("u", "I"),
    ("w", "I"),
    ("x", "I"),
    ("z", "I"),
    ("y", "I"),
    ("A", "I"),
    ("C", "I"),
    ("R", "I"),
    ("a", "[B"),
    ("a", "[S"),
    ("b", "[B"),
    ("b", "[[B"),
    ("a", "[[S"),
    ("b", "[S"),
    ("a", "Lg;"),
]


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

    wanted = set(IMPORTANT_FIELDS)

    selected = [
        item for item in fields
        if (item["field"], item["type"]) in wanted
    ]

    lines = []

    lines.append("PREHISTORIC TRIBES - FIELD USAGE")
    lines.append("Class: c")
    lines.append("")
    lines.append(
        "Detailed usage of the most important fields."
    )
    lines.append("")

    for item in selected:
        lines.append("=" * 80)
        lines.append(
            f"FIELD: {item['field']}"
        )
        lines.append(
            f"TYPE:  {item['type']}"
        )
        lines.append("")

        lines.append(
            f"READ COUNT:  {len(set(item['reads']))}"
        )
        lines.append(
            f"WRITE COUNT: {len(set(item['writes']))}"
        )
        lines.append("")

        lines.append("READ BY:")

        if item["reads"]:
            for method in sorted(set(item["reads"])):
                lines.append(f"  {method}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("WRITE BY:")

        if item["writes"]:
            for method in sorted(set(item["writes"])):
                lines.append(f"  {method}")
        else:
            lines.append("  (none)")

        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
