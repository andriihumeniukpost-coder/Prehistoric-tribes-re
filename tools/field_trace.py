from pathlib import Path
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/field_trace.txt")

TARGET_FIELDS = {
    "v:I",
    "u:I",
    "w:I",
    "x:I",
    "y:I",
    "z:I",
}

METHOD_PATTERN = re.compile(
    r"^\s{2}"
    r"(?:(?:public|private|protected|static|final|"
    r"synchronized|native|abstract|strictfp)\s+)+"
    r".+\([^;]*\);$"
)

FIELD_PATTERN = re.compile(
    r"//\s*Field\s+([A-Za-z0-9_$]+):([^\s]+)"
)


def is_method_declaration(line):
    """Определяет строку объявления метода в выводе javap."""
    return bool(METHOD_PATTERN.match(line))


def find_method_blocks(text):
    """Разбивает вывод javap на блоки методов."""
    methods = []
    current_name = None
    current_lines = []

    for line in text.splitlines():
        if is_method_declaration(line):
            if current_name is not None:
                methods.append((current_name, current_lines))

            current_name = line.strip()
            current_lines = [line]

        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        methods.append((current_name, current_lines))

    return methods


def find_field_operations(lines):
    """Находит чтение и запись целевых полей."""
    results = []

    for index, line in enumerate(lines):
        match = FIELD_PATTERN.search(line)

        if not match:
            continue

        field_name = match.group(1)
        field_type = match.group(2)
        field_id = f"{field_name}:{field_type}"

        if field_id not in TARGET_FIELDS:
            continue

        if "getfield" in line:
            operation = "READ"
        elif "putfield" in line:
            operation = "WRITE"
        elif "getstatic" in line:
            operation = "STATIC READ"
        elif "putstatic" in line:
            operation = "STATIC WRITE"
        else:
            continue

        start = max(0, index - 8)
        end = min(len(lines), index + 9)

        results.append({
            "field": field_id,
            "operation": operation,
            "line": index + 1,
            "context": lines[start:end],
        })

    return results


def main():
    if not INPUT.exists():
        raise SystemExit(f"ERROR: Input file not found: {INPUT}")

    text = INPUT.read_text(
        encoding="utf-8",
        errors="replace"
    )

    if not text.strip():
        raise SystemExit(
            f"ERROR: Input file is empty: {INPUT}"
        )

    methods = find_method_blocks(text)

    output = [
        "PREHISTORIC TRIBES - FIELD TRACE",
        "Class: c",
        "",
        "Target fields: u, v, w, x, y, z",
        "Context: 8 lines before and after each access.",
        "",
        f"INPUT LINES: {len(text.splitlines())}",
        f"METHODS FOUND: {len(methods)}",
        "",
    ]

    total = 0
    totals = {
        field: {"READ": 0, "WRITE": 0,
                "STATIC READ": 0, "STATIC WRITE": 0}
        for field in sorted(TARGET_FIELDS)
    }

    for method_name, lines in methods:
        operations = find_field_operations(lines)

        if not operations:
            continue

        output.extend([
            "=" * 80,
            f"METHOD: {method_name}",
            "=" * 80,
            "",
        ])

        for item in operations:
            total += 1
            totals[item["field"]][item["operation"]] += 1

            output.extend([
                f"FIELD: {item['field']}",
                f"OPERATION: {item['operation']}",
                f"BYTECODE LINE: {item['line']}",
                "",
                "CONTEXT:",
            ])

            output.extend(
                f"    {line}" for line in item["context"]
            )
            output.append("")

    output.extend([
        "=" * 80,
        "SUMMARY",
        "=" * 80,
        "",
    ])

    for field in sorted(TARGET_FIELDS):
        counts = totals[field]
        field_total = sum(counts.values())

        output.append(
            f"{field}: total={field_total}, "
            f"reads={counts['READ'] + counts['STATIC READ']}, "
            f"writes={counts['WRITE'] + counts['STATIC WRITE']}"
        )

    output.extend([
        "",
        f"TOTAL FIELD ACCESS EVENTS: {total}",
        f"METHODS FOUND: {len(methods)}",
        "=" * 80,
        "",
    ])

    if total == 0:
        output.extend([
            "WARNING: No target field accesses were detected.",
            "Check the javap format and field descriptors.",
            "",
        ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(output), encoding="utf-8")

    print(f"Created: {OUTPUT}")
    print(f"Input lines: {len(text.splitlines())}")
    print(f"Methods found: {len(methods)}")
    print(f"Field access events: {total}")

    if total == 0:
        raise SystemExit(
            "ERROR: No field accesses detected. "
            "Inspect the generated report before continuing."
        )


if __name__ == "__main__":
    main()
