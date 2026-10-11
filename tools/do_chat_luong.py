"""Đo chất lượng TKB khi luật có sẵn xếp bằng mã hóa riêng (luật gốc) và khi xếp bằng bộ ghép luật, để chuẩn bị gộp
luật có sẵn vào bộ ghép (docs/Thiet_Ke_Gop_Luat.md). Không đổi gì của chương trình: chỉ chạy, đo, in bảng.

Mỗi cách xếp (biến thể) là một lần solver.solve trên cùng file vào, cùng thời gian:
  goc          luật có sẵn ở dạng gốc xếp bằng mã hóa riêng (như chương trình hiện nay)
  ghep         mọi luật có sẵn có câu bộ ghép (trừ Buổi nghỉ, Giáo viên chỉ dạy cơ sở 2) tắt mã hóa riêng (config.OFF)
               và xếp chính các dòng đó bằng bộ ghép (config.CUSTOM_RULES)
  ghep:k1,k2   chỉ các luật có khóa k1, k2 (luat_co_san.NATIVES) xếp bằng bộ ghép
Mọi TKB chấm cùng một cách: bộ kiểm tra độc lập (checker) và sheet Chất lượng (writer.quality_rows) với các luật như
file vào (luật gốc), nên điểm trừ so được với nhau. In thêm kích thước mô hình CP-SAT (số biến, số ràng buộc).

Không in họ tên, không ghi file ra: dùng được với file thật của trường.
  python tools/do_chat_luong.py data/INPUT_V8.xlsx --mode bu_gio --max-overtime 3 --time-limit 300 goc ghep
  python tools/do_chat_luong.py <file> --tung-luat     # mỗi luật có sẵn một biến thể ghep:<khóa>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tkb import config, luat_co_san  # noqa: E402
from tkb.__main__ import use_utf8_output  # noqa: E402
from tkb.bo_ghep import know_staff  # noqa: E402
from tkb.checker import check  # noqa: E402
from tkb.program import read_program  # noqa: E402
from tkb.rules import applied, read_rules  # noqa: E402
from tkb.allocation import build_problem  # noqa: E402
from tkb.solver import Solution, SolveError, _assignment, build_timetable, saved_lessons, solve  # noqa: E402
from tkb.staff import InputError, read_staff  # noqa: E402
from tkb.writer import quality_rows  # noqa: E402

NATIVE_ONLY = ("buoi_nghi", "co_so_2")  # chỉ có dạng gốc (cột của sheet NHÂN SỰ), không có câu bộ ghép
# Luật gốc phải thay cùng nhau: tắt riêng HĐTN cố định thì course HĐTN gộp một, cả tuần chỉ ở ngày HĐTN còn lại
# (allocation.build_problem), trái với dòng "đúng 1 tiết ở giờ cố định" của bộ ghép.
TOGETHER = {"hdtn_co_dinh": ("hdtn_co_dinh", "hdtn_ngay")}


def replaceable() -> list[str]:
    """Các luật có sẵn đang bật có câu bộ ghép (thay được bằng bộ ghép)."""
    return [n.key for n in luat_co_san.NATIVES if n.key not in NATIVE_ONLY and config.on(n.key)]


def overrides(variant: str) -> dict:
    """Giá trị config của một biến thể (gọi trong rules.applied của file vào)."""
    if variant == "goc":
        return {}
    keys = replaceable() if variant == "ghep" else variant.split(":", 1)[1].split(",")
    unknown = [k for k in keys if k not in luat_co_san.BY_KEY or k in NATIVE_ONLY]
    if unknown:
        raise SystemExit(f"Khóa luật không thay được: {', '.join(unknown)} (các khóa: {', '.join(replaceable())})")
    rows = [r for r in luat_co_san.rows() if not r.off and (n := luat_co_san.native_of(r)) is not None
            and n.key in keys]
    zero = {n.weight: 0 for n in luat_co_san.NATIVES if n.key in keys and n.weight}  # như luat_co_san.apply
    return {"OFF": frozenset(config.OFF) | frozenset(keys), "WEIGHTS": {**config.WEIGHTS, **zero},
            "CUSTOM_RULES": [*config.CUSTOM_RULES, *rows]}


def model_size(staff, curriculum, settings) -> tuple[int, int]:
    """(số biến, số ràng buộc) của mô hình xếp giờ với phân công cố định (như lần xếp thật)."""
    _, _, work, fixed, _, _ = _assignment(staff, curriculum, settings, lambda *_: None)
    proto = build_timetable(work, settings, fixed).model.proto
    return len(proto.variables), len(proto.constraints)


def measure(path: str, variant: str, settings: config.Settings) -> dict:
    """Một lần xếp: {variant, status, seconds, vars, cons, errors, soft, rows: {câu: (lần, điểm)}, history}."""
    out = {"variant": variant}
    curriculum = read_program(path)
    staff = read_staff(path, subjects=[s for req in curriculum.values() for s in req])
    know_staff(staff)
    try:
        with applied(overrides(variant)):
            out["vars"], out["cons"] = model_size(staff, curriculum, settings)
            start = time.time()
            sol = solve(staff, curriculum, settings, log=lambda *_: None)
            out["seconds"] = round(time.time() - start)
    except (InputError, SolveError) as exc:
        out["status"] = f"không xếp được: {str(exc).splitlines()[0]}"
        return out
    out["status"] = sol.status
    out["history"] = next((n for n in sol.notes if n.startswith("Xếp giờ:")), "")
    # Chấm theo luật của file vào (luật gốc bật), như sheet Chất lượng của file thống kê: dựng lại bài toán theo
    # luật gốc (vd tiết HĐTN cố định là một course riêng) rồi đọc lại các tiết như đọc TKB đã xếp.
    counts = {role: len(titles) for role, titles in sol.problem.supplement_roles.items()}
    over = settings.overtime_max if settings.mode == config.MODE_OVERTIME else 0
    problem = build_problem(staff, curriculum, counts, overtime_max=over)
    cells = [(les.class_name, config.DAYS[les.day], les.period, sol.problem.subject_label(les.subject),
              sol.problem.teachers[les.teacher].code, les.overtime, False, "") for les in sol.lessons]
    lessons, errors = saved_lessons(problem, cells)
    out["errors"] = len(errors or check(problem, lessons, settings.student_rules))
    rows = quality_rows(Solution(problem, sol.status, lessons, sol.objective, sol.best_bound, sol.wall_time,
                                 sol.stage), settings.student_rules)
    out["soft"] = rows[-1][4]
    out["rows"] = {r[1]: (r[3], r[4]) for r in rows[:-1] if isinstance(r[3], int)}
    return out


def report(results: list[dict]) -> None:
    print("| Biến thể | Kết quả | Lỗi luật bắt buộc | Điểm trừ (luật ưu tiên) | Biến | Ràng buộc | Giây |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['variant']} | {r['status']} | {r.get('errors', '')} | {r.get('soft', '')} | {r.get('vars', '')} | "
              f"{r.get('cons', '')} | {r.get('seconds', '')} |")
    solved = [r for r in results if "rows" in r]
    names = list(solved[0]["rows"]) if solved else []
    diff = [n for n in names if len({r["rows"].get(n) for r in solved}) > 1]
    if diff:
        print()
        print("| Luật | " + " | ".join(r["variant"] for r in solved) + " |")
        print("|---|" + "---|" * len(solved))
        for n in diff:
            cells = [f"{c[0]} lần, {c[1] or 0} điểm" if (c := r["rows"].get(n)) else "" for r in solved]
            print(f"| {n} | " + " | ".join(cells) + " |")
    for r in solved:
        if r.get("history"):
            print(f"{r['variant']}: {r['history']}")


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    ap = argparse.ArgumentParser(prog="python tools/do_chat_luong.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="File vào")
    ap.add_argument("variants", nargs="*", default=["goc", "ghep"], help="goc, ghep, ghep:<khóa>[,<khóa>…]")
    ap.add_argument("--tung-luat", action="store_true", help="Thêm một biến thể ghep:<khóa> cho mỗi luật có sẵn")
    ap.add_argument("--mode", choices=config.MODES, default=config.MODE_HIRE)
    ap.add_argument("--max-overtime", type=int, default=config.OVERTIME_MAX)
    ap.add_argument("--time-limit", type=float, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-student-rules", action="store_true")
    args = ap.parse_args(argv)
    settings = config.Settings(student_rules=not args.no_student_rules, mode=args.mode,
                               overtime_max=args.max_overtime, time_limit=args.time_limit or None,
                               workers=args.workers)
    results = []
    with applied(read_rules(args.file)):
        variants = list(args.variants) + ([f"ghep:{','.join(TOGETHER.get(k, (k,)))}" for k in replaceable()]
                                          if args.tung_luat else [])
        for variant in variants:
            print(f"Đang xếp: {variant}…", file=sys.stderr)
            results.append(measure(args.file, variant, settings))
    report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
