from pathlib import Path
from collections import Counter, defaultdict
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/array_access.txt")

TARGET_OFFSETS = [0, 101, 2828, 2929, 3131, 3232, 4444]

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\s*(.*?)\s*$"
)

FIELD_RE = re.compile(
    r"// Field ([^:]+):([^\s]+)"
)

MAX_EXAMPLES = 15


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def parse_instructions(text):
    methods = []
    current_method = "(unknown method)"
    current = []

    for line in text.splitlines():
        stripped = line.strip()

        # javap method declarations end with ); or )V etc.
        if (
            stripped.endswith(";")
            and "(" in stripped
            and not stripped.startswith("//")
            and not stripped.startswith("descriptor:")
            and not stripped.startswith("Signature:")
            and not INSTRUCTION_RE.match(line)
        ):
            if current:
                methods.append((current_method, current))
                current = []

            current_method = stripped
            continue

        match = INSTRUCTION_RE.match(line)

        if match:
            offset = int(match.group(1))
            opcode = match.group(2)
            operand = match.group(3)

            current.append({
                "offset": offset,
                "opcode": opcode,
                "operand": operand,
                "raw": line.rstrip(),
            })

    if current:
        methods.append((current_method, current))

    return methods


def const_from_opcode(opcode, operand):
    if opcode == "iconst_m1":
        return -1

    if re.fullmatch(r"iconst_[0-5]", opcode):
        return int(opcode[-1])

    if opcode in ("bipush", "sipush"):
        match = re.match(r"(-?\d+)", operand)

        if match:
            return int(match.group(1))

    return None


def local_from_opcode(opcode):
    match = re.fullmatch(
        r"[ailfd]load(?:_(\d+))?",
        opcode,
    )

    if not match:
        return None

    if match.group(1) is not None:
        return int(match.group(1))

    return -1


def is_branch(opcode):
    return (
        opcode.startswith("if")
        or opcode in {
            "goto", "goto_w",
            "tableswitch", "lookupswitch",
            "jsr", "jsr_w",
            "ireturn", "lreturn", "freturn",
            "dreturn", "areturn", "return",
            "athrow",
        }
    )


def is_target_index(expression):
    if not isinstance(expression, tuple):
        return None

    if len(expression) != 3 or expression[0] != "add":
        return None

    left, right = expression[1], expression[2]

    candidates = [(left, right), (right, left)]

    for constant, variable in candidates:
        if (
            isinstance(constant, tuple)
            and constant[0] == "const"
            and isinstance(variable, tuple)
            and variable == ("field", "v:I")
        ):
            value = constant[1]

            if value in TARGET_OFFSETS:
                return value

    return None


def field_expression(operand):
    match = FIELD_RE.search(operand)

    if not match:
        return ("field", "unknown")

    name = match.group(1)
    descriptor = match.group(2)

    if name == "a" and descriptor == "[B":
        return ("array", "a:[B")

    if name == "v" and descriptor == "I":
        return ("field", "v:I")

    return ("field", f"{name}:{descriptor}")


def simulate_method(method_name, instructions):
    stack = []
    accesses = []

    def pop():
        if stack:
            return stack.pop()

        return ("unknown",)

    def push(value):
        stack.append(value)

    def record_access(operation, array_expr, index_expr, instruction):
        if array_expr != ("array", "a:[B"):
            return

        target = is_target_index(index_expr)

        if target is None:
            return

        accesses.append({
            "method": method_name,
            "offset": target,
            "operation": operation,
            "line": instruction["offset"],
            "expression": index_expr,
            "instruction": instruction["raw"],
        })

    for instruction in instructions:
        opcode = instruction["opcode"]
        operand = instruction["operand"]

        value = const_from_opcode(opcode, operand)

        if value is not None:
            push(("const", value))
            continue

        if opcode in ("aconst_null",):
            push(("null",))
            continue

        if opcode.startswith(("aload", "iload", "lload",
                              "fload", "dload")):
            local = local_from_opcode(opcode)

            if local is None:
                push(("local", opcode))
            else:
                push(("local", local))

            continue

        if opcode in ("getfield", "getstatic"):
            expression = field_expression(operand)

            if opcode == "getfield":
                pop()

            push(expression)
            continue

        if opcode in ("iadd", "ladd"):
            right = pop()
            left = pop()
            push(("add", left, right))
            continue

        if opcode in ("isub", "lsub"):
            right = pop()
            left = pop()
            push(("sub", left, right))
            continue

        if opcode in ("imul", "lmul"):
            right = pop()
            left = pop()
            push(("mul", left, right))
            continue

        if opcode in ("idiv", "ldiv", "irem", "lrem"):
            right = pop()
            left = pop()
            push((opcode, left, right))
            continue

        if opcode in ("ineg", "lneg"):
            push(("neg", pop()))
            continue

        if opcode in (
            "i2b", "i2c", "i2s",
            "i2l", "i2f", "i2d",
            "l2i", "f2i", "d2i",
        ):
            push((opcode, pop()))
            continue

        if opcode in ("baload", "caload", "saload",
                      "iaload", "laload", "faload",
                      "daload", "aaload"):
            index_expr = pop()
            array_expr = pop()

            if opcode == "baload":
                record_access(
                    "READ",
                    array_expr,
                    index_expr,
                    instruction,
                )

            push(("loaded", opcode))
            continue

        if opcode in ("bastore", "castore", "sastore",
                      "iastore", "lastore", "fastore",
                      "dastore", "aastore"):
            value_expr = pop()
            index_expr = pop()
            array_expr = pop()

            if opcode == "bastore":
                record_access(
                    "WRITE",
                    array_expr,
                    index_expr,
                    instruction,
                )

            continue

        if opcode == "dup":
            first = pop()
            push(first)
            push(first)
            continue

        if opcode == "dup_x1":
            first = pop()
            second = pop()
            push(first)
            push(second)
            push(first)
            continue

        if opcode == "dup2":
            if len(stack) >= 2:
                first = stack[-2]
                second = stack[-1]
                push(first)
                push(second)
            elif stack:
                push(stack[-1])
            continue

        if opcode == "pop":
            pop()
            continue

        if opcode == "pop2":
            pop()
            pop()
            continue

        if opcode == "swap":
            first = pop()
            second = pop()
            push(first)
            push(second)
            continue

        if opcode.startswith("invoke"):
            # Method descriptors determine argument counts.
            # Without a complete descriptor-aware JVM stack model,
            # discard the current stack to avoid false attribution.
            stack.clear()

            if opcode != "invokestatic":
                # The receiver and arguments were discarded together.
                pass

            if opcode == "invokestatic":
                if " )" in operand:
                    pass

            # Return values are not reconstructed here.
            continue

        if opcode in ("new", "newarray", "anewarray"):
            if opcode != "new":
                pop()

            push(("object", opcode))
            continue

        if opcode == "arraylength":
            pop()
            push(("length",))
            continue

        if opcode in ("checkcast", "instanceof"):
            original = pop()
            push((opcode, original))
            continue

        if opcode in ("iinc",):
            continue

        # Branch targets change control flow. A linear scan cannot
        # safely carry one stack state into the next basic block.
        if is_branch(opcode):
            stack.clear()
            continue

        # Unknown instructions invalidate the current stack model.
        # Continue at the next instruction with a clean stack.
        stack.clear()

    return accesses


def main():
    text = read_text(INPUT)
    methods = parse_instructions(text)

    all_accesses = []

    for method_name, instructions in methods:
        all_accesses.extend(
            simulate_method(method_name, instructions)
        )

    counts = Counter()
    method_sets = defaultdict(set)
    examples = defaultdict(list)

    for access in all_accesses:
        key = (access["offset"], access["operation"])
        counts[key] += 1
        method_sets[key].add(access["method"])

        if len(examples[key]) < MAX_EXAMPLES:
            examples[key].append(access)

    output = [
        "PREHISTORIC TRIBES - ARRAY ACCESS ANALYSIS",
        "Class: c",
        "",
        "Analysis type: symbolic operand-stack pattern matching",
        "Target: a[offset + v]",
        "",
        "IMPORTANT:",
        "This is a partial JVM stack simulation, not a full verifier.",
        "Unknown instructions and branches reset the symbolic stack.",
        "Only matches with array a:[B and index offset + v are reported.",
        "A missing match does not prove that an access does not exist.",
        "",
        "=" * 80,
        "SUMMARY",
        "=" * 80,
        "",
        f"PARSED METHODS: {len(methods)}",
        f"CONFIRMED PATTERN MATCHES: {len(all_accesses)}",
        "",
    ]

    for offset in TARGET_OFFSETS:
        output.extend([
            "=" * 80,
            f"OFFSET {offset} + v",
            "=" * 80,
            "",
        ])

        for operation in ("READ", "WRITE"):
            key = (offset, operation)

            output.append(f"{operation} MATCHES: {counts[key]}")
            output.append(
                f"METHODS: {len(method_sets[key])}"
            )

            for number, access in enumerate(
                examples[key],
                start=1,
            ):
                output.append("")
                output.append(
                    f"EXAMPLE {number} | "
                    f"{access['method']} | "
                    f"BYTECODE OFFSET {access['line']}"
                )
                output.append(
                    f"    OPERATION: {access['operation']}"
                )
                output.append(
                    f"    INDEX: {access['offset']} + v"
                )
                output.append(
                    f"    INSTRUCTION: {access['instruction']}"
                )

            output.append("")

    output.extend([
        "=" * 80,
        "METHOD SUMMARY",
        "=" * 80,
        "",
    ])

    by_method = defaultdict(list)

    for access in all_accesses:
        by_method[access["method"]].append(access)

    for method_name in sorted(by_method):
        output.append(method_name)

        summary = Counter(
            (item["offset"], item["operation"])
            for item in by_method[method_name]
        )

        for (offset, operation), count in sorted(summary.items()):
            output.append(
                f"    {operation:5s} {offset:5d} + v"
                f"    occurrences: {count}"
            )

        output.append("")

    output.extend([
        "=" * 80,
        "LIMITATIONS",
        "=" * 80,
        "",
        "1. The JVM operand stack is simulated only partially.",
        "2. Branches and unknown instructions reset the stack.",
        "3. Calls and complex stack manipulation may hide accesses.",
        "4. Only byte-array instructions baload and bastore are counted.",
        "5. Array offsets have no automatic semantic meaning.",
        "",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8",
    )

    print(f"Created: {OUTPUT}")
    print(f"Parsed methods: {len(methods)}")
    print(f"Pattern matches: {len(all_accesses)}")


if __name__ == "__main__":
    main()
