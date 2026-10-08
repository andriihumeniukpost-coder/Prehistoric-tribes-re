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


def find_method_blocks(text):
    """
    Разделяет javap-файл на методы.
    Возвращает список:
        (method_name, method_body)
    """

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

        # javap показывает начало метода примерно так:
        #
        # private void a();
        # final int b(int);
        #
        # Нас интересуют строки, заканчивающиеся на );
        if method_pattern.match(line) and not line.startswith(" " * 4):
            if current_method is not None:
                methods.append(
                    (current_method, current_lines)
                )

            current_method = line.strip()
            current_lines = [line]

        elif current_method is not None:
            current_lines.append(line)

    if current_method is not None:
        methods.append(
            (current_method, current_lines)
        )

    return methods


def find_field_operations(lines):
    """
    Ищет getfield/putfield для целевых полей.
    """

    results = []

    for index, line in enumerate(lines):

        if (
            "getfield" not in line
            and "putfield" not in line
            and "getstatic" not in line
            and "putstatic" not in line
        ):
            continue

        match = re.search(
            r"//\s*Field\s+([A-Za-z0-9_$]+):(.+)$",
            line
        )

        if not match:
            continue

        field_name = match.group(1)
        field_type = match.group(2).strip()

        field_id = f"{field_name}:{field_type}"

        if field_id not in TARGET_FIELDS:
            continue

        operation = "UNKNOWN"

        if "getfield" in line:
            operation = "READ"

        elif "putfield" in line:
            operation = "WRITE"

        elif "getstatic" in line:
            operation = "STATIC READ"

        elif "putstatic" in line:
            operation = "STATIC WRITE"

        start = max(0, index - 8)
        end = min(len(lines), index + 9)

        context = lines[start:end]

        results.append({
            "field": field_id,
            "operation": operation,
            "line": index + 1,
            "context": context,
        })

    return results


def main():

    if not INPUT.exists():
        raise SystemExit(
            f"File not found: {INPUT}"
        )

    text = INPUT.read_text(
        encoding="utf-8",
        errors="replace"
    )

    methods = find_method_blocks(text)

    output = []

    output.append(
        "PREHISTORIC TRIBES - FIELD TRACE"
    )
    output.append(
        "Class: c"
    )
    output.append("")
    output.append(
        "Tracing important integer fields."
    )
    output.append(
        "Context: 8 lines before and 8 lines after each access."
    )
    output.append("")

    total = 0

    for method_name, lines in methods:

        operations = find_field_operations(lines)

        if not operations:
            continue

        output.append(
            "=" * 80
        )
        output.append(
            f"METHOD: {method_name}"
        )
        output.append(
            "=" * 80
        )

        for item in operations:

            total += 1

            output.append("")
            output.append(
                f"FIELD: {item['field']}"
            )
            output.append(
                f"OPERATION: {item['operation']}"
            )
            output.append(
                f"BYTECODE LINE: {item['line']}"
            )
            output.append("")
            output.append(
                "CONTEXT:"
            )

            for context_line in item["context"]:
                output.append(
                    f"    {context_line}"
                )

            output.append("")

    output.append("=" * 80)
    output.append(
        f"TOTAL FIELD ACCESS EVENTS: {total}"
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

    print(
        f"Created: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
