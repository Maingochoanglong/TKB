"""Khung giờ do nhà trường đặt (sheet QUY ĐỊNH, bảng Ngày): tên các ngày học, các buổi của từng ngày và số tiết mỗi
buổi. Tiết đánh số liên tục trong ngày (1..n) theo thứ tự buổi; mỗi ngày có thể khác nhau (vd chiều Thứ 5 có 4 tiết,
Thứ 7 chỉ học sáng, một trường có buổi Tối).

Mọi chỗ cần đọc chữ ngày, buổi do người dùng ghi (cột Buổi Nghỉ, cột Ngày/Buổi của sheet LUẬT) hay hỏi một tiết thuộc
buổi nào đều qua module này. Đọc config lúc gọi (rules.applied đổi khung giờ theo file vào).
"""
from __future__ import annotations

import re

from . import config
from .staff import _fold

Slot = tuple[int, int]


def days() -> list[int]:
    """Các ngày học (chỉ số trong config.DAYS), theo thứ tự."""
    return sorted(config.DAY_SESSIONS)


def sessions(d: int) -> tuple[config.Session, ...]:
    return config.DAY_SESSIONS.get(d, ())


def session_at(d: int, p: int) -> config.Session | None:
    """Buổi chứa tiết p của ngày d (None: ngày đó không có tiết p)."""
    return next((s for s in sessions(d) if p in s.periods), None)


def session_names() -> list[str]:
    """Tên các buổi, theo thứ tự xuất hiện trong ngày (vd Sáng, Chiều)."""
    names: dict[str, None] = {}
    for d in days():
        for s in sessions(d):
            names.setdefault(s.name, None)
    return list(names)


def first_session_name() -> str:
    """Buổi đầu ngày (vd Sáng): buổi đầu tiên của ngày học đầu tiên."""
    names = session_names()
    return names[0] if names else ""


def periods(d: int) -> list[int]:
    return [p for s in sessions(d) for p in s.periods]


def max_periods() -> int:
    """Số tiết của ngày dài nhất."""
    return max((len(periods(d)) for d in days()), default=0)


def day_name(d: int) -> str:
    """Tên ngày d; ngày ngoài khung giờ (luật nhắc tới Thứ 7 khi trường học Thứ 2 – Thứ 6): theo cách đặt tên "Thứ n"
    nếu khung giờ đặt tên như vậy, không thì "ngày n"."""
    if 0 <= d < len(config.DAYS):
        return config.DAYS[d]
    classic = all(re.fullmatch(rf"Thứ {i + 2}", name) for i, name in enumerate(config.DAYS))
    return f"Thứ {d + 2}" if classic else f"ngày {d + 1}"


def short_day(d: int) -> str:
    """Tên ngày viết gọn để ghi trong ô chữ, vd "Thứ 5" -> "T5"; tên khác giữ nguyên."""
    name = day_name(d)
    m = re.fullmatch(r"Thứ\s*(\d)", name)
    return f"T{m.group(1)}" if m else name


def _day_keys(d: int) -> set[str]:
    """Các cách viết một ngày: tên ngày (không phân biệt hoa thường, dấu), và với tên dạng "Thứ n": "Tn", "thu n", "n";
    "Chủ nhật": "CN"."""
    name = _fold(day_name(d))
    keys = {name, name.replace(" ", "")}
    if m := re.fullmatch(r"thu\s*(\d)", name):
        n = m.group(1)
        keys |= {f"t{n}", f"t {n}", f"thu{n}", n}
    if name.replace(" ", "") == "chunhat":
        keys |= {"cn", "chu nhat"}
    return keys


def day_index(text) -> int | None:
    """Ngày học ghi bằng chữ (tên ngày hoặc cách viết gọn) -> chỉ số ngày; None nếu không có ngày nào như vậy."""
    key = re.sub(r"\s+", " ", _fold(text)).strip()
    for d in days():
        if key in _day_keys(d):
            return d
    return None


def day_list(text) -> list[int] | None:
    """Danh sách ngày, cách nhau bằng dấu phẩy; khoảng "Thứ 2-Thứ 4", "T2-T4" theo thứ tự ngày học.
    None nếu có phần không phải ngày học."""
    out: list[int] = []
    order = days()
    for part in re.split(r"[,;]", str(text)):
        part = part.strip()
        if not part:
            continue
        d = day_index(part)
        if d is None:
            ends = re.split(r"\s*[-–]\s*", part)
            if len(ends) != 2:
                return None
            a, b = day_index(ends[0]), day_index(_range_end(ends[0], ends[1]))
            if a is None or b is None:
                return None
            i, j = sorted((order.index(a), order.index(b)))
            out += order[i:j + 1]
        else:
            out.append(d)
    return sorted(set(out))


def _range_end(start: str, end: str) -> str:
    """"Thứ 2-4", "T2-4": vế sau chỉ ghi số thì mượn chữ của vế trước."""
    if re.fullmatch(r"\d", end.strip()) and (m := re.match(r"(.*?)\d\s*$", start)):
        return m.group(1) + end.strip()
    return end


def session_name(text) -> str | None:
    """Tên buổi ghi bằng chữ ("chiều", "Buổi chiều") -> tên buổi trong khung giờ; None nếu không có buổi nào như vậy."""
    key = re.sub(r"^buoi\s+", "", re.sub(r"\s+", " ", _fold(text)).strip())
    for name in session_names():
        if _fold(name) == key:
            return name
    return None


def split_session_day(text) -> tuple[str, int] | None:
    """"Chiều T5", "Sáng thứ 6", "Tối Mon" -> (buổi, ngày); None nếu không đọc được."""
    folded = re.sub(r"\s+", " ", _fold(text)).strip()
    for name in sorted(session_names(), key=lambda n: -len(_fold(n))):
        head = _fold(name)
        for prefix in (head, f"buoi {head}"):
            if folded.startswith(prefix + " ") or (folded.startswith(prefix) and folded[len(prefix):len(prefix) + 1]
                                                    .isdigit()):
                d = day_index(folded[len(prefix):])
                if d is not None:
                    return name, d
    return None
