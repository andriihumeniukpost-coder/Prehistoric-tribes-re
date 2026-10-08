#!/usr/bin/env python3

import re
from pathlib import Path

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/method_map.txt")


def main():
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found")
        return

    text = INPUT.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    methods = []
    current = None

    for line in lines:
        # Method declaration
        m = re.match(
            r"\s{2}(public|private|protected|static|final|native|synchronized|abstract).*"
            r"\s([a-zA-Z_$][\w$]*)\(([^)]*)\);?",
            line,
        )

        if m and "Method" not in line:
            current = {
                "name": m.group(2),
                "signature": line.strip(),
                "calls": [],
            }
            methods.append(current)
            continue

        # javap bytecode call
        if current:
            call = re.search(
                r"// (?:Method|InterfaceMethod) ([^ ]+)\.([^\(:]+):",
                line
            )

            if call:
                owner = call.group(1)
                name = call.group(2)

                current["calls"].append(
                    f"{owner}.{name}"
                )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", encoding="utf-8") as out:
        out.write("PREHISTORIC TRIBES - METHOD MAP\n")
        out.write("=" * 70 + "\n\n")

        for method in methods:
            out.write(f"{method['signature']}\n")

            unique_calls = []
            for call in method["calls"]:
                if call not in unique_calls:
                    unique_calls.append(call)

            if unique_calls:
                out.write("  calls:\n")
                for call in unique_calls:
                    out.write(f"    -> {call}\n")
            else:
                out.write("  calls: none\n")

            out.write("\n")

    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
