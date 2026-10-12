
from pathlib import Path
from collections import Counter, defaultdict
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/array_access.txt")

TARGET_OFFSETS = [0, 101, 2828, 2929, 3131, 3232, 4444]
MAX_EXAMPLES = 20

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\s*(.*?)\s*$"
)
FIELD_RE = re.compile(r"// Field ([^:]+):([^\s]+)")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def parse_methods(text):
    methods = []
    name = "(unknown method)"
    instructions = []

    for line in text.splitlines():
        stripped = line.strip()

        if (
            stripped.endswith(";")
            and "(" in stripped
            and not stripped.startswith(
                ("//", "descriptor:", "Signature:")
            )
            and not INSTRUCTION_RE.match(line)
        ):
            if instructions:
                methods.append((name, instructions))
                instructions = []
            name = stripped
            continue

        match = INSTRUCTION_RE.match(line)
        if match:
            instructions.append({
                "pc": int(match.group(1)),
                "op": match.group(2),
                "arg": match.group(3),
                "raw": line.rstrip(),
            })

    if instructions:
        methods.append((name, instructions))

    return methods


def constant_value(op, arg):
    if op == "iconst_m1":
        return -1

    if re.fullmatch(r"iconst_[0-5]", op):
        return int(op[-1])

    if op in ("bipush", "sipush"):
        match = re.match(r"-?\d+", arg)
        if match:
            return int(match.group())

    return None


def field_name(arg):
    match = FIELD_RE.search(arg)
    if not match:
        return None
    return f"{match.group(1)}:{match.group(2)}"


def index_offset(expr):
    if not isinstance(expr, tuple) or len(expr) != 3:
        return None

    if expr[0] != "add":
        return None

    for constant, variable in (
        (expr[1], expr[2]),
        (expr[2], expr[1]),
    ):
        if (
            isinstance(constant, tuple)
            and constant[0] == "const"
            and variable == ("field", "v:I")
        ):
            if constant[1] in TARGET_OFFSETS:
                return constant[1]

    return None


def analyse_method(method_name, instructions):
    stack = []
    results = []

    def pop():
        return stack.pop() if stack else ("unknown",)

    def push(value):
        stack.append(value)

    def record(kind, array, index, value, instruction):
        if array != ("array", "a:[B"):
            return

        base = index_offset(index)
        if base is None:
            return

        results.append({
            "method": method_name,
            "offset": base,
            "operation": kind,
            "pc": instruction["pc"],
            "value": value,
            "instruction": instruction["raw"],
        })

    for ins in instructions:
        op = ins["op"]
        arg = ins["arg"]
        number = constant_value(op, arg)

        if number is not None:
            push(("const", number))
            continue

        if op in ("aload_0", "aload_1", "aload_2", "aload_3",
                  "iload_0", "iload_1", "iload_2", "iload_3",
                  "lload_0", "lload_1", "lload_2", "lload_3",
                  "fload_0", "fload_1", "fload_2", "fload_3",
                  "dload_0", "dload_1", "dload_2", "dload_3"):
            push(("local", op))
            continue

        if op in ("aload", "iload", "lload", "fload", "dload"):
            push(("local", arg.strip()))
            continue

        if op in ("getfield", "getstatic"):
            field = field_name(arg)

            if op == "getfield":
                pop()

            if field == "a:[B":
                push(("array", "a:[B"))
            elif field == "v:I":
                push(("field", "v:I"))
            elif field:
                push(("field", field))
            else:
                push(("unknown",))
            continue

        if op in ("iadd", "ladd", "isub", "lsub",
                  "imul", "lmul", "idiv", "ldiv"):
            right = pop()
            left = pop()
            operation = {
                "iadd": "add", "ladd": "add",
                "isub": "sub", "lsub": "sub",
                "imul": "mul", "lmul": "mul",
                "idiv": "div", "ldiv": "div",
            }[op]
            push((operation, left, right))
            continue

        if op in ("i2b", "i2c", "i2s", "i2l", "i2f",
                  "i2d", "l2i", "f2i", "d2i", "ineg"):
            push((op, pop()))
            continue

        if op == "dup":
            value = pop()
            push(value)
            push(value)
            continue

        if op == "swap":
            first = pop()
            second = pop()
            push(first)
            push(second)
            continue

        if op == "baload":
            index = pop()
            array = pop()
            record("READ", array, index, None, ins)
            push(("loaded-byte",))
            continue

        if op == "bastore":
            value = pop()
            index = pop()
            array = pop()
            record("WRITE", array, index, value, ins)
            continue

        if op in ("pop", "pop2"):
            pop()
            if op == "pop2":
                pop()
            continue

        if op.startswith("invoke"):
            # Calls have variable stack effects. Do not guess their
            # arguments or return values in this partial analyzer.
            stack.clear()
            continue

        # Branches, unsupported instructions and complex operations
        # invalidate the symbolic stack to avoid stale conclusions.
        stack.clear()

    return results


def describe_value(value):
    if value is None:
        return "not applicable"

    if isinstance(value, tuple):
        if len(value) == 2 and value[0] == "const":
            return f"constant {value[1]}"

        if len(value) == 2 and value[0] == "field":
            return f"field {value[1]}"

        if len(value) == 2 and value[0] == "local":
            return f"local {value[1]}"

        if value[0] in ("i2b", "i2c", "i2s", "i2l",
                        "i2f", "i2d", "l2i", "f2i",
                        "d2i", "ineg"):
            return f"{value[0]}({describe_value(value[1])})"

        if value[0] in ("add", "sub", "mul", "div"):
            return (
                f"{describe_value(value[1])} {value[0]} "
                f"{describe_value(value[2])}"
            )

        return repr(value)

    return str(value)


def main():
    methods = parse_methods(read_text(INPUT))
    all_results = []

    for name, instructions in methods:
        all_results.extend(analyse_method(name, instructions))

    counts = Counter()
    method_sets = defaultdict(set)
    examples = defaultdict(list)
    written_values = defaultdict(Counter)

    for item in all_results:
        key = (item["offset"], item["operation"])
        counts[key] += 1
        method_sets[key].add(item["method"])

        if len(examples[key]) < MAX_EXAMPLES:
            examples[key].append(item)

        if item["operation"] == "WRITE":
            written_values[item["offset"]][
                describe_value(item["value"])
            ] += 1

    out = [
        "PREHISTORIC TRIBES - ARRAY ACCESS AND WRITE VALUE ANALYSIS",
        "Class: c",
        "",
        "Target: a[offset + v]",
        "This is partial symbolic analysis, not a complete JVM interpreter.",
        "Reported values are symbolic candidates, not game semantics.",
        "",
        f"PARSED METHODS: {len(methods)}",
        f"TOTAL MATCHES: {len(all_results)}",
        "",
    ]

    for base in TARGET_OFFSETS:
        out.extend(["=" * 80, f"OFFSET {base} + v", "=" * 80, ""])

        for operation in ("READ", "WRITE"):
            key = (base, operation)
            out.append(f"{operation} MATCHES: {counts[key]}")
            out.append(f"METHODS: {len(method_sets[key])}")

            for i, item in enumerate(examples[key], 1):
                out.append("")
                out.append(
                    f"EXAMPLE {i} | {item['method']} | PC {item['pc']}"
                )
                out.append(f"    INSTRUCTION: {item['instruction']}")

                if operation == "WRITE":
                    out.append(
                        "    VALUE CANDIDATE: "
                        + describe_value(item["value"])
                    )

            out.append("")

        out.append("WRITE VALUE SUMMARY")
        if written_values[base]:
            for value, count in written_values[base].most_common():
                out.append(f"    {value}: {count}")
        else:
            out.append("    No recognized writes")
        out.append("")

    out.extend([
        "=" * 80,
        "LIMITATIONS",
        "=" * 80,
        "1. Unknown JVM instructions reset the symbolic stack.",
        "2. Method calls and branches may hide valid accesses.",
        "3. A value candidate may be incomplete if stack state was lost.",
        "4. Numeric values do not establish what a game field means.",
        "",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"Created: {OUTPUT}")
    print(f"Parsed methods: {len(methods)}")
    print(f"Matches: {len(all_results)}")


if __name__ == "__main__":
    main()
