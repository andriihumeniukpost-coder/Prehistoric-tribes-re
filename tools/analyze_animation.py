#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prehistoric Tribes v0.1.38
Автоматический первичный анализ индексов кадров и ресурса /a.

Вход:
    analysis/bytecode/g.txt
    analysis/a_dump/a_dump.json

Выход:
    analysis/animation_report.txt
    analysis/frame_field_access.csv
    analysis/record_154_analysis.txt

Скрипт ничего не изменяет в игровом коде и исходных данных.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parent.parent
BYTECODE = ROOT / "analysis" / "bytecode" / "g.txt"
DUMP_JSON = ROOT / "analysis" / "a_dump" / "a_dump.json"
OUT_DIR = ROOT / "analysis"

REPORT = OUT_DIR / "animation_report.txt"
FIELDS_CSV = OUT_DIR / "frame_field_access.csv"
RECORD_REPORT = OUT_DIR / "record_154_analysis.txt"


# Поля, связанные с вычислением индекса изображения/кадра.
TARGET_FIELDS = {
    "o:B",
    "q:B",
    "ai:B",
    "a:[B",
    "a:[S",
    "aS:[S",
    "aR:I",
    "ag:B",
    "ah:B",
    "aj:B",
    "ak:B",
    "p:[B",
    "v:B",
}

TARGET_NAMES = {
    "o", "q", "ai", "a", "aS", "aR", "ag", "ah",
    "aj", "ak", "p", "v",
}


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_field(raw: str) -> str:
    return re.sub(r"\s+", "", raw.strip())


def parse_methods(text: str) -> list[dict]:
    """
    Выделяет методы из текстового дизассемблера.
    Ожидаемый формат содержит строки наподобие:
        final void b(int);
        private void U();
        descriptor: (I)V
        Code:
    """
    lines = text.splitlines()
    starts = []

    method_re = re.compile(
        r"^\s*(?:(?:public|private|protected|static|final|"
        r"synchronized|native|abstract)\s+)*"
        r"[\w.$\[\]/<>]+\s+[\w$<>]+\([^;]*\);\s*$"
    )

    for i, line in enumerate(lines):
        if method_re.match(line):
            # Заголовок метода должен сопровождаться дескриптором
            # в ближайших следующих строках.
            nearby = "\n".join(lines[i + 1:i + 5])
            if "descriptor:" in nearby:
                starts.append(i)

    methods = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[start:end]
        header = lines[start].strip()
        descriptor = ""

        for line in block[:8]:
            match = re.search(r"descriptor:\s*(\S+)", line)
            if match:
                descriptor = match.group(1)
                break

        methods.append({
            "header": header,
            "descriptor": descriptor,
            "start_line": start + 1,
            "lines": block,
            "text": "\n".join(block),
        })

    return methods


def find_field_accesses(methods: list[dict]) -> list[dict]:
    """
    Извлекает getfield/putfield/getstatic/putstatic,
    сохраняя метод, строку и окружающий контекст.
    """
    results = []
    instruction_re = re.compile(
        r"^\s*(\d+):\s+"
        r"(getfield|putfield|getstatic|putstatic)\s+"
        r"#\d+.*?//\s*Field\s+(.+?)\s*$"
    )

    for method in methods:
        for i, line in enumerate(method["lines"]):
            match = instruction_re.match(line)
            if not match:
                continue

            offset, opcode, raw_field = match.groups()
            field = normalize_field(raw_field)
            simple_name = field.split(":")[0].split(".")[-1]

            # Берём целевые поля и похожие записи/чтения массивов.
            relevant = (
                field in TARGET_FIELDS
                or simple_name in TARGET_NAMES
                or (
                    simple_name == "o"
                    and opcode in {"putfield", "getfield"}
                )
            )
            if not relevant:
                continue

            context_start = max(0, i - 5)
            context_end = min(len(method["lines"]), i + 4)
            context = " | ".join(
                x.strip() for x in method["lines"][context_start:context_end]
            )

            results.append({
                "method": method["header"],
                "descriptor": method["descriptor"],
                "method_start_line": method["start_line"],
                "instruction_offset": offset,
                "opcode": opcode,
                "field": field,
                "context": context,
            })

    return results


def find_method_calls(methods: list[dict]) -> list[dict]:
    """Собирает вызовы методов из invoke-инструкций."""
    results = []
    invoke_re = re.compile(
        r"^\s*(\d+):\s+(invoke\w+)\s+#\d+.*?//\s*Method\s+(.+?)\s*$"
    )

    for method in methods:
        for line in method["lines"]:
            match = invoke_re.match(line)
            if not match:
                continue

            offset, opcode, target = match.groups()
            results.append({
                "method": method["header"],
                "offset": offset,
                "opcode": opcode,
                "target": target.strip(),
            })

    return results


def find_relevant_methods(methods: list[dict]) -> list[dict]:
    """
    Отбирает методы, где встречаются целевые поля или загрузка изображений.
    """
    selected = []

    for method in methods:
        text = method["text"]
        reasons = []

        for field in sorted(TARGET_FIELDS):
            if field in text:
                reasons.append(field)

        if "Image.createImage" in text:
            reasons.append("Image.createImage")
        if "drawImage" in text or "drawRegion" in text:
            reasons.append("drawImage/drawRegion")

        if reasons:
            selected.append({
                "header": method["header"],
                "descriptor": method["descriptor"],
                "line": method["start_line"],
                "reasons": sorted(set(reasons)),
                "text": text,
            })

    return selected


def walk_for_record(obj, target_key="record_154", path="$"):
    """
    Находит record_154 в JSON независимо от глубины вложенности.
    """
    found = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if key == target_key and isinstance(value, dict):
                found.append((child_path, value))
            found.extend(walk_for_record(value, target_key, child_path))

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found.extend(
                walk_for_record(value, target_key, f"{path}[{i}]")
            )

    return found


def decode_record(record: dict) -> tuple[int | None, list[int]]:
    offset = record.get("offset")
    raw = record.get("bytes", [])

    if isinstance(raw, str):
        # Поддерживаем hex-строки с пробелами и префиксом 0x.
        cleaned = re.sub(r"[^0-9a-fA-F]", "", raw)
        if len(cleaned) % 2 == 1:
            cleaned = "0" + cleaned
        data = bytes.fromhex(cleaned) if cleaned else b""
        values = list(data)
    elif isinstance(raw, list):
        values = []
        for item in raw:
            if isinstance(item, int):
                values.append(item & 0xFF)
            elif isinstance(item, str):
                try:
                    values.append(int(item, 0) & 0xFF)
                except ValueError:
                    pass
    else:
        values = []

    try:
        offset = int(offset) if offset is not None else None
    except (TypeError, ValueError):
        offset = None

    return offset, values


def write_record_report(data: dict) -> str:
    matches = walk_for_record(data)
    output = [
        "АНАЛИЗ RECORD 154",
        "=" * 60,
        f"Файл: {DUMP_JSON.relative_to(ROOT)}",
        f"Найдено записей record_154: {len(matches)}",
        "",
    ]

    if not matches:
        output += [
            "Запись record_154 не найдена по ожидаемому ключу.",
            "Проверьте структуру a_dump.json.",
            "Верхний уровень JSON:",
            ", ".join(str(k) for k in data.keys())
            if isinstance(data, dict) else type(data).__name__,
        ]
        return "\n".join(output) + "\n"

    for path, record in matches:
        offset, values = decode_record(record)
        output += [
            f"Путь JSON: {path}",
            f"Offset: {offset}",
            f"Длина из JSON: {record.get('length', 'не указана')}",
            f"Количество декодированных байтов: {len(values)}",
            f"Байты: {values}",
            "Hex: " + bytes(values).hex(),
            "",
            "Индексы внутри записи:",
        ]

        for i, value in enumerate(values):
            absolute = offset + i if offset is not None else "?"
            output.append(
                f"  q={i:3d}  абсолютное смещение={str(absolute):>6}  "
                f"unsigned={value:3d}  signed={value if value < 128 else value - 256:4d}"
            )

        output.append("")
        output.append(
            "Важно: индекс записи в JSON и индекс кадра — не одно и то же. "
            "Значения интерпретируются только после подтверждения формулы "
            "в байткоде."
        )
        output.append("")

    return "\n".join(output) + "\n"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bytecode_text = read_text(BYTECODE)
        json_text = read_text(DUMP_JSON)
        dump_data = json.loads(json_text)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        print(
            "Проверь пути analysis/bytecode/g.txt и "
            "analysis/a_dump/a_dump.json.",
            file=sys.stderr,
        )
        return 1

    methods = parse_methods(bytecode_text)
    accesses = find_field_accesses(methods)
    calls = find_method_calls(methods)
    relevant = find_relevant_methods(methods)

    with FIELDS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method", "descriptor", "method_start_line",
                "instruction_offset", "opcode", "field", "context",
            ],
        )
        writer.writeheader()
        writer.writerows(accesses)

    RECORD_REPORT.write_text(
        write_record_report(dump_data), encoding="utf-8"
    )

    field_counts = Counter(
        (row["field"], row["opcode"]) for row in accesses
    )

    report = [
        "PREHISTORIC TRIBES v0.1.38 — ANIMATION ANALYSIS",
        "=" * 72,
        "",
        f"Байткод: {BYTECODE.relative_to(ROOT)}",
        f"Дамп ресурса: {DUMP_JSON.relative_to(ROOT)}",
        "",
        "1. ОБЩАЯ СТАТИСТИКА",
        "-" * 72,
        f"Методов распознано: {len(methods)}",
        f"Обращений к интересующим полям: {len(accesses)}",
        f"Методов с целевыми полями/отрисовкой: {len(relevant)}",
        f"Вызовов методов найдено: {len(calls)}",
        "",
        "2. ЧТЕНИЕ И ЗАПИСЬ ПОЛЕЙ",
        "-" * 72,
    ]

    if field_counts:
        for (field, opcode), count in sorted(field_counts.items()):
            report.append(f"{field:16} {opcode:12} {count:5}")
    else:
        report.append(
            "Не удалось распознать обращения к полям. "
            "Возможно, формат комментариев байткода отличается."
        )

    report += [
        "",
        "3. МЕТОДЫ, СВЯЗАННЫЕ С КАДРАМИ И ОТРИСОВКОЙ",
        "-" * 72,
    ]

    for method in relevant:
        report += [
            f"[строка {method['line']}] {method['header']}",
            f"  дескриптор: {method['descriptor']}",
            f"  признаки: {', '.join(method['reasons'])}",
        ]

    report += [
        "",
        "4. ВЫЗОВЫ h(byte), b(int), U() И c(byte)",
        "-" * 72,
    ]

    wanted = ("h(byte)", "b(int)", "U()", "c(byte)")
    matching_calls = [
        call for call in calls
        if any(name in call["target"] for name in wanted)
    ]

    for call in matching_calls:
        report.append(
            f"{call['method']} @ {call['offset']}: "
            f"{call['opcode']} -> {call['target']}"
        )

    if not matching_calls:
        report.append(
            "Точные имена вызовов не распознаны; см. полный CSV "
            "и исходный g.txt."
        )

    report += [
        "",
        "5. ФАЙЛЫ РЕЗУЛЬТАТА",
        "-" * 72,
        str(REPORT.relative_to(ROOT)),
        str(FIELDS_CSV.relative_to(ROOT)),
        str(RECORD_REPORT.relative_to(ROOT)),
        "",
        "ОГРАНИЧЕНИЯ",
        "-" * 72,
        "Это статический первичный анализ, а не окончательная расшифровка.",
        "Обфусцированные имена полей могут повторяться у полей разных типов.",
        "Числовое значение байта не считается индексом кадра без подтверждения.",
        "Скрипт не меняет игровые ресурсы и исходный код.",
        "",
    ]

    REPORT.write_text("\n".join(report), encoding="utf-8")

    print("Анализ завершён.")
    print(f"Методов распознано: {len(methods)}")
    print(f"Обращений к полям: {len(accesses)}")
    print(f"Релевантных методов: {len(relevant)}")
    print()
    print(f"Отчёт: {REPORT.relative_to(ROOT)}")
    print(f"Поля CSV: {FIELDS_CSV.relative_to(ROOT)}")
    print(f"Record 154: {RECORD_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
