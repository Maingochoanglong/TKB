"""Phòng học dùng chung (sheet PHÒNG, config.ROOMS): phòng nào hợp với tiết nào, ràng buộc sức chứa trong mô hình xếp
giờ, xếp phòng cho từng tiết sau khi xếp giờ, kiểm tra độc lập.

- Một tiết (course: lớp, môn) cần phòng nếu có ít nhất một phòng ghi môn đó (hay một nhãn môn có môn đó), khối của
  lớp (cột Khối trống: mọi khối), ở cơ sở của lớp. Khi đó tiết học ở một trong các phòng đó (`Problem.room_fit`);
  môn không có phòng nào ghi thì học ở lớp như trước.
- Các course hợp cùng một tập phòng là một loại; các loại dùng chung phòng nối thành một cụm (`clusters`). Cụm một
  loại (vd các phòng Tin giống nhau): mỗi giờ học số tiết của cụm ≤ tổng sức chứa. Cụm nhiều loại (vd Phòng Tin 2 chỉ
  khối 4, 5): biến nguyên y[loại, phòng, giờ] = số tiết của loại học ở phòng, như một bài toán luồng, nên có y thỏa
  là xếp được phòng cho mọi tiết.
- Xếp phòng cho từng tiết (`assign`) làm sau khi xếp giờ: mỗi giờ học một bài toán luồng chi phí nhỏ nhất
  (phan_cong.MinCostFlow: Python thuần, thứ tự cố định nên mọi máy như nhau), ưu tiên phòng lớp đó đã học môn đó ở
  các giờ trước. Phòng không vào mã kết quả (mã băm lớp, ngày, tiết, môn, GV).

Không có sheet PHÒNG (config.ROOMS rỗng) thì không có gì ở đây thêm vào mô hình: mã kết quả không đổi.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import config
from .staff import CAMPUS1, InputError, _fold, class_sort_key, subject_key


def fit(courses, campus_of: dict[str, str], subject_labels: dict[str, str]) -> dict[int, tuple[int, ...]]:
    """course -> chỉ số các phòng (config.ROOMS) hợp với tiết của course (trống: course không cần phòng). Báo lỗi
    (InputError, mọi lỗi cùng lúc) nếu phòng ghi môn, nhãn môn hay cơ sở không có."""
    from .bo_ghep import subject_tags
    from .program import canonical_subject
    if not config.ROOMS:
        return {}
    known = {subject_key(s): s for s in subject_labels} | {subject_key(label): s for s, label in subject_labels.items()}
    tags = {subject_key(head): members for head, members in subject_tags().items()}
    campuses = {_fold(n) for n in campus_of.values()} | {_fold(CAMPUS1)}
    errors: list[str] = []
    rooms: list[tuple[set[str], set, str]] = []
    for room in config.ROOMS:
        where = f"{config.ROOMS_SHEET}, dòng {room.row}" if room.row else f"Phòng {room.name}"
        subjects: set[str] = set()
        for name in room.subjects:
            key = subject_key(name)
            if key in known or subject_key(canonical_subject(name)) in known:
                subjects.add(known.get(key) or known[subject_key(canonical_subject(name))])
            elif key in tags:
                subjects |= {s for s in tags[key] if s in subject_labels}
            else:
                errors.append(f"{where}: không có môn hay nhãn môn '{name}' ở sheet {config.PROGRAM_SHEET}")
        campus = _fold(room.campus or CAMPUS1)
        if campus not in campuses:
            errors.append(f"{where}: không có lớp nào ở cơ sở '{room.campus}' (cột Cơ sở của sheet "
                          f"{config.CLASSES_SHEET})")
        rooms.append((subjects, {_fold(str(g)) for g in room.grades}, campus))
    if errors:
        raise InputError("Sheet PHÒNG có lỗi:\n  " + "\n  ".join(dict.fromkeys(errors)))
    out: dict[int, tuple[int, ...]] = {}
    for c in courses:
        here = _fold(campus_of.get(c.class_name) or CAMPUS1)
        rs = tuple(i for i, (subjects, grades, campus) in enumerate(rooms)
                   if c.subject in subjects and (not grades or _fold(str(c.grade)) in grades) and campus == here)
        if rs:
            out[c.id] = rs
    return out


def clusters(problem) -> list[tuple[dict[tuple[int, ...], list[int]], tuple[int, ...]]]:
    """Các cụm phòng: [({tập phòng của một loại: các course}, các phòng của cụm)]. Hai loại có chung một phòng thì
    cùng cụm; thứ tự theo chỉ số phòng nhỏ nhất (cố định)."""
    kinds: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for cid, rooms in sorted(problem.room_fit.items()):
        kinds[rooms].append(cid)
    parent = list(range(len(problem.rooms)))

    def find(r: int) -> int:
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r

    for rooms in kinds:
        for r in rooms[1:]:
            parent[find(r)] = find(rooms[0])
    groups: dict[int, dict[tuple[int, ...], list[int]]] = defaultdict(dict)
    for rooms in sorted(kinds):
        groups[find(rooms[0])][rooms] = kinds[rooms]
    out = []
    for root in sorted(groups, key=lambda g: min(min(k) for k in groups[g])):
        members = groups[root]
        out.append((members, tuple(sorted({r for k in members for r in k}))))
    return out


def _flow(problem, items: list[tuple[int, ...]], rooms: tuple[int, ...], prefer=None):
    """Xếp các tiết `items` (mỗi tiết là tập phòng hợp) vào phòng, mỗi phòng không quá sức chứa: chỉ số phòng của
    từng tiết (None: không còn chỗ). `prefer[i]`: phòng nên dùng cho tiết i (giá 0, phòng khác giá 1)."""
    from .phan_cong import MinCostFlow
    source, sink = 0, 1
    node = {r: 2 + len(items) + j for j, r in enumerate(rooms)}
    mcf = MinCostFlow(2 + len(items) + len(rooms))
    arcs = []
    for i, fits in enumerate(items):
        mcf.add(source, 2 + i, 1, 0)
        want = (prefer or {}).get(i)
        arcs.append([(r, mcf.add(2 + i, node[r], 1, 0 if want in (None, r) else 1)) for r in fits])
    for r in rooms:
        mcf.add(node[r], sink, problem.rooms[r].capacity, 0)
    mcf.run(source, sink)
    return [next((r for r, ref in refs if mcf.used(ref)), None) for refs in arcs]


def constrain(m, problem, x: dict) -> None:
    """Ràng buộc phòng trong mô hình CP-SAT (solver.build_timetable): mỗi giờ học, các tiết cần phòng của một cụm xếp
    được vào các phòng của cụm. Giờ mà mọi tiết có thể có của cụm đều xếp được thì không thêm gì."""
    for kinds, rooms in clusters(problem):
        capacity = sum(problem.rooms[r].capacity for r in rooms)
        for s in problem.slots:
            terms = {k: [x[cid, s] for cid in cids if (cid, s) in x] for k, cids in kinds.items()}
            possible = [k for k, lits in terms.items() for _ in lits]
            if len(possible) <= capacity and None not in _flow(problem, possible, rooms):
                continue
            if len(kinds) == 1:
                m.Add(sum(lit for lits in terms.values() for lit in lits) <= capacity)
                continue
            y: dict[tuple[tuple[int, ...], int], object] = {}
            for k, lits in terms.items():
                if not lits:
                    continue
                for r in k:
                    y[k, r] = m.NewIntVar(0, min(problem.rooms[r].capacity, len(lits)),
                                          f"phong_{min(k)}_{r}_{s[0]}_{s[1]}")
                m.Add(sum(y[k, r] for r in k) == sum(lits))
            for r in rooms:
                used = [v for (k, room), v in y.items() if room == r]
                if used:
                    m.Add(sum(used) <= problem.rooms[r].capacity)


def campus(problem, room) -> str:
    """Tên cơ sở của phòng, viết như cột Cơ sở của sheet LỚP (trống: Cơ sở 1)."""
    names = {_fold(n): n for n in problem.campuses}
    return names.get(_fold(room.campus or CAMPUS1), room.campus or CAMPUS1)


def labels(problem) -> list[str]:
    """Tên từng phòng để phân biệt: tên phòng, thêm tên cơ sở nếu cơ sở khác có phòng cùng tên."""
    count = Counter(_fold(r.name) for r in problem.rooms)
    return [f"{r.name} ({campus(problem, r)})" if count[_fold(r.name)] > 1 else r.name for r in problem.rooms]


def assign(problem, lessons) -> list[str]:
    """Tên phòng của từng tiết (cùng thứ tự với `lessons`; "" nếu tiết học ở lớp hoặc không còn chỗ)."""
    return [problem.rooms[r].name if r is not None else "" for r in placed(problem, lessons)]


def placed(problem, lessons) -> list[int | None]:
    """Chỉ số phòng của từng tiết (cùng thứ tự với `lessons`; None nếu tiết học ở lớp hoặc không còn chỗ). Mỗi giờ
    học xếp theo luồng; một lớp học một môn ở phòng nào thì các giờ sau ưu tiên phòng đó."""
    out: list[int | None] = [None] * len(lessons)
    if not problem.room_fit:
        return out
    used: dict[tuple[str, str], Counter] = defaultdict(Counter)
    by_slot: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, les in enumerate(lessons):
        if les.course_id in problem.room_fit:
            by_slot[les.day, les.period].append(i)
    groups = clusters(problem)
    for s in sorted(by_slot):
        for kinds, rooms in groups:
            here = [i for i in by_slot[s] if problem.room_fit[lessons[i].course_id] in kinds]
            here.sort(key=lambda i: (class_sort_key(lessons[i].class_name), lessons[i].subject))
            prefer = {}
            for j, i in enumerate(here):
                seen = used[lessons[i].class_name, lessons[i].subject]
                if seen:
                    prefer[j] = min(seen, key=lambda r: (-seen[r], r))
            got = _flow(problem, [problem.room_fit[lessons[i].course_id] for i in here], rooms, prefer)
            for i, r in zip(here, got):
                if r is not None:
                    out[i] = r
                    used[lessons[i].class_name, lessons[i].subject][r] += 1
    return out


def errors(problem, lessons) -> list[str]:
    """Kiểm tra độc lập (checker): giờ học nào có tiết cần phòng mà không xếp được vào phòng hợp (quá sức chứa)."""
    if not problem.room_fit:
        return []
    out = []
    rooms = placed(problem, lessons)
    missing: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, les in enumerate(lessons):
        if les.course_id in problem.room_fit and rooms[i] is None:
            missing[les.day, les.period].append(i)
    for (d, p), items in sorted(missing.items()):
        rooms = sorted({r for i in items for r in problem.room_fit[lessons[i].course_id]})
        need = [i for i, les in enumerate(lessons) if (les.day, les.period) == (d, p)
                and set(problem.room_fit.get(les.course_id, ())) & set(rooms)]
        classes = ", ".join(f"{lessons[i].class_name} {problem.subject_label(lessons[i].subject)}"
                            for i in sorted(need, key=lambda i: class_sort_key(lessons[i].class_name)))
        places = ", ".join(f"{problem.rooms[r].name} ({problem.rooms[r].capacity} lớp)" for r in rooms)
        out.append(f"{config.DAYS[d]} tiết {p}: không đủ phòng cho {len(need)} tiết {classes} (các phòng hợp: "
                   f"{places})")
    return out
