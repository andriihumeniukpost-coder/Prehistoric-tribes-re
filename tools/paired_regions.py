
from pathlib import Path
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/paired_regions.txt")

TARGET_OFFSETS = (3131, 3232)

BEFORE = 8
AFTER = 12

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\s*(.*?)\s*$"
)

METHOD_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|static|final|"
    r"synchronized|native|abstract|strictfp)\s+)+"
    r".+\([^;]*\);\s*$"
)


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def parse_methods(text):
    methods = []
    current_name = None
    current_instructions = []

    def save_current():
        if current_name is not None and current_instructions:
            methods.append({
                "name": current_name,
                "instructions": list(current_instructions),
            })

    for line in text.splitlines():
        stripped = line.strip()

        if METHOD_RE.match(line) and not INSTRUCTION_RE.match(line):
            save_current()
            current_name = stripped
            current_instructions = []
            continue

        match = INSTRUCTION_RE.match(line)

        if match and current_name is not None:
            current_instructions.append({
                "pc": int(match.group(1)),
                "op": match.group(2),
                "arg": match.group(3),
                "raw": line.rstrip(),
            })

    save_current()
    return methods


def is_v_field(instruction):
    return (
        instruction["op"] in ("getfield", "getstatic")
        and "// Field v:I" in instruction["arg"]
    )


def find_offset_uses(instructions, target):
    """
    Find candidate expressions shaped like:

        sipush TARGET
        aload_0
        getfield ... // Field v:I
        iadd

    The result is a candidate expression, not a semantic
    interpretation of the array region.
    """
    results = []

    for index, instruction in enumerate(instructions):
        if instruction["op"] not in ("sipush", "bipush"):
            continue

        if not re.match(
            rf"^{target}(?:\s|$)",
            instruction["arg"]
        ):
            continue

        end = min(len(instructions), index + 7)
        window = instructions[index:end]

        v_positions = [
            index + local_index
            for local_index, item in enumerate(window)
            if is_v_field(item)
        ]

        for v_index in v_positions:
            add_index = next(
                (
                    j for j in range(v_index + 1, end)
                    if instructions[j]["op"] == "iadd"
                ),
                None
            )

            if add_index is None:
                continue

            results.append({
                "target": target,
                "start": index,
                "end": add_index,
                "pc": instruction["pc"],
            })
            break

    return results


def method_region_data(method):
    instructions = method["instructions"]

    uses = {
        target: find_offset_uses(instructions, target)
        for target in TARGET_OFFSETS
    }

    return {
        "name": method["name"],
        "instructions": instructions,
        "uses": uses,
        "has_3131": bool(uses[3131]),
        "has_3232": bool(uses[3232]),
    }


def render_context(method_data, use, number):
    instructions = method_data["instructions"]

    start = max(0, use["start"] - BEFORE)
    end = min(
        len(instructions),
        use["end"] + AFTER + 1
    )

    output = [
        "-" * 80,
        f"CONTEXT #{number}",
        f"METHOD: {method_data['name']}",
        f"TARGET: {use['target']} + v",
        f"START BYTECODE PC: {use['pc']}",
        "",
    ]

    for index in range(start, end):
        instruction = instructions[index]

        if index == use["start"]:
            marker = " >>> "
        elif index == use["end"]:
            marker = " <<< "
        else:
            marker = "     "

        output.append(marker + instruction["raw"])

    output.extend([
        "",
        ">>> marks the start of the candidate expression.",
        "<<< marks the iadd that may complete the index.",
        "Check the surrounding stack operations before",
        "concluding whether this is a read or a write.",
        "",
    ])

    return output


def main():
    text = read_text(INPUT)
    methods = parse_methods(text)
    analyzed = [
        method_region_data(method)
        for method in methods
    ]

    both = [
        item for item in analyzed
        if item["has_3131"] and item["has_3232"]
    ]

    only_3131 = [
        item for item in analyzed
        if item["has_3131"] and not item["has_3232"]
    ]

    only_3232 = [
        item for item in analyzed
        if item["has_3232"] and not item["has_3131"]
    ]

    output = [
        "PREHISTORIC TRIBES - PAIRED ARRAY REGION ANALYSIS",
        "Class: c",
        "",
        "Targets:",
        "  a[3131 + v]",
        "  a[3232 + v]",
        "",
        "PURPOSE",
        "Find methods that reference both target expressions and",
        "show nearby bytecode for manual inspection.",
        "",
        "IMPORTANT LIMITATIONS",
        "This script searches for a constant, Field v:I, and iadd.",
        "It does not fully simulate the JVM operand stack.",
        "It does not prove the final array index or access type.",
        "No semantic names are assigned to these regions.",
        "",
        "=" * 80,
        "SUMMARY",
        "=" * 80,
        f"PARSED METHODS: {len(methods)}",
        f"METHODS USING BOTH REGIONS: {len(both)}",
        f"METHODS USING ONLY 3131 + v: {len(only_3131)}",
        f"METHODS USING ONLY 3232 + v: {len(only_3232)}",
        "",
        "=" * 80,
        "METHODS USING BOTH REGIONS",
        "=" * 80,
        "",
    ]

    if not both:
        output.append(
            "No methods matching both candidate expressions were found."
        )
        output.append(
            "Check the bytecode format and method parser."
        )
        output.append("")

    context_number = 0

    for item in both:
        count_3131 = len(item["uses"][3131])
        count_3232 = len(item["uses"][3232])

        output.extend([
            "-" * 80,
            f"METHOD: {item['name']}",
            f"3131 + v CANDIDATES: {count_3131}",
            f"3232 + v CANDIDATES: {count_3232}",
            "",
        ])

        for target in TARGET_OFFSETS:
            for use in item["uses"][target]:
                context_number += 1
                output.extend(
                    render_context(item, use, context_number)
                )

    output.extend([
        "=" * 80,
        "METHODS USING ONLY 3131 + v",
        "=" * 80,
        "",
    ])

    for item in only_3131:
        output.append(
            f"{item['name']} "
            f"(candidates: {len(item['uses'][3131])})"
        )

    output.extend([
        "",
        "=" * 80,
        "METHODS USING ONLY 3232 + v",
        "=" * 80,
        "",
    ])

    for item in only_3232:
        output.append(
            f"{item['name']} "
            f"(candidates: {len(item['uses'][3232])})"
        )

    output.extend([
        "",
        "=" * 80,
        "FINAL NOTES",
        "=" * 80,
        "1. A method using both regions is a useful investigation lead.",
        "2. Nearby bytecode must be checked to identify real accesses.",
        "3. A bastore writes a byte; a baload reads a byte.",
        "4. The exact meaning of every field remains unconfirmed.",
        "",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    print(f"Created: {OUTPUT}")
    print(f"Parsed methods: {len(methods)}")
    print(f"Methods using both regions: {len(both)}")
    print(f"Methods using only 3131 + v: {len(only_3131)}")
    print(f"Methods using only 3232 + v: {len(only_3232)}")


if __name__ == "__main__":
    main()
