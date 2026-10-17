"""Đo chất lượng TKB của một file vào: xếp (mỗi hạt giống CP-SAT một lần), chấm bằng bộ kiểm tra độc lập (checker) và
sheet Chất lượng (writer.quality_rows), in bảng. Không đổi gì của chương trình: chỉ chạy, đo, in bảng.

Dùng để so hai phiên bản chương trình (vd trước và sau khi đổi cách hạ một luật, docs/Thiet_Ke_Gop_Luat.md): chạy
công cụ ở hai commit, cùng file, cùng hằng số, cùng hạt giống; một lần chạy không đủ (mục 3.3), so trung bình nhiều
hạt giống. In thêm kích thước mô hình CP-SAT (số biến, số ràng buộc).

Không in họ tên, không ghi file ra: dùng được với file thật của trường.
  python tools/do_chat_luong.py data/INPUT_V8.xlsx --mode bu_gio --max-overtime 3 --time-limit 300
  python tools/do_chat_luong.py <file> --seed 0,1,2    # 3 hạt giống CP-SAT, in điểm trung bình
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tkb import config  # noqa: E402
from tkb.__main__ import use_utf8_output  # noqa: E402
from tkb.bo_ghep import know_staff  # noqa: E402
from tkb.checker import check  # noqa: E402
from tkb.program import read_program  # noqa: E402
from tkb.rules import applied, read_rules  # noqa: E402
from tkb.solver import SolveError, _assignment, build_timetable, solve  # noqa: E402
from tkb.staff import InputError, read_staff  # noqa: E402
from tkb.writer import quality_rows  # noqa: E402


def model_size(staff, curriculum, settings) -> tuple[int, int]:
    """(số biến, số ràng buộc) của mô hình xếp giờ với phân công cố định (như lần xếp thật)."""
    _, _, work, fixed, _, _ = _assignment(staff, curriculum, settings, lambda *_: None)
    proto = build_timetable(work, settings, fixed).model.proto
    return len(proto.variables), len(proto.constraints)


def measure(path: str, name: str, settings: config.Settings) -> dict:
    """Một lần xếp: {name, status, seconds, vars, cons, errors, soft, rows: {câu: (lần, điểm)}, history}."""
    out = {"name": name}
    curriculum = read_program(path)
    staff = read_staff(path, subjects=[s for req in curriculum.values() for s in req])
    know_staff(staff)
    try:
        out["vars"], out["cons"] = model_size(staff, curriculum, settings)
        start = time.time()
        sol = solve(staff, curriculum, settings, log=lambda *_: None)
        out["seconds"] = round(time.time() - start)
    except (InputError, SolveError) as exc:
        out["status"] = f"không xếp được: {str(exc).splitlines()[0]}"
        return out
    out["status"] = sol.status
    out["history"] = next((n for n in sol.notes if n.startswith("Xếp giờ:")), "")
    out["errors"] = len(check(sol.problem, sol.lessons, settings.student_rules))
    rows = quality_rows(sol, settings.student_rules)
    out["soft"] = rows[-1][4]
    out["rows"] = {r[1]: (r[3], r[4]) for r in rows[:-1] if isinstance(r[3], int)}
    return out


def report(results: list[dict]) -> None:
    print("| Lần xếp | Kết quả | Lỗi luật bắt buộc | Điểm trừ (luật ưu tiên) | Biến | Ràng buộc | Giây |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['name']} | {r['status']} | {r.get('errors', '')} | {r.get('soft', '')} | {r.get('vars', '')} | "
              f"{r.get('cons', '')} | {r.get('seconds', '')} |")
    solved = [r for r in results if "rows" in r]
    names = list(solved[0]["rows"]) if solved else []
    shown = [n for n in names if any((r["rows"].get(n) or (0, 0))[0] for r in solved)]
    if shown:
        print()
        print("| Luật | " + " | ".join(r["name"] for r in solved) + " |")
        print("|---|" + "---|" * len(solved))
        for n in shown:
            cells = [f"{c[0]} lần, {c[1] or 0} điểm" if (c := r["rows"].get(n)) else "" for r in solved]
            print(f"| {n} | " + " | ".join(cells) + " |")
    for r in solved:
        if r.get("history"):
            print(f"{r['name']}: {r['history']}")


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    ap = argparse.ArgumentParser(prog="python tools/do_chat_luong.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="File vào")
    ap.add_argument("--mode", choices=config.MODES, default=config.MODE_HIRE)
    ap.add_argument("--max-overtime", type=int, default=config.OVERTIME_MAX)
    ap.add_argument("--time-limit", type=float, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-student-rules", action="store_true")
    ap.add_argument("--seed", default="0", help="Hạt giống của CP-SAT, vd 0,1,2: mỗi hạt giống một lần xếp")
    args = ap.parse_args(argv)
    seeds = [int(x) for x in args.seed.split(",")]
    results = []
    with applied(read_rules(args.file)):
        for seed in seeds:
            settings = config.Settings(student_rules=not args.no_student_rules, mode=args.mode,
                                       overtime_max=args.max_overtime, time_limit=args.time_limit or None,
                                       workers=args.workers, seed=seed)
            print(f"Đang xếp (hạt giống {seed})…", file=sys.stderr)
            results.append(measure(args.file, f"#{seed}", settings))
    report(results)
    points = [r["soft"] for r in results if "soft" in r]
    if len(seeds) > 1 and points:
        print()
        print(f"Điểm trừ trung bình {round(sum(points) / len(points))}, thấp nhất {min(points)}, cao nhất "
              f"{max(points)} ({len(points)}/{len(seeds)} lần xếp được)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
