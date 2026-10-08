from pathlib import Path
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/record_map.txt")


def find_method_blocks(text):
    lines = text.splitlines()

    methods = []
    current_method = None
    current_lines = []

    method_pattern = re.compile(
        r"^\s*(?:public|private|protected|static|final|"
        r"synchronized|native|abstract|strictfp|\s)*"
        r".+\);$"
    )

    for line in lines:
        if method_pattern.match(line) and not line.startswith(" " * 4):
            if current_method is not None:
                methods.append((current_method, current_lines))

            current_method = line.strip()
            current_lines = [line]

        elif current_method is not None:
            current_lines.append(line)

    if current_method is not None:
        methods.append((current_method, current_lines))

    return methods


def find_v_offsets(lines):
    results = []

    for index in range(len(lines) - 3):

        # Ищем:
        #
        # sipush/bipush <number>
        # aload_0
        # getfield ... // Field v:I
        # iadd
        #
        # Это означает:
        # <number> + v

        line1 = lines[index]
        line2 = lines[index + 1]
        line3 = lines[index + 2]
        line4 = lines[index + 3]

        match = re.search(
            r"\b(?:sipush|bipush|iconst_\d+)\s+(-?\d+)",
            line1
        )

        if not match:
            continue

        if "getfield" not in line2:
            continue

        if "Field v:I" not in line2:
            continue

        if "iadd" not in line3:
            continue

        results.append({
            "offset": int(match.group(1)),
            "line": index + 1,
            "context": lines[max(0, index - 2):min(len(lines), index + 6)]
        })

    return results


def main():
    if not INPUT.exists():
        raise SystemExit(f"File not found: {INPUT}")

    text = INPUT.read_text(
        encoding="utf-8",
        errors="replace"
    )

    methods = find_method_blocks(text)

    all_records = []

    for method_name, lines in methods:

        offsets = find_v_offsets(lines)

        for item in offsets:
            all_records.append({
                "method": method_name,
                "offset": item["offset"],
                "line": item["line"],
                "context": item["context"],
            })

    # Группируем offsets
    grouped = {}

    for item in all_records:
        grouped.setdefault(
            item["offset"],
            []
        ).append(item)

    output = []

    output.append("PREHISTORIC TRIBES - RECORD MAP")
    output.append("Class: c")
    output.append("")
    output.append(
        "Offsets used as BASE + v inside the large byte array a:[B."
    )
    output.append("")
    output.append(
        "The offset itself does not yet have a known semantic meaning."
    )
    output.append("")

    output.append("=" * 80)
    output.append("OFFSET SUMMARY")
    output.append("=" * 80)
    output.append("")

    for offset in sorted(grouped):

        items = grouped[offset]

        methods_used = sorted(
            set(item["method"] for item in items)
        )

        output.append(
            f"OFFSET {offset:5d} + v"
        )

        output.append(
            f"  ACCESS COUNT: {len(items)}"
        )

        output.append(
            "  METHODS: " + ", ".join(methods_used)
        )

        output.append("")

    output.append("=" * 80)
    output.append("DETAILED ACCESS MAP")
    output.append("=" * 80)

    for offset in sorted(grouped):

        output.append("")
        output.append(
            f"OFFSET {offset} + v"
        )
        output.append("-" * 80)

        for item in grouped[offset]:

            output.append("")
            output.append(
                f"METHOD: {item['method']}"
            )

            output.append(
                f"BYTECODE LINE: {item['line']}"
            )

            output.append("")

            for line in item["context"]:
                output.append(
                    f"    {line}"
                )

    output.append("")
    output.append("=" * 80)
    output.append(
        f"TOTAL BASE+v ACCESS EVENTS: {len(all_records)}"
    )
    output.append(
        f"TOTAL UNIQUE OFFSETS: {len(grouped)}"
    )
    output.append("=" * 80)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
