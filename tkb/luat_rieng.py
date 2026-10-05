"""Luật riêng của trường: sheet LUẬT RIÊNG, mỗi dòng một luật, theo một mẫu có sẵn (KINDS) hoặc tự ghép.

Nhà trường tự thêm luật mà không cần sửa mã nguồn. Mỗi dòng là một câu của bộ ghép luật (tkb/bo_ghep.py):
"Với mỗi [phạm vi], chỉ xét các tiết [Môn, Nhãn, Khối, Lớp, Ngày, Tiết, Buổi, Giáo viên] thì [Phép đo] [So sánh]
[Số], khi [Áp dụng khi]". Mẫu (vd "Không xếp vào", "Học 2 tiết liền") điền sẵn phạm vi và phép đo; "Tự ghép" ghi đủ
các cột Với mỗi, Phép đo, So sánh. Module này đọc/ghi các ô và nói luật bằng lời; phần xếp (miền ô, mô hình CP-SAT,
kiểm tra độc lập, QA, phép đếm trước, phân công) nằm ở tkb/bo_ghep.py, viết một lần cho mọi phép đo.

Mỗi luật là bắt buộc (cột Bắt buộc = Có) hoặc ưu tiên: cột Mức ghi Thấp, Vừa, Cao, Rất cao (hoặc 1–4, trọng số
`config.Weights.custom_levels`), hoặc cột Điểm ghi thẳng điểm trừ mỗi lần không theo.
Không có luật riêng nào (config.CUSTOM_RULES rỗng) thì mô hình dựng ra y như cũ: mã kết quả không đổi.

Khối, Lớp, Ngày, Tiết, Môn, Nhãn ghi danh sách cách nhau bằng dấu phẩy hoặc khoảng, vd "3, 4, 5", "3-5",
"Thứ 2, Thứ 4", "T2-T4", "5-7"; Buổi ghi Sáng/Chiều; Giáo viên ghi chức vụ (Chủ Nhiệm, Bộ Môn, Quản Lý hoặc chức vụ
GV chuyên biệt).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import bo_ghep, config
from .bo_ghep import MEASURE, MEASURES, OPS, SCOPE, SCOPES
from .config import CustomRule
from .staff import _NO, _YES, _fold, clean_name, normalize, subject_key

SHEET = "LUẬT RIÊNG"  # sheet của bản trước (chỉ có luật riêng): vẫn đọc được
RULES_SHEET = config.RULES_SHEET_ROWS  # sheet LUẬT: mọi luật, kể cả luật có sẵn (tkb/luat_co_san.py)
NOTE = "Ghi chú"
SAY = "Luật đọc là"  # cột chương trình ghi câu đọc lại của dòng; khi đọc thì bỏ qua như Ghi chú
GROUP = ("group_label", "Nhóm")  # cột đầu của sheet LUẬT
# Cột của sheet: (khóa, tiêu đề), theo thứ tự đọc câu luật.
COLUMNS = (("kind", "Kiểu luật"), ("scope", "Với mỗi"), ("subject", "Môn"), ("group", "Gồm môn tăng cường"),
           ("tags", "Nhãn"), ("exclude", "Trừ nhãn"), ("grades", "Khối"), ("classes", "Lớp"), ("days", "Ngày"),
           ("periods", "Tiết"), ("sessions", "Buổi"), ("role", "Giáo viên"), ("measure", "Phép đo"),
           ("op", "So sánh"), ("number", "Số"), ("count_by", "Đếm theo"), ("other", "Môn thứ hai"),
           ("when", "Áp dụng khi"), ("hard", "Bắt buộc"), ("level", "Mức"), ("points", "Điểm"))
HEADERS = dict(COLUMNS)
COMPOSE = ("scope", "measure", "op", "count_by", "when", "exclude")  # các cột chỉ dùng khi Tự ghép
LEVEL = ("hard", "level", "points")  # các cột mức, mọi kiểu luật đều dùng
LEVELS = ("Thấp", "Vừa", "Cao", "Rất cao")  # cột Mức của luật ưu tiên: mức 1–4 (config.Weights.custom_levels)


@dataclass(frozen=True)
class Kind:
    key: str
    label: str  # chữ ở cột Kiểu luật
    needs: tuple[str, ...]  # cột phải ghi
    uses: tuple[str, ...]  # cột được ghi (ngoài Kiểu luật, Bắt buộc, Mức)
    note: str
    family: str = ""  # họ luật (bo_ghep.FAMILIES); Tự ghép lấy họ của phép đo


_WHAT = ("subject", "group", "tags", "grades", "classes")
_PLACE = (*_WHAT, "days", "periods", "sessions")
KINDS = (
    Kind("khong_xep", "Không xếp vào", ("subject",), _PLACE,
         "Môn (của các khối ở cột Khối; để trống: mọi khối) không xếp vào các ngày, tiết, buổi ghi ở dòng này (ghi ít "
         "nhất một trong ba cột), vd Thể dục không xếp vào tiết 1; Tin học không xếp vào Thứ 2.", "Ở đâu"),
    Kind("chi_xep", "Chỉ xếp vào", ("subject",), _PLACE,
         "Môn chỉ xếp vào các ngày, tiết, buổi ghi ở dòng này (ghi ít nhất một trong ba cột), vd Thể dục chỉ xếp vào "
         "buổi chiều.", "Ở đâu"),
    Kind("co_dinh", "Cố định vào", ("subject",), ("subject", "grades", "classes", "days", "periods", "sessions"),
         "Mỗi lớp (của các khối, lớp ghi ở dòng này) học đúng 1 tiết của Môn ở mỗi giờ ghi ở cột Ngày, Tiết, Buổi, vd "
         "Thể dục khối 1 cố định vào Thứ 3 tiết 3.", "Ở đâu"),
    Kind("gv_ngay", "Giáo viên tối đa tiết mỗi ngày", ("number",), ("role", "number"),
         "Mỗi giáo viên có chức vụ ở cột Giáo viên (để trống: mọi giáo viên) dạy tối đa Số tiết mỗi ngày.",
         "Bao nhiêu"),
    Kind("gv_lop_ngay", "Giáo viên tối đa lớp mỗi ngày", ("number",), ("role", "number"),
         "Mỗi giáo viên có chức vụ ở cột Giáo viên (để trống: mọi giáo viên) dạy tối đa Số lớp khác nhau mỗi ngày.",
         "Bao nhiêu"),
    Kind("cung_luc", "Số lớp học cùng lúc tối đa", ("subject", "number"), ("subject", "group", "tags", "grades",
                                                                            "number"),
         "Môn có tối đa Số lớp học cùng một giờ (cả trường, hoặc các khối ở cột Khối), vd phòng Tin học: 1, sân Thể "
         "dục: 2.", "Bao nhiêu"),
    Kind("rai_ngay", "Học ít nhất số ngày", ("subject", "number"), (*_WHAT, "number"),
         "Mỗi lớp học Môn ở ít nhất Số ngày khác nhau trong tuần, vd Tiếng Anh ít nhất 3 ngày.", "Bao nhiêu"),
    Kind("lien_2", "Học 2 tiết liền", ("subject",), ("subject", "grades", "classes"),
         "Môn học thành cặp 2 tiết liền, cùng người dạy: mỗi buổi 0 hoặc 2 tiết của môn (tính chung môn tăng cường "
         "cùng nhóm), vd Tiếng Anh. Bắt buộc thì số tiết/tuần phải chẵn.", "Đi cùng nhau"),
    Kind("truoc", "Học trước", ("subject", "other"), ("subject", "other", "grades", "classes"),
         "Trong một buổi có cả hai môn thì Môn học trước Môn thứ hai, vd Tiếng Việt trước Toán.", "Đi cùng nhau"),
    Kind("chi_gv", "Chỉ giáo viên dạy", ("subject", "role"), (*_PLACE, "role"),
         "Các tiết của Môn (ở các khối, lớp, ngày, tiết ghi ở dòng này) chỉ do giáo viên có chức vụ ở cột Giáo viên "
         "dạy, vd Tin học khối 3 chỉ GV Tin Học dạy; tiết 1 Thứ 2 chỉ GV chủ nhiệm dạy.", "Ai dạy"),
    Kind("nghi_gv", "Buổi nghỉ của giáo viên", (), (),
         "Giáo viên không dạy vào các buổi nghỉ ghi ở cột Buổi Nghỉ (sheet NHÂN SỰ) và nghỉ đủ số buổi ghi ở đó. Chỉ "
         "ghi Bắt buộc = Có; muốn bỏ luật thì xóa dòng.", "Ai dạy"),
    Kind("co_so_2", "Giáo viên chỉ dạy cơ sở 2", (), (),
         "Giáo viên không chủ nhiệm ghi Có ở cột Cơ sở 2 hoặc Thai Sản (sheet NHÂN SỰ) chỉ dạy các lớp ở cơ sở 2. "
         "Chỉ ghi Bắt buộc = Có; muốn bỏ luật thì xóa dòng.", "Ai dạy"),
    Kind("tu_ghep", "Tự ghép", ("measure",), tuple(k for k, _ in COLUMNS[1:] if k not in LEVEL),
         "Tự ghép câu luật: Với mỗi [phạm vi] · các tiết [Môn, Nhãn, Khối, Lớp, Ngày, Tiết, Buổi, Giáo viên] · thì "
         "[Phép đo] [So sánh] [Số] · khi [Áp dụng khi]. Xem các phép đo ở dưới."),
)
BY_KEY = {k.key: k for k in KINDS}
_BY_LABEL = {subject_key(k.label): k for k in KINDS} | {subject_key(k.key): k for k in KINDS}


def _day_label(d: int) -> str:
    return f"Thứ {d + 2}"


def _numbers(text: str) -> list[int] | None:
    """"3, 4, 5", "3-5", "3–5" -> [3, 4, 5]; None nếu có phần không phải số."""
    out = []
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:[-–]\s*(\d+))?", part)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += range(min(a, b), max(a, b) + 1)
    return sorted(set(out))


def _days(text: str) -> list[int] | None:
    """"Thứ 2, Thứ 4", "T2-T4", "2, 3" -> [0, 2] / [0, 1, 2] / [0, 1]."""
    folded = re.sub(r"\b(?:thu|t)\s*(?=\d)", "", _fold(text))
    days = _numbers(folded)
    if days is None or any(not 2 <= d <= 7 for d in days):
        return None
    return [d - 2 for d in days]


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _lookup(text: str, items) -> object | None:
    """Tìm theo nhãn, khóa hoặc tên khác (không phân biệt hoa thường, dấu cách)."""
    key = subject_key(text)
    for item in items:
        if key in {subject_key(item.label), subject_key(item.key), *(subject_key(a) for a in
                                                                      getattr(item, "aliases", ()))}:
            return item
    return None


def _op(text: str) -> str | None:
    key = subject_key(text)
    for op, label in OPS.items():
        if key in {subject_key(op), subject_key(label), *(subject_key(a) for a in bo_ghep.OP_ALIASES.get(op, ()))}:
            return op
    return None


def _when(text: str) -> tuple[tuple[str, int], ...] | None:
    """"≥ 6, chẵn", "<= số ngày" -> ((">=", 6), ("chan", 0)) / (("<=", -1),); None nếu sai."""
    out = []
    for part in re.split(r"[,;]|\bvà\b", text):
        part = _fold(part).replace("≤", "<=").replace("≥", ">=").replace(" ", "")
        if not part:
            continue
        if part in ("chan", "le"):
            out.append((part, 0))
            continue
        m = re.fullmatch(r"(<=|>=|=)(\d+|songay)", part)
        if not m:
            return None
        out.append((m.group(1), bo_ghep.NUMBER_DAYS if m.group(2) == "songay" else int(m.group(2))))
    return tuple(out) or None


def parse(values: dict, row: int, error) -> CustomRule | None:
    """Một dòng của sheet LUẬT RIÊNG ({khóa cột: ô}) -> CustomRule; lỗi gọi error(chữ). Dòng trống: None."""
    if all(_blank(v) for v in values.values()):
        return None
    raw = {k: (v if not _blank(v) else None) for k, v in values.items()}
    if raw.get("kind") is None:
        error("thiếu Kiểu luật")
        return None
    kind = _BY_LABEL.get(subject_key(raw["kind"]))
    if kind is None:
        error(f"Kiểu luật '{clean_name(raw['kind'])}' không có (các kiểu: {', '.join(k.label for k in KINDS)})")
        return None
    out: dict = {"kind": kind.key, "row": row}
    if raw.get("group_label") is not None:  # cột Nhóm của sheet LUẬT: chỉ để đọc
        out["group_label"] = clean_name(raw["group_label"])
    ok = True
    for key, _ in COLUMNS[1:]:
        value = raw.get(key)
        if value is None:
            if key in kind.needs and not (key == "subject" and raw.get("tags")):
                error(f"kiểu luật {kind.label} phải ghi cột {HEADERS[key]}")
                ok = False
            continue
        if key not in kind.uses and key not in LEVEL:
            error(f"cột {HEADERS[key]} không dùng cho kiểu luật {kind.label} (để trống)")
            ok = False
            continue
        text = clean_name(value) if not isinstance(value, (int, float)) else str(int(value))
        if key in ("subject", "other"):
            out[key] = text
        elif key == "role":  # "trừ Chủ Nhiệm": mọi GV trừ chức vụ đó
            out[key] = ", ".join(normalize(r) for r in bo_ghep.names(text))
        elif key == "grades":
            grades = _numbers(text)
            if not grades or 0 in grades:
                error(f"cột Khối ghi số khối, vd '3, 4' hoặc '3-5', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(grades)
        elif key == "classes":
            out[key] = tuple(dict.fromkeys(bo_ghep.names(text)))
        elif key == "days":
            days = _days(text)
            if not days:
                error(f"cột Ngày ghi Thứ 2 … Thứ 7, vd 'Thứ 2, Thứ 4' hoặc 'T2-T4', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(days)
        elif key == "periods":
            periods = _numbers(text)
            if not periods or 0 in periods:
                error(f"cột Tiết ghi số tiết, vd '1' hoặc '5-7', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(periods)
        elif key == "sessions":
            names = {_fold(s.name): s.name for s in (config.MORNING, config.AFTERNOON)}
            parts = [_fold(p) for p in re.split(r"[,;]", text) if p.strip()]
            if not parts or any(p.replace("buoi ", "") not in names for p in parts):
                error(f"cột Buổi ghi {config.MORNING.name} hoặc {config.AFTERNOON.name}, đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(sorted({names[p.replace('buoi ', '')] for p in parts}))
        elif key in ("tags", "exclude"):
            known = {subject_key(t): t for t in bo_ghep.tag_names()}
            tags = [known.get(subject_key(t)) for t in bo_ghep.names(text)]
            if not tags or None in tags:
                error(f"cột {HEADERS[key]} ghi tên các cột Có/Không của môn, ngày, tiết ({', '.join(known.values())}), "
                      f"đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(dict.fromkeys(tags))
        elif key == "number":
            least = 0 if kind.key == "tu_ghep" else 1
            derived = {subject_key(v): k for k, v in bo_ghep.DERIVED.items()}.get(subject_key(text))
            if derived and kind.key == "tu_ghep":
                out["derived"] = derived
            elif not text.isdigit() or int(text) < least:
                words = f" hoặc {', '.join(bo_ghep.DERIVED.values())}" if kind.key == "tu_ghep" else ""
                error(f"cột Số ghi một số nguyên {'(0, 1, 2…)' if least == 0 else 'dương'}{words}, đang ghi "
                      f"{value!r}")
                ok = False
            else:
                out[key] = int(text)
        elif key == "points":
            if not text.isdigit() or int(text) < 1:
                error(f"cột Điểm ghi một số nguyên dương (điểm trừ mỗi lần không theo luật ưu tiên), đang ghi "
                      f"{value!r}")
                ok = False
            else:
                out[key] = int(text)
        elif key in ("hard", "group"):
            folded = _fold(value) if not isinstance(value, bool) else ("co" if value else "khong")
            if folded not in _YES | _NO:
                error(f"cột {HEADERS[key]} chỉ ghi Có hoặc Không, đang ghi {value!r}")
                ok = False
            out[key] = folded in _YES
        elif key == "level":
            words = {subject_key(w): i + 1 for i, w in enumerate(LEVELS)}
            level = int(text) if text in ("1", "2", "3", "4") else words.get(subject_key(text))
            if level is None:
                error(f"cột Mức ghi {', '.join(LEVELS)} (hoặc 1–4, 4 là ưu tiên nhất), đang ghi {value!r}")
                ok = False
            else:
                out[key] = level
        elif key == "scope":
            dims = [_lookup(p, SCOPES) for p in bo_ghep.names(text.replace("×", ","))]
            if not dims or None in dims:
                error(f"cột Với mỗi ghi các chiều {', '.join(d.label for d in SCOPES)}, đang ghi {value!r}")
                ok = False
            else:
                keys = {d.key for d in dims}
                out[key] = tuple(d.key for d in SCOPES if d.key in keys)
        elif key in ("measure", "count_by"):
            found = _lookup(text, MEASURES if key == "measure" else SCOPES)
            if found is None:
                choices = MEASURES if key == "measure" else SCOPES
                error(f"cột {HEADERS[key]} ghi một trong {', '.join(c.label for c in choices)}, đang ghi {value!r}")
                ok = False
            else:
                out[key] = found.key
        elif key == "op":
            op = _op(text)
            if op is None:
                error(f"cột So sánh ghi một trong {', '.join(OPS.values())}, đang ghi {value!r}")
                ok = False
            else:
                out[key] = op
        elif key == "when":
            when = _when(text)
            if when is None:
                error(f"cột Áp dụng khi ghi điều kiện trên số tiết/tuần của môn, vd '>= 6, chẵn' hoặc '<= số ngày', "
                      f"đang ghi {value!r}")
                ok = False
            else:
                out[key] = when
    place = any(k in out for k in ("days", "periods", "sessions")) or \
        any(t in bo_ghep.slot_tags() for t in out.get("tags", ()))
    if ok and kind.key in ("khong_xep", "chi_xep", "co_dinh") and not place:
        error(f"kiểu luật {kind.label} phải ghi ít nhất một trong các cột Ngày, Tiết, Buổi")
        ok = False
    if ok and kind.key == "truoc" and subject_key(out["subject"]) == subject_key(out["other"]):
        error("Môn và Môn thứ hai phải khác nhau")
        ok = False
    if ok and kind.key == "tu_ghep":
        ok = _check_composed(out, place, error)
    if ok and kind.key in ("nghi_gv", "co_so_2") and not out.get("hard"):
        error(f"kiểu luật {kind.label} chỉ ghi Bắt buộc = Có (muốn bỏ luật thì xóa dòng)")
        ok = False
    return CustomRule(**out) if ok else None


def _check_composed(out: dict, place: bool, error) -> bool:
    """Cột nào phải ghi, cột nào để trống theo phép đo của luật tự ghép."""
    m = MEASURE[out["measure"]]
    errors = []
    need = {"op": bool(m.ops) and not m.default_op, "number": m.number, "count_by": m.count_by}
    for key, must in need.items():
        given = key in out or (key == "number" and "derived" in out)
        if must and not given:
            errors.append(f"phép đo {m.label} phải ghi cột {HEADERS[key]}")
        elif not must and given and not (key == "op" and m.ops):
            errors.append(f"cột {HEADERS[key]} không dùng cho phép đo {m.label} (để trống)")
    if not m.other and "other" in out:
        errors.append(f"cột {HEADERS['other']} không dùng cho phép đo {m.label} (để trống)")
    if "derived" in out and m.key != "so_tiet":
        errors.append(f"cột Số chỉ ghi {', '.join(bo_ghep.DERIVED.values())} cho phép đo Số tiết")
    scope_set = set(out.get("scope", ()))
    if out.get("derived") in ("tai_ngay", "tai_ngay_1") and not {"gv", "ngay"} <= scope_set:
        errors.append("cột Số ghi tải ngày thì cột Với mỗi phải có Giáo viên và Ngày")
    if out.get("derived") == "tran_ngay" and not {"lop", "mon"} <= scope_set:
        errors.append("cột Số ghi số tiết/tuần chia số ngày thì cột Với mỗi phải có Lớp và Môn")
    if "op" in out and m.ops and out["op"] not in m.ops:
        errors.append(f"phép đo {m.label} so sánh {', '.join(OPS[o] for o in m.ops)}, đang ghi {OPS[out['op']]}")
    scope = out.get("scope", ())
    if out.get("count_by") in scope:
        errors.append("cột Đếm theo không được trùng một chiều của cột Với mỗi")
    if m.key == "vi_tri" and not place:
        errors.append("phép đo Vị trí phải ghi ít nhất một trong các cột Ngày, Tiết, Buổi (hoặc nhãn ngày, tiết)")
    if m.key == "vi_tri" and scope:
        errors.append("phép đo Vị trí không dùng cột Với mỗi (để trống)")
    if m.key == "nguoi_day" and out.get("op") in ("do", "dau_tuan") and not out.get("role"):
        errors.append(f"phép đo Người dạy, so sánh {OPS[out['op']]} phải ghi chức vụ ở cột Giáo viên")
    if m.key == "nguoi_day" and out.get("op") == "cung_nguoi" and not scope:
        errors.append("phép đo Người dạy, so sánh Cùng một người phải ghi cột Với mỗi, vd Lớp, Môn")
    if m.sequence and not {"lop", "gv"} & set(scope):
        errors.append(f"phép đo {m.label} xét thứ tự các tiết trong buổi: cột Với mỗi phải có Lớp hoặc Giáo viên")
    for text in errors:
        error(text)
    return not errors


def _role_label(role: str) -> str:
    from .staff import SPECIAL_ROLES
    if role.startswith(bo_ghep.NOT):  # "trừ chủ nhiệm" -> "trừ Chủ Nhiệm"
        return bo_ghep.NOT + _role_label(role[len(bo_ghep.NOT):].strip())
    custom = {subject_key(r.name): r.name for r in config.CUSTOM_ROLES}  # chức vụ của sheet CHỨC VỤ: tên như ghi
    return config.ROLE_LABELS.get(role) if role in SPECIAL_ROLES else custom.get(subject_key(role)) or role.title()


def _when_text(when) -> str:
    """Ô Áp dụng khi, vd ">= 6, chẵn", "<= số ngày" (ngược với `_when`)."""
    return ", ".join("chẵn" if op == "chan" else "lẻ" if op == "le" else
                     f"{op} {'số ngày' if v == bo_ghep.NUMBER_DAYS else v}" for op, v in when)


def _when_say(when) -> str:
    """Áp dụng khi bằng lời, vd "số tiết/tuần của môn từ 6 trở lên và là số chẵn"."""
    parts = []
    for op, v in when:
        n = "số ngày học" if v == bo_ghep.NUMBER_DAYS else v
        parts.append({"chan": "là số chẵn", "le": "là số lẻ", ">=": f"từ {n} trở lên", "<=": f"không quá {n}",
                      "=": f"đúng {n}"}[op])
    return "số tiết/tuần của môn " + " và ".join(parts)


def level_label(rule: CustomRule) -> str:
    """Mức ưu tiên bằng chữ (Thấp, Vừa, Cao, Rất cao); dòng ghi Điểm thì lấy mức có điểm gần nhất."""
    if rule.points is None:
        return LEVELS[rule.level - 1]
    levels = config.Weights().custom_levels
    i = min(range(len(levels)), key=lambda k: abs(math.log(rule.points / levels[k])))
    return LEVELS[i]


def cells(rule: CustomRule) -> dict:
    """Các ô của luật khi ghi ra sheet LUẬT ({khóa cột: giá trị}), ngược với `parse`."""
    from .rules import NO, YES
    role = ", ".join(_role_label(r) for r in bo_ghep.names(rule.role))
    return {"kind": BY_KEY[rule.kind].label, "scope": ", ".join(SCOPE[d].label for d in rule.scope) or None,
            "subject": rule.subject or None, "group": YES if rule.group else None,
            "tags": ", ".join(rule.tags) or None, "grades": ", ".join(map(str, rule.grades)) or None,
            "classes": ", ".join(rule.classes) or None,
            "days": ", ".join(_day_label(d) for d in rule.days) or None,
            "periods": ", ".join(map(str, rule.periods)) or None, "sessions": ", ".join(rule.sessions) or None,
            "role": role or None, "measure": MEASURE[rule.measure].label if rule.measure else None,
            "op": OPS[rule.op] if rule.op else None,
            "number": bo_ghep.DERIVED[rule.derived] if rule.derived else rule.number,
            "count_by": SCOPE[rule.count_by].label if rule.count_by else None, "other": rule.other or None,
            "when": _when_text(rule.when) or None, "hard": YES if rule.hard else NO,
            "level": None if rule.hard or rule.points is not None else LEVELS[rule.level - 1],
            "exclude": ", ".join(rule.exclude) or None, "points": None if rule.hard else rule.points}


def _teacher(role: str) -> str:
    """Chức vụ khi đọc câu: "chủ nhiệm" -> "GV chủ nhiệm", "Tiếng Anh" -> "GV Tiếng Anh", "trừ ..." giữ "trừ"."""
    if role.startswith(bo_ghep.NOT):
        return bo_ghep.NOT + _teacher(role[len(bo_ghep.NOT):].strip())
    name = _role_label(role)
    if role in (config.ROLE_HOMEROOM, config.ROLE_GENERAL):
        return f"GV {name.lower()}"
    return name if _fold(name).startswith(("gv ", "giao vien")) else f"GV {name}"


def _teachers(rule: CustomRule) -> str:
    """Các chức vụ ở cột Giáo viên bằng lời, vd "GV bộ môn", "giáo viên trừ GV chủ nhiệm"."""
    names = bo_ghep.names(rule.role)
    keep = [_teacher(r) for r in names if not r.startswith(bo_ghep.NOT)]
    skip = [_teacher(r[len(bo_ghep.NOT):].strip()) for r in names if r.startswith(bo_ghep.NOT)]
    return ", ".join(keep) + (f"{' ' if keep else 'giáo viên '}trừ {', '.join(skip)}" if skip else "")


def _what(rule: CustomRule) -> str:
    """Các tiết luật xét, vd "Thể dục khối 3, 4", "môn có nhãn Môn nặng lớp 3/1"; trống: mọi tiết."""
    parts = [rule.subject + (" (cả môn tăng cường)" if rule.group else "") if rule.subject else ""]
    tags = [t for t in rule.tags if t not in bo_ghep.slot_tags()]
    if tags:
        parts.append(f"{'môn có nhãn' if not rule.subject else '(môn có nhãn'} {', '.join(tags)}"
                     f"{')' if rule.subject else ''}")
    if rule.grades:
        parts.append(f"khối {', '.join(map(str, rule.grades))}")
    if rule.classes:
        parts.append(f"lớp {', '.join(rule.classes)}")
    skip = [t for t in rule.exclude if t not in bo_ghep.slot_tags()]
    if skip:
        parts.append(f"trừ môn có nhãn {', '.join(skip)}")
    return " ".join(p for p in parts if p)


def _where(rule: CustomRule) -> str:
    """Các giờ học luật ghi, vd "buổi sáng Thứ 2 tiết 1", "giờ có nhãn Hạn chế môn nặng"."""
    slot_tags = [t for t in rule.tags if t in bo_ghep.slot_tags()]
    skip = [t for t in rule.exclude if t in bo_ghep.slot_tags()]
    return " ".join(filter(None, [
        rule.sessions and f"buổi {', '.join(s.lower() for s in rule.sessions)}",
        rule.days and ", ".join(_day_label(d) for d in rule.days),
        rule.periods and f"tiết {', '.join(map(str, rule.periods))}",
        slot_tags and f"giờ có nhãn {' hoặc '.join(slot_tags)}",
        skip and f"trừ giờ có nhãn {', '.join(skip)}"]))


def _who(rule: CustomRule) -> str:
    return f"Mỗi {_teachers(rule)}" if rule.role else "Mỗi giáo viên"


def describe(rule: CustomRule) -> str:
    """Luật bằng lời, vd "Thể dục khối 3, 4 không xếp vào tiết 1 (bắt buộc)". Dòng đúng dạng gốc của một luật có sẵn
    đọc bằng tên của luật đó (luat_co_san.title)."""
    from .luat_co_san import title
    who, where = _what(rule), _where(rule)
    text = title(rule) or {
        "khong_xep": lambda: f"{who} không xếp vào {where}",
        "chi_xep": lambda: f"{who} chỉ xếp vào {where}",
        "lien_2": lambda: f"{who} học 2 tiết liền",
        "truoc": lambda: f"{who} học trước {rule.other} trong buổi",
        "gv_ngay": lambda: f"{_who(rule)} dạy tối đa {rule.number} tiết mỗi ngày",
        "cung_luc": lambda: f"{who} có tối đa {rule.number} lớp học cùng lúc",
        "co_dinh": lambda: f"{who} cố định vào {where}",
        "gv_lop_ngay": lambda: f"{_who(rule)} dạy tối đa {rule.number} lớp mỗi ngày",
        "rai_ngay": lambda: f"{who} học ít nhất {rule.number} ngày mỗi tuần",
        "chi_gv": lambda: f"{who}{' ' + where if where else ''} chỉ do {_teachers(rule)} dạy",
        "nghi_gv": lambda: "Giáo viên không dạy vào buổi nghỉ ghi ở cột Buổi Nghỉ và nghỉ đủ số buổi ghi ở đó",
        "co_so_2": lambda: "Giáo viên không chủ nhiệm ghi Cơ sở 2 hoặc Thai Sản chỉ dạy các lớp ở cơ sở 2",
        "tu_ghep": lambda: composed(rule),
    }[rule.kind]()
    return text + level_text(rule)


def level_text(rule: CustomRule) -> str:
    return " (bắt buộc)" if rule.hard else f" (ưu tiên {level_label(rule).lower()})"


def composed(rule: CustomRule) -> str:
    """Câu của luật tự ghép, vd "Mỗi lớp, mỗi ngày: học tối đa 1 tiết Toán"."""
    m = MEASURE[rule.measure]
    scope = rule.scope
    teacher_in_scope = "gv" in scope and rule.role
    parts = [f"mỗi {_teachers(rule) if d == 'gv' and rule.role else SCOPE[d].unit}" for d in scope]
    where = _where(rule) if m.key != "vi_tri" else ""
    if where.startswith("giờ"):  # "các tiết ở giờ có nhãn …"
        where = "ở " + where
    teach = rule.role and not teacher_in_scope and not (m.key == "nguoi_day" and rule.op in ("do", "dau_tuan"))
    what = " ".join(filter(None, [_what(rule), where, f"của {_teachers(rule)}" if teach else ""]))
    some = f"tiết {what}" if what else "tiết"  # "tiết Toán khối 3", "tiết"
    each = f"các tiết {what}" if what else "các tiết"
    verb = "dạy" if "gv" in scope else "học" if "lop" in scope else "có"
    op = {"<=": "tối đa", ">=": "ít nhất", "=": "đúng"}.get(rule.op, "")
    other = f"tiết {rule.other}" if rule.other else "tiết môn khác cùng nhóm"
    n = rule.number

    def count() -> str:
        if rule.derived:
            limit = {"<=": "không quá", ">=": "ít nhất bằng", "=": "đúng bằng"}[rule.op]
            return f"số {some} {limit} {bo_ghep.DERIVED[rule.derived]}"
        return f"{verb} {op} {n} {some}"

    def distinct() -> str:
        unit = SCOPE[rule.count_by].unit
        return f"{verb}{' ' + what if what else ''} {op} {n} {unit}{' khác nhau' if n != 1 else ''}"

    def teacher() -> str:
        role = _teachers(rule)
        return {"do": f"{each if what else 'mọi tiết'} do {role} dạy",
                "cung_nguoi": f"{each} do cùng một giáo viên dạy",
                "lien_cung_nguoi": f"hai {some} liền nhau do cùng một giáo viên dạy",
                "dau_tuan": f"tiết đầu tuần{' của ' + what if what else ''} do {role} dạy, tiết của giáo viên khác "
                            f"không đứng trước"}[rule.op or "do"]

    def gap() -> str:
        if rule.op == "trong_tiet":
            return f"{each} không có tiết trống xen giữa" if n == 0 else f"tối đa {n} tiết trống giữa {each}"
        return f"{each} xếp ở tiết cuối buổi" if n == 0 else f"{each} cách cuối buổi không quá {n} tiết"

    body = {
        "so_tiet": count,
        "so_khac": distinct,
        "vi_tri": lambda: f"{each if what else 'mọi tiết'} {'chỉ xếp vào' if rule.op == 'trong' else 'không xếp vào'} "
                          f"{_where(rule)}",
        "lien": lambda: f"{each} trong một buổi đứng liền nhau",
        "cap": lambda: f"{each} xếp thành cặp 2 tiết liền trong buổi",
        "thu_tu": lambda: f"{each} đứng {'sau' if rule.op == 'sau' else 'trước'} các {other}",
        "di_kem": lambda: f"có {some} thì cũng có {other}",
        "nguoi_day": teacher,
        "khoang_cach": gap,
    }[m.key]()
    when = f", khi {_when_say(rule.when)}" if rule.when else ""
    text = f"{', '.join(parts)}: {body}{when}" if parts else f"{body}{when}"
    return text[0].upper() + text[1:]


def label(rule: CustomRule) -> str:
    """Tên luật khi báo lỗi: sheet và dòng của luật (dòng mặc định của file không có sheet LUẬT: Luật có sẵn)."""
    if not rule.row:
        return f"Luật có sẵn: {describe(rule)}"
    return f"{RULES_SHEET if config.RULES is not None else SHEET} dòng {rule.row}: {describe(rule)}"


# ---- dùng khi xếp (đọc config hiện tại, gọi trong rules.applied); phần việc ở tkb/bo_ghep.py ----

def banned(subject: str, grade: int, class_name: str | None = None, curriculum=None) -> set[tuple[int, int]]:
    """Ô mà môn của khối (lớp) không được học theo các luật bắt buộc (dùng trong solver.allowed_slots)."""
    return bo_ghep.banned(subject, grade, class_name, curriculum)


def forced_pairs(grade: int, totals: dict[str, int]) -> set[str]:
    """Nhóm môn của khối phải học 2 tiết liền theo luật bắt buộc (số tiết chẵn; lẻ thì precheck báo lỗi)."""
    return bo_ghep.forced_pairs(grade, totals)


def day_cap(teacher) -> int | None:
    """Số tiết tối đa mỗi ngày của GV theo luật bắt buộc (None: không giới hạn); dùng trong phan_cong.teacher_slots."""
    return bo_ghep.day_cap(teacher)


def build(m, problem, x: dict, z: dict, dom: dict, teachers_of: dict, w: config.Weights) -> list:
    """Ràng buộc và mục tiêu của các luật riêng trong mô hình CP-SAT (solver.build_timetable); trả về các số hạng
    mục tiêu."""
    return bo_ghep.build(m, problem, x, z, dom, teachers_of, w)


def check(problem, lessons) -> list[str]:
    """Kiểm tra độc lập các luật riêng bắt buộc (checker.check)."""
    return [f"{label(L.rule)}: {text}" for L, _, _, text in bo_ghep.violations(problem, lessons, hard=True)]


def qa(problem, lessons, w: config.Weights):
    """Chi phí của các luật riêng ưu tiên theo (lớp, ngày), như mục tiêu trong `build` (lns._Search.qa)."""
    return bo_ghep.qa(problem, lessons, w)


def soft_report(problem, lessons) -> list[str]:
    """Số lần không theo từng luật riêng ưu tiên (in ra màn hình sau khi xếp)."""
    if not any(not r.hard for r in config.CUSTOM_RULES):
        return []
    count = bo_ghep.soft_counts(problem, lessons)
    return [f"{label(r)}: {count[r]} lần không theo" for r in config.CUSTOM_RULES if not r.hard]


def validate(problem) -> list[str]:
    """Lỗi ghi của luật riêng chỉ thấy khi có chương trình học và nhân sự: môn, chức vụ hay lớp không có."""
    return bo_ghep.validate(problem, SHEET, _role_label)


def precheck(problem) -> list[str]:
    """Mâu thuẫn chắc chắn của luật riêng bắt buộc, tìm bằng phép đếm: luật vị trí để lại ít ô hơn số tiết, môn phải
    học 2 tiết liền mà số tiết lẻ, số lớp cùng lúc không đủ ô, luật cần nhiều tiết hơn có thể. Luật ghi sai
    (validate) thì bỏ qua."""
    invalid = {int(line.split(":")[0].split("dòng ")[1]) for line in validate(problem)}
    return bo_ghep.precheck(problem, label, skip=invalid)
