
#!/usr/bin/env python3
"""
Control-flow-aware tracer for bytecode accesses to this.a:[B.

Reads javap -c -p reports from analysis/bytecode/.
Writes a separate report to analysis/array_field_trace_cfg.txt.

This is a conservative, partial JVM interpreter, not a complete verifier.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "analysis" / "bytecode"
OUTPUT = ROOT / "analysis" / "array_field_trace_cfg.txt"

UNKNOWN = ("unknown",)
THIS = ("this",)


@dataclass
class Instruction:
    offset: int
    text: str
    op: str
    operand: str = ""
    switch_targets: list[int] = field(default_factory=list)


@dataclass
class Method:
    source: str
    name: str
    instructions: list[Instruction]


def is_method_header(line: str) -> bool:
    s = line.strip()
    return (
        "(" in s
        and s.endswith(");")
        and not re.match(r"^\d+:", s)
        and not s.startswith(("descriptor:", "Signature:"))
    )


def parse_methods(path: Path) -> list[Method]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    methods: list[Method] = []
    current_name: Optional[str] = None
    in_code = False
    body: list[str] = []

    def finish() -> None:
        nonlocal current_name, body, in_code
        if current_name is not None:
            methods.append(Method(str(path.relative_to(ROOT)), current_name,
                                  parse_instructions(body)))
        current_name = None
        body = []
        in_code = False

    for line in lines:
        if is_method_header(line):
            finish()
            current_name = line.strip()
            continue
        if current_name is None:
            continue
        if line.strip() == "Code:":
            in_code = True
            continue
        if in_code:
            body.append(line)

    finish()
    return methods


def parse_instructions(lines: list[str]) -> list[Instruction]:
    parsed: list[Instruction] = []
    current_switch: Optional[Instruction] = None

    for line in lines:
        m = re.match(r"^\s*(\d+):\s+(\S+)(.*)$", line)
        if m:
            current_switch = None
            offset = int(m.group(1))
            op = m.group(2)
            operand = m.group(3).strip()
            ins = Instruction(offset, line.strip(), op, operand)
            parsed.append(ins)
            if op in ("tableswitch", "lookupswitch"):
                current_switch = ins
            continue

        # javap prints switch cases on lines without bytecode offsets.
        if current_switch is not None:
            target = re.search(r":\s*(-?\d+)\s*$", line.strip())
            if target:
                current_switch.switch_targets.append(int(target.group(1)))

    return parsed


def field_ref(ins: Instruction) -> Optional[tuple[str, str]]:
    m = re.search(r"//\s*Field\s+([\w$<>]+):(\S+)", ins.operand)
    if not m:
        return None
    return m.group(1), m.group(2)


def method_descriptor(ins: Instruction) -> Optional[tuple[int, str]]:
    # javap comment example: // Method example:([BI)Z
    m = re.search(r"//\s*(?:InterfaceMethod|Method)\s+.*?:"
                  r"\((.*?)\)(\S+)", ins.operand)
    if not m:
        return None

    args = m.group(1)
    ret = m.group(2)
    count = 0
    i = 0
    while i < len(args):
        while i < len(args) and args[i] == "[":
            i += 1
        if i >= len(args):
            break
        if args[i] == "L":
            end = args.find(";", i)
            i = len(args) if end < 0 else end + 1
        else:
            i += 1
        count += 1
    return count, ret


def iconst_value(op: str, operand: str) -> Optional[int]:
    m = re.fullmatch(r"iconst_(-?\d+)", op)
    if m:
        return int(m.group(1))
    if op == "bipush" or op == "sipush":
        m = re.match(r"(-?\d+)", operand)
        if m:
            return int(m.group(1))
    if op == "ldc" or op == "ldc_w":
        m = re.search(r"//\s*int\s+(-?\d+)", operand)
        if m:
            return int(m.group(1))
    return None


def local_index(op: str, operand: str) -> Optional[int]:
    m = re.fullmatch(r"[ailf]load_(\d+)", op)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"[ailf]store_(\d+)", op)
    if m:
        return int(m.group(1))
    if op in ("iload", "aload", "istore", "astore",
              "lload", "lstore", "fload", "fstore",
              "dload", "dstore"):
        m = re.match(r"(\d+)", operand)
        if m:
            return int(m.group(1))
    return None


def is_load(op: str) -> bool:
    return op.startswith(("iload", "aload", "lload", "fload", "dload"))


def is_store(op: str) -> bool:
    return op.startswith(("istore", "astore", "lstore", "fstore", "dstore"))


def pop(stack: list, count: int = 1) -> list:
    values = []
    for _ in range(count):
        values.append(stack.pop() if stack else UNKNOWN)
    return values


def make_add(a, b):
    if a == UNKNOWN or b == UNKNOWN:
        return UNKNOWN
    if isinstance(a, tuple) and a[0] == "const":
        if isinstance(b, tuple) and b[0] == "const":
            return ("const", a[1] + b[1])
    if isinstance(b, tuple) and b[0] == "const":
        return ("add", a, b)
    if isinstance(a, tuple) and a[0] == "const":
        return ("add", b, a)
    return ("add", a, b)


def index_base(value) -> Optional[int]:
    """Return C only for a provable index C + this.v:I."""
    if not isinstance(value, tuple):
        return None
    if value[0] == "add" and len(value) == 3:
        a, b = value[1], value[2]
        if isinstance(a, tuple) and a[0] == "const":
            if b == ("field", "this.v:I"):
                return a[1]
        if isinstance(b, tuple) and b[0] == "const":
            if a == ("field", "this.v:I"):
                return b[1]
    return None


def merge_value(a, b):
    if a == b:
        return a
    return UNKNOWN


def merge_state(old, new):
    if old is None:
        return new
    old_stack, old_locals = old
    new_stack, new_locals = new

    if len(old_stack) != len(new_stack):
        size = max(len(old_stack), len(new_stack))
        stack = [UNKNOWN] * size
    else:
        stack = [merge_value(a, b) for a, b in zip(old_stack, new_stack)]

    keys = set(old_locals) | set(new_locals)
    locals_out = {}
    for key in keys:
        locals_out[key] = merge_value(
            old_locals.get(key, UNKNOWN),
            new_locals.get(key, UNKNOWN),
        )
    return stack, locals_out


def branch_targets(ins: Instruction) -> list[int]:
    if ins.op in ("tableswitch", "lookupswitch"):
        return sorted(set(ins.switch_targets))
    if ins.op.startswith("if") or ins.op in ("goto", "goto_w", "jsr", "jsr_w"):
        m = re.search(r"(-?\d+)\s*$", ins.operand)
        if m:
            return [int(m.group(1))]
    return []


def is_conditional(op: str) -> bool:
    return op.startswith("if")


def is_terminal(op: str) -> bool:
    return op in (
        "goto", "goto_w", "jsr", "jsr_w",
        "ireturn", "lreturn", "freturn", "dreturn",
        "areturn", "return", "athrow", "ret",
        "tableswitch", "lookupswitch",
    )


def build_blocks(insns: list[Instruction]):
    if not insns:
        return [], {}, []

    by_offset = {ins.offset: i for i, ins in enumerate(insns)}
    leaders = {insns[0].offset}

    for i, ins in enumerate(insns):
        targets = branch_targets(ins)
        leaders.update(t for t in targets if t in by_offset)
        if (is_conditional(ins.op) or ins.op in (
            "goto", "goto_w", "jsr", "jsr_w",
            "tableswitch", "lookupswitch",
            "ireturn", "lreturn", "freturn", "dreturn",
            "areturn", "return", "athrow",
        )) and i + 1 < len(insns):
            leaders.add(insns[i + 1].offset)

    leader_indices = sorted(by_offset[x] for x in leaders)
    blocks = []
    for n, start in enumerate(leader_indices):
        end = leader_indices[n + 1] if n + 1 < len(leader_indices) else len(insns)
        blocks.append(insns[start:end])

    offset_to_block = {}
    for bi, block in enumerate(blocks):
        for ins in block:
            offset_to_block[ins.offset] = bi

    successors = [[] for _ in blocks]
    for bi, block in enumerate(blocks):
        last = block[-1]
        targets = branch_targets(last)
        for target in targets:
            if target in offset_to_block:
                successors[bi].append(offset_to_block[target])

        falls_through = (
            not is_terminal(last.op)
            or is_conditional(last.op)
        )
        if falls_through and bi + 1 < len(blocks):
            successors[bi].append(bi + 1)

        successors[bi] = sorted(set(successors[bi]))

    return blocks, offset_to_block, successors


def transfer(ins: Instruction, stack: list, locals_: dict, events: list,
             method_label: str):
    op, operand = ins.op, ins.operand
    value = iconst_value(op, operand)

    if value is not None:
        stack.append(("const", value))
        return

    if op == "aconst_null":
        stack.append(UNKNOWN)
        return

    if op == "aload_0":
        stack.append(THIS)
        return

    idx = local_index(op, operand)
    if idx is not None and is_load(op):
        stack.append(locals_.get(idx, UNKNOWN))
        return
    if idx is not None and is_store(op):
        locals_[idx] = pop(stack)[0]
        return

    if op.startswith(("iconst_", "lconst_", "fconst_", "dconst_")):
        stack.append(UNKNOWN)
        return

    if op in ("getfield", "getstatic"):
        receiver = THIS if op == "getstatic" else pop(stack)[0]
        ref = field_ref(ins)
        if ref:
            name, desc = ref
            if receiver == THIS:
                stack.append(("field", f"this.{name}:{desc}"))
            else:
                stack.append(("field", f"other.{name}:{desc}"))
        else:
            stack.append(UNKNOWN)
        return

    if op in ("putfield", "putstatic"):
        pop(stack)  # value
        if op == "putfield":
            pop(stack)  # receiver
        return

    if op in ("iadd", "ladd", "fadd", "dadd"):
        b, a = pop(stack, 2)
        stack.append(make_add(a, b))
        return

    if op in ("isub", "lsub", "imul", "idiv", "irem",
              "iand", "ior", "ixor", "ishl", "ishr", "iushr",
              "lsub", "lmul", "ldiv", "lrem", "land", "lor", "lxor",
              "fsub", "fmul", "fdiv", "dsub", "dmul", "ddiv"):
        pop(stack, 2)
        stack.append(UNKNOWN)
        return

    if op in ("ineg", "lneg", "fneg", "dneg",
              "i2b", "i2c", "i2s", "i2l", "i2f", "i2d",
              "l2i", "l2f", "l2d", "f2i", "f2l", "f2d",
              "d2i", "d2l", "d2f", "checkcast", "instanceof"):
        old = pop(stack)[0]
        stack.append(old if op == "checkcast" else UNKNOWN)
        return

    if op in ("baload", "caload", "saload", "iaload",
              "laload", "faload", "daload", "aaload"):
        index, array = pop(stack, 2)
        if array == ("field", "this.a:[B") and op == "baload":
            base = index_base(index)
            events.append(("READ", base, ins.offset, method_label, ins.text))
        stack.append(("element", array, index))
        return

    if op in ("bastore", "castore", "sastore", "iastore",
              "lastore", "fastore", "dastore", "aastore"):
        value_sym, index, array = pop(stack, 3)
        if array == ("field", "this.a:[B") and op == "bastore":
            base = index_base(index)
            events.append(("WRITE", base, ins.offset, method_label, ins.text))
        return

    if op == "arraylength":
        pop(stack)
        stack.append(UNKNOWN)
        return

    if op in ("dup",):
        a = stack[-1] if stack else UNKNOWN
        stack.append(a)
        return
    if op == "dup_x1":
        a, b = pop(stack, 2)
        stack.extend([a, b, a])
        return
    if op == "dup_x2":
        a, b, c = pop(stack, 3)
        stack.extend([a, c, b, a])
        return
    if op == "dup2":
        a, b = pop(stack, 2)
        stack.extend([b, a, b, a])
        return
    if op == "dup2_x1":
        a, b, c = pop(stack, 3)
        stack.extend([b, a, c, b, a])
        return
    if op == "dup2_x2":
        a, b, c, d = pop(stack, 4)
        stack.extend([b, a, d, c, b, a])
        return
    if op == "swap":
        a, b = pop(stack, 2)
        stack.extend([a, b])
        return
    if op in ("pop",):
        pop(stack)
        return
    if op == "pop2":
        pop(stack, 2)
        return

    if op.startswith("invoke"):
        desc = method_descriptor(ins)
        if desc:
            argc, ret = desc
            pop(stack, argc)
            if op not in ("invokestatic", "invokedynamic"):
                pop(stack)
            if ret != "V":
                stack.append(UNKNOWN)
        else:
            # Unknown call shape: clear the stack to avoid false matches.
            stack.clear()
        return

    if op == "iinc":
        m = re.match(r"(\d+)", operand)
        if m:
            locals_[int(m.group(1))] = UNKNOWN
        return

    if is_conditional(op):
        pop(stack, 2 if ("icmp" in op or "acmp" in op) else 1)
        return

    if op in ("tableswitch", "lookupswitch"):
        pop(stack)
        return

    if op in ("ireturn", "lreturn", "freturn", "dreturn", "areturn", "athrow"):
        pop(stack)
        return

    if op in ("goto", "goto_w", "return", "nop", "jsr", "jsr_w", "ret"):
        return

    if op in ("new", "newarray", "anewarray", "multianewarray"):
        if op in ("newarray", "anewarray"):
            pop(stack)
        elif op == "multianewarray":
            m = re.search(r"\s+(\d+)\s*$", operand)
            pop(stack, int(m.group(1)) if m else 1)
        stack.append(UNKNOWN)
        return

    if op in ("monitorenter", "monitorexit"):
        pop(stack)
        return

    # Unimplemented instruction: keep the analysis conservative.
    # We do not guess its result.
    if op.startswith(("iload", "aload", "lload", "fload", "dload")):
        stack.append(UNKNOWN)


def analyze_method(method: Method):
    insns = method.instructions
    if not insns:
        return []

    blocks, _, successors = build_blocks(insns)
    if not blocks:
        return []

    in_states = [None] * len(blocks)
    in_states[0] = ([], {})
    queue = deque([0])
    queued = {0}
    iterations = 0
    max_iterations = max(1000, len(blocks) * 100)

    # Fixed-point propagation over the control-flow graph.
    while queue and iterations < max_iterations:
        bi = queue.popleft()
        queued.discard(bi)
        iterations += 1
        state = in_states[bi]
        if state is None:
            continue

        stack = list(state[0])
        locals_ = dict(state[1])
        for ins in blocks[bi]:
            transfer(ins, stack, locals_, [], method.name)

        out_state = (stack, locals_)
        for target in successors[bi]:
            merged = merge_state(in_states[target], out_state)
            if merged != in_states[target]:
                in_states[target] = merged
                if target not in queued:
                    queue.append(target)
                    queued.add(target)

    # Re-run each reachable block once with its final merged input state.
    events = []
    for bi, block in enumerate(blocks):
        state = in_states[bi]
        if state is None:
            continue
        stack = list(state[0])
        locals_ = dict(state[1])
        label = f"{method.source} | {method.name}"
        for ins in block:
            transfer(ins, stack, locals_, events, label)

    return events


def main():
    if not INPUT_DIR.exists():
        raise SystemExit(f"Missing bytecode reports directory: {INPUT_DIR}")

    paths = sorted(INPUT_DIR.glob("*.txt"))
    methods: list[Method] = []
    for path in paths:
        methods.extend(parse_methods(path))

    all_events = []
    for method in methods:
        all_events.extend(analyze_method(method))

    known = defaultdict(lambda: {"READ": 0, "WRITE": 0, "methods": set()})
    unresolved = {"READ": 0, "WRITE": 0}
    examples = defaultdict(list)

    for kind, base, offset, method, text_line in all_events:
        if base is None:
            unresolved[kind] += 1
            continue
        known[base][kind] += 1
        known[base]["methods"].add(method)
        if len(examples[(base, kind)]) < 8:
            examples[(base, kind)].append(
                f"  {method} @ bytecode {offset}: {text_line}"
            )

    out = []
    out.append("CONTROL-FLOW-AWARE JVM ARRAY TRACE REPORT")
    out.append(f"Input reports: {len(paths)}")
    out.append(f"Methods parsed: {len(methods)}")
    out.append(f"Reachable a:[B accesses: {len(all_events)}")
    out.append("Only exact C + this.v:I indices are classified.")
    out.append("Unclassified means the array was traced but its index was not proven.")
    out.append("")
    out.append("SUMMARY BY BASE OFFSET")
    out.append("base | reads | writes | methods")

    for base in sorted(known):
        item = known[base]
        out.append(
            f"{base:>5} | {item['READ']:>5} | {item['WRITE']:>6} | "
            f"{len(item['methods']):>7}"
        )

    out.append("")
    out.append("UNCLASSIFIED ACCESSES")
    out.append(f"READ: {unresolved['READ']}")
    out.append(f"WRITE: {unresolved['WRITE']}")
    out.append("")
    out.append("EXAMPLES")

    for base in sorted(known):
        for kind in ("READ", "WRITE"):
            items = examples[(base, kind)]
            if items:
                out.append(f"\n[{kind}] base {base}")
                out.extend(items)

    out.append("")
    out.append("LIMITATIONS")
    out.append("- This is a partial interpreter, not a complete JVM verifier.")
    out.append("- Stack operations assume common category-1 values.")
    out.append("- Unknown invocation descriptors can stop tracing a stack path.")
    out.append("- Treat counts as candidates until verified against bytecode.")
    out.append("- Unclassified accesses are not evidence of a particular field meaning.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"Methods: {len(methods)}; traced accesses: {len(all_events)}")


if __name__ == "__main__":
    main()
