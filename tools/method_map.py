#!/usr/bin/env python3

import re
from pathlib import Path

INPUT_DIR = Path("analysis/bytecode")
OUTPUT_DIR = Path("analysis/method_maps")


def parse_methods(text):
    lines = text.splitlines()

    methods = []
    current = None

    for line in lines:
        # Method declaration
        m = re.match(
            r"\s{2}"
            r"(?:(?:public|private|protected|static|final|native|synchronized|abstract)\s+)+"
            r".*?\s([a-zA-Z_$][\w$]*)\(([^)]*)\);",
            line,
        )

        if m and "Method" not in line:
            current = {
                "name": m.group(1),
                "signature": line.strip(),
                "calls": [],
            }
            methods.append(current)
            continue

        if current:
            call = re.search(
                r"// (?:Method|InterfaceMethod) ([^ ]+)\.([^\(:]+):",
                line,
            )

            if call:
                owner = call.group(1)
                name = call.group(2)

                current["calls"].append(
                    f"{owner}.{name}"
                )

    return methods


def write_map(output_file, class_name, methods):
    with output_file.open("w", encoding="utf-8") as out:

        out.write(
            f"PREHISTORIC TRIBES - METHOD MAP: {class_name}\n"
        )
        out.write("=" * 70 + "\n\n")

        for method in methods:

            out.write(
                f"{method['signature']}\n"
            )

            unique_calls = []

            for call in method["calls"]:
                if call not in unique_calls:
                    unique_calls.append(call)

            if unique_calls:
                out.write("  calls:\n")

                for call in unique_calls:
                    out.write(
                        f"    -> {call}\n"
                    )

            else:
                out.write(
                    "  calls: none\n"
                )

            out.write("\n")


def main():

    if not INPUT_DIR.exists():
        print(
            f"ERROR: {INPUT_DIR} not found"
        )
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        INPUT_DIR.glob("*.txt")
    )

    if not files:
        print(
            f"ERROR: no .txt files found in {INPUT_DIR}"
        )
        return

    print(
        f"Found {len(files)} bytecode files."
    )

    for input_file in files:

        class_name = input_file.stem

        print(
            f"Processing {class_name}..."
        )

        text = input_file.read_text(
            encoding="utf-8",
            errors="replace"
        )

        methods = parse_methods(text)

        output_file = (
            OUTPUT_DIR /
            f"{class_name}.txt"
        )

        write_map(
            output_file,
            class_name,
            methods
        )

        print(
            f"  -> {output_file}"
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
