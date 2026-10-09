
#!/usr/bin/env python3
"""Symbolically trace byte-array reads and writes in javap reports.

Input:
    analysis/bytecode/*.txt

Output:
    analysis/array_field_trace.txt

The interpreter tracks symbolic JVM operand-stack values. It is deliberately
conservative: unsupported instructions clear the symbolic stack to avoid
inventing array/index relationships.
"""

from collections import Counter, defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "analysis" / "bytecode"
OUTPUT_FILE = ROOT / "analysis" / "array_field_trace.txt"

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\b(.*?)\s*$"
)
FIELD_RE = re.compile(
    r"//\s*Field\s+([A-Za-z_$][\w$]*):([^\s]+)"
)
METHOD_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|static|final|synchronized|native|abstract|strictfp)\s+)+"
    r".*\([^;]*\);\s*$"
)

ARRAY_LOADS = {
    "iaload", "laload", "faload", "daload",
    "aaload", "baload", "caload", "saload",
}
ARRAY_STORES = {
    "iastore", "lastore", "fastore", "dastore",
    "aastore", "bastore", "castore", "sastore",
}

BINARY_ARITHMETIC = {
    "iadd", "ladd", "fadd", "dadd",
    "isub", "lsub", "fsub", "dsub",
    "imul", "lmul", "fmul", "dmul",
    "idiv", "ldiv", "fdiv", "ddiv",
    "irem", "lrem", "frem", "drem",
    "iand", "land", "ior", "lor", "ixor", "lxor",
    "ishl", "lshl", "ishr", "lshr", "iushr", "lushr",
}
UNARY_ARITHMETIC = {
    "ineg", "lneg", "fneg", "dneg",
    "i2l", "i2f", "i2d", "l2i", "l2f", "l2d",
    "f2i", "f2l", "f2d", "d2i", "d2l", "d2f",
    "i2b", "i2c", "i2s",
}


def field_ref(instruction):
    match = FIELD_RE.search(instruction["operand"])
    if not match:
        return None
    return match.group(1), match.group(2)


def integer_constant(instruction):
    op = instruction["opcode"]
    operand = instruction["operand"].strip()

    if op.startswith("iconst_"):
        value = op[len("iconst_"):]
        if value == "m1":
            return -1
        if value.isdigit():
            return int(value)

    if op in ("bipush", "sipush"):
        match = re.match(r"^-?\d+", operand)
        if match:
            return int(match.group(0))

    if op in ("ldc", "ldc_w"):
        match = re.search(r"//\s*int\s+(-?\d+)\b", operand)
        if match:
            return int(match.group(1))

    return None


def parse_methods(path):
    methods = []
    current = None

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()

            if METHOD_RE.match(line) and not stripped.startswith("//"):
                current = {
                    "file": path.name,
                    "signature": stripped,
                    "instructions": [],
                }
                methods.append(current)
                continue

            match = INSTRUCTION_RE.match(line)
            if match and current is not None:
                current["instructions"].append({
                    "offset": int(match.group(1)),
                    "opcode": match.group(2),
                    "operand": match.group(3).strip(),
                })

    return methods


def sym_const(value):
    return ("const", value)


def sym_field(owner, name, descriptor):
    return ("field", owner, name, descriptor)


def sym_expr(op, left, right=None):
    return ("expr", op, left, right)


def describe(value):
    if not isinstance(value, tuple):
        return repr(value)

    kind = value[0]

    if kind == "const":
        return str(value[1])

    if kind == "this":
        return "this"

    if kind == "local":
        return f"local{value[1]}"

    if kind == "field":
        return f"{value[1]}.{value[2]}:{value[3]}"

    if kind == "expr":
        op, left, right = value[1], value[2], value[3]
        if right is None:
            return f"({op} {describe(left)})"
        return f"({describe(left)} {op} {describe(right)})"

    if kind == "array":
        return f"array({describe(value[1])})"

    if kind == "element":
        return f"element({describe(value[1])}, {describe(value[2])})"

    if kind == "unknown":
        return "?"

    return str(value)


def is_byte_array_a(value):
    return (
        isinstance(value, tuple)
        and value[0] == "field"
        and value[2] == "a"
        and value[3] == "[B"
    )


def find_constant_plus_v(index_value):
    """Return base if index is exactly CONSTANT + this.v."""
    if not isinstance(index_value, tuple) or index_value[0] != "expr":
        return None

    _, op, left, right = index_value
    if op != "iadd":
        return None

    candidates = ((left, right), (right, left))
    for constant_side, field_side in candidates:
        if (
            isinstance(constant_side, tuple)
            and constant_side[0] == "const"
            and isinstance(constant_side[1], int)
            and isinstance(field_side, tuple)
            and field_side[0] == "field"
            and field_side[1] == "this"
            and field_side[2] == "v"
            and field_side[3] == "I"
        ):
            return constant_side[1]

    return None


def descriptor_arguments(descriptor):
    """Count JVM method parameters in a descriptor such as (II[BI)V."""
    if not descriptor.startswith("("):
        return None

    end = descriptor.find(")")
    if end < 0:
        return None

    text = descriptor[1:end]
    count = 0
    i = 0

    while i < len(text):
        while i < len(text) and text[i] == "[":
            i += 1

        if i >= len(text):
            return None

        if text[i] == "L":
            semicolon = text.find(";", i)
            if semicolon < 0:
                return None
            i = semicolon + 1
        else:
            i += 1

        count += 1

    return count


def descriptor_return(descriptor):
    end = descriptor.find(")")
    if end < 0 or end + 1 >= len(descriptor):
        return None
    return descriptor[end + 1:]


def method_ref(operand):
    match = re.search(
        r"//\s*(?:InterfaceMethod|Method)\s+"
        r"[^:]+:(\([^)]*\).+)$",
        operand,
    )
    if match:
        return match.group(1)

    # invokedynamic normally displays a call-site descriptor differently.
    match = re.search(r":(\([^)]*\).+)$", operand)
    if match:
        return match.group(1)

    return None


def local_index(opcode, operand):
    match = re.fullmatch(r"(?:[ilfda])load_(\d+)", opcode)
    if match:
        return int(match.group(1))

    match = re.fullmatch(r"(?:[ilfda])store_(\d+)", opcode)
    if match:
        return int(match.group(1))

    if opcode in (
        "iload", "lload", "fload", "dload", "aload",
        "istore", "lstore", "fstore", "dstore", "astore",
    ):
        match = re.match(r"(\d+)", operand)
        if match:
            return int(match.group(1))

    return None


def pop(stack):
    return stack.pop() if stack else ("unknown",)


def push_unknown(stack):
    stack.append(("unknown",))


def simulate(method):
    stack = []
    events = []
    instructions = method["instructions"]

    for pos, ins in enumerate(instructions):
        op = ins["opcode"]
        operand = ins["operand"]
        offset = ins["offset"]

        # Constants
        constant = integer_constant(ins)
        if constant is not None:
            stack.append(sym_const(constant))
            continue

        if op in ("aconst_null",):
            stack.append(("null",))
            continue

        if op.startswith(("lconst_", "fconst_", "dconst_")):
            stack.append(("constant", op))
            continue

        # Local variables
        local = local_index(op, operand)
        if op.startswith(("aload", "iload", "lload", "fload", "dload")):
            if op == "aload_0":
                stack.append(("this",))
            else:
                stack.append(("local", local) if local is not None else ("unknown",))
            continue

        if op.startswith(("astore", "istore", "lstore", "fstore", "dstore")):
            pop(stack)
            continue

        if op == "iinc":
            continue

        # Fields
        field = field_ref(ins)

        if op == "getfield":
            owner = pop(stack)
            owner_name = "this" if owner == ("this",) else describe(owner)
            if field:
                stack.append(sym_field(owner_name, field[0], field[1]))
            else:
                push_unknown(stack)
            continue

        if op == "putfield":
            value = pop(stack)
            owner = pop(stack)
            continue

        if op == "getstatic":
            if field:
                stack.append(sym_field("static", field[0], field[1]))
            else:
                push_unknown(stack)
            continue

        if op == "putstatic":
            pop(stack)
            continue

        # Integer/primitive operations
        if op in BINARY_ARITHMETIC:
            right = pop(stack)
            left = pop(stack)
            stack.append(sym_expr(op, left, right))
            continue

        if op in UNARY_ARITHMETIC:
            value = pop(stack)
            stack.append(sym_expr(op, value))
            continue

        # Stack manipulation
        if op == "dup":
            value = pop(stack)
            stack.extend([value, value])
            continue

        if op == "dup_x1":
            a = pop(stack)
            b = pop(stack)
            stack.extend([a, b, a])
            continue

        if op == "dup_x2":
            a = pop(stack)
            b = pop(stack)
            c = pop(stack)
            stack.extend([a, c, b, a])
            continue

        if op == "dup2":
            a = pop(stack)
            b = pop(stack)
            stack.extend([b, a, b, a])
            continue

        if op == "swap":
            a = pop(stack)
            b = pop(stack)
            stack.extend([a, b])
            continue

        if op == "pop":
            pop(stack)
            continue

        if op == "pop2":
            pop(stack)
            pop(stack)
            continue

        # Array reads and writes
        if op in ARRAY_LOADS:
            index = pop(stack)
            array = pop(stack)

            if op == "baload" and is_byte_array_a(array):
                base = find_constant_plus_v(index)
                events.append({
                    "file": method["file"],
                    "method": method["signature"],
                    "offset": offset,
                    "operation": "READ",
                    "base": base,
                    "index": describe(index),
                    "array": describe(array),
                    "value": "byte",
                    "context": instructions[max(0, pos - 5):pos + 2],
                })

            stack.append(("element", array, index))
            continue

        if op in ARRAY_STORES:
            value = pop(stack)
            index = pop(stack)
            array = pop(stack)

            if op == "bastore" and is_byte_array_a(array):
                base = find_constant_plus_v(index)
                events.append({
                    "file": method["file"],
                    "method": method["signature"],
                    "offset": offset,
                    "operation": "WRITE",
                    "base": base,
                    "index": describe(index),
                    "array": describe(array),
                    "value": describe(value),
                    "context": instructions[max(0, pos - 6):pos + 1],
                })
            continue

        # Object and array creation
        if op == "new":
            stack.append(("object", operand))
            continue

        if op in ("newarray", "anewarray"):
            count = pop(stack)
            stack.append(("array", count))
            continue

        if op == "multianewarray":
            match = re.search(r",\s*(\d+)", operand)
            dimensions = int(match.group(1)) if match else 1
            for _ in range(dimensions):
                pop(stack)
            stack.append(("array", ("unknown",)))
            continue

        if op == "arraylength":
            pop(stack)
            push_unknown(stack)
            continue

        if op == "checkcast":
            continue

        if op == "instanceof":
            pop(stack)
            push_unknown(stack)
            continue

        # Method calls: pop parameters and receiver, then push return value.
        if op.startswith(("invokevirtual", "invokespecial", "invokestatic",
                          "invokeinterface", "invokedynamic")):
            descriptor = method_ref(operand)
            argc = descriptor_arguments(descriptor) if descriptor else None
            returns = descriptor_return(descriptor) if descriptor else None

            if argc is None:
                stack.clear()
                continue

            for _ in range(argc):
                pop(stack)

            if op not in ("invokestatic", "invokedynamic"):
                pop(stack)

            if returns and returns != "V":
                push_unknown(stack)
            continue

        # Branches
        if op in ("ifeq", "ifne", "iflt", "ifge", "ifgt", "ifle",
                  "ifnull", "ifnonnull", "tableswitch", "lookupswitch"):
            pop(stack)
            continue

        if op.startswith(("if_icmp", "if_acmp")):
            pop(stack)
            pop(stack)
            continue

        if op in ("goto", "goto_w", "nop", "i2b", "i2c", "i2s"):
            continue

        # Returns and exceptions
        if op in ("ireturn", "lreturn", "freturn", "dreturn",
                  "areturn", "athrow", "monitorenter", "monitorexit"):
            pop(stack)
            continue

        if op == "return":
            continue

        # Unknown opcode: clear stack rather than risk false attribution.
        stack.clear()

    return events


def main():
    if not INPUT_DIR.exists():
        raise SystemExit(f"Input directory not found: {INPUT_DIR}")

    reports = sorted(INPUT_DIR.glob("*.txt"))
    if not reports:
        raise SystemExit(f"No bytecode reports found in {INPUT_DIR}")

    methods = []
    for report in reports:
        methods.extend(parse_methods(report))

    events = []
    for method in methods:
        events.extend(simulate(method))

    counts = Counter()
    method_sets = defaultdict(set)
    unknown_index = Counter()

    for event in events:
        if event["base"] is None:
            unknown_index[event["operation"]] += 1
            continue

        counts[(event["base"], event["operation"])] += 1
        method_sets[event["base"]].add(
            (event["file"], event["method"])
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        out.write("SYMBOLIC JVM ARRAY TRACE REPORT\n")
        out.write("=" * 76 + "\n")
        out.write(f"Input reports scanned: {len(reports)}\n")
        out.write(f"Methods parsed: {len(methods)}\n")
        out.write(f"Array accesses to a:[B traced: {len(events)}\n")
        out.write(
            "Index classification: exact CONSTANT + this.v:I, "
            "or unresolved expression\n\n"
        )

        out.write("1. SUMMARY BY BASE OFFSET\n")
        out.write("-" * 76 + "\n")

        for base in sorted(method_sets):
            out.write(
                f"{base:>6} + v:I  "
                f"reads={counts[(base, 'READ')]:>4} "
                f"writes={counts[(base, 'WRITE')]:>4} "
                f"methods={len(method_sets[base]):>3}\n"
            )

        out.write("\nUnclassified index accesses:\n")
        out.write(f"  READ:  {unknown_index['READ']}\n")
        out.write(f"  WRITE: {unknown_index['WRITE']}\n")

        out.write("\n2. ACCESS DETAILS\n")
        out.write("-" * 76 + "\n")

        for number, event in enumerate(events, start=1):
            base_text = (
                f"{event['base']} + v"
                if event["base"] is not None
                else "unclassified index"
            )

            out.write(
                f"\n[{number}] {event['file']} | {event['method']}\n"
            )
            out.write(
                f"{event['operation']} a[{base_text}] at bytecode "
                f"offset {event['offset']}\n"
            )
            out.write(f"Index expression: {event['index']}\n")
            if event["operation"] == "WRITE":
                out.write(f"Stored value: {event['value']}\n")

            out.write("Context:\n")
            for ins in event["context"]:
                marker = ">> " if ins["offset"] == event["offset"] else "   "
                out.write(
                    f"  {marker}{ins['offset']:>5}: "
                    f"{ins['opcode']:<18} {ins['operand']}\n"
                )

        out.write("\n3. LIMITATIONS\n")
        out.write("-" * 76 + "\n")
        out.write(
            "- This is a partial symbolic interpreter, not a verifier.\n"
            "- Unsupported bytecode clears the symbolic stack; some accesses "
            "may therefore be missed.\n"
            "- Unclassified index expressions are reported separately.\n"
            "- A symbolic match describes data flow, not game semantics.\n"
        )

    print(f"Reports scanned: {len(reports)}")
    print(f"Methods parsed: {len(methods)}")
    print(f"Array accesses traced: {len(events)}")
    print(f"Output: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
