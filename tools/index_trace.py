from pathlib import Path
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/index_trace.txt")

TARGETS = {
    "u:I",
    "v:I",
    "w:I",
    "x:I",
    "y:I",
    "z:I",
}


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


def find_interesting_blocks(lines):
    results = []

    for index, line in enumerate(lines):

        # Нас интересуют места, где используются u/v/w/x/y/z
        if not any(f"Field {field}" in line for field in TARGETS):
            continue

        start = max(0, index - 12)
        end = min(len(lines), index + 13)

        context = lines[start:end]

        context_text = "\n".join(context)

        # Ищем признаки арифметики с индексами
        interesting = False

        if "bipush        50" in context_text:
            interesting = True

        if "imul" in context_text:
            interesting = True

        if "iadd" in context_text:
            interesting = True

        if "Field u:I" in context_text and "Field v:I" in context_text:
            interesting = True

        if "Field v:I" in context_text and "putfield" in context_text:
            interesting = True

        if not interesting:
            continue

        results.append({
            "line": index + 1,
            "context": context,
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

    output = []

    output.append("PREHISTORIC TRIBES - INDEX TRACE")
    output.append("Class: c")
    output.append("")
    output.append(
        "Searching for relationships between u/v/w/x/y/z "
        "and arithmetic involving blocks of 50."
    )
    output.append("")

    total = 0

    for method_name, lines in methods:

        blocks = find_interesting_blocks(lines)

        if not blocks:
            continue

        output.append("=" * 80)
        output.append(f"METHOD: {method_name}")
        output.append("=" * 80)

        for block in blocks:

            total += 1

            output.append("")
            output.append(
                f"BYTECODE LINE: {block['line']}"
            )
            output.append("")
            output.append("CONTEXT:")

            for context_line in block["context"]:
                output.append(
                    f"    {context_line}"
                )

            output.append("")

    output.append("=" * 80)
    output.append(
        f"TOTAL INTERESTING BLOCKS: {total}"
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
