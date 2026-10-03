"""Dự toán và phân công giáo viên, không dùng CP-SAT: Python thuần, số nguyên, duyệt theo thứ tự cố định nên
mọi máy (Windows, Linux) ra cùng một phân công.

1. Dự toán: luồng chi phí nhỏ nhất từ các lớp–môn ("phần còn lại" ngoài phần GVCN) sang các giáo viên được
   phép dạy. Giá theo thứ tự ưu tiên của config.Weights: tiết thiếu ≫ bộ môn bù ≫ GVCN bù; tiết bù thứ hai
   của một người đắt hơn tiết thứ nhất (ai cũng +1 rồi mới +2); GVCN bù môn ưu tiên trước. Cho biết mỗi GVCN
   bù bao nhiêu tiết và còn thiếu bao nhiêu tiết.
2. GVCN nhận tiết bù ở lớp mình: môn ưu tiên trước, rồi các môn trọn vẹn theo HOMEROOM_FILL_ORDER; phần của
   GVCN trong nhóm môn ghép cặp (allocation.paired_groups) luôn chẵn.
3. Phần còn lại: luồng lần 2 cho bộ môn, GV chuyên biệt, quản lý, rồi tìm kiếm cục bộ (bớt chia môn, gom lớp
   theo khối, cân bằng tải, chia chẵn nhóm ghép cặp).
4. Tiết bù (và tiết thiếu ở chế độ tuyển) chia cho người tuyển mới (`tach_tiet_bu`): chế độ tuyển dùng đúng
   TKB của chế độ bù, người mới dạy các ô bù.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import combinations

from . import config
from .allocation import (Course, Problem, keep_cost, overtime_cost, paired_groups, roles_for_subject,
                         sessions_per_week, subject_group, supplement_capacity)
from .staff import Teacher, class_sort_key, grade_of

Key = tuple[int, str]  # (course, chức vụ GV)
MANAGER_BONUS = 10_000_000  # quản lý phải dạy đúng số tiết: cạnh của quản lý có giá âm lớn


# --------------------------------------------------------------------------
# Luồng chi phí nhỏ nhất (đường đi ngắn nhất liên tiếp), số nguyên
# --------------------------------------------------------------------------
class MinCostFlow:
    def __init__(self, n: int):
        self.g: list[list[list[int]]] = [[] for _ in range(n)]  # [đến, sức chứa, giá, chỉ số cạnh ngược]

    def add(self, u: int, v: int, cap: int, cost: int) -> tuple[int, int]:
        self.g[u].append([v, cap, cost, len(self.g[v])])
        self.g[v].append([u, 0, -cost, len(self.g[u]) - 1])
        return u, len(self.g[u]) - 1

    def run(self, s: int, t: int) -> None:
        n = len(self.g)
        while True:
            dist: list[int | None] = [None] * n
            prev: list[tuple[int, int] | None] = [None] * n
            queued = [False] * n
            dist[s] = 0
            queue = deque([s])
            while queue:
                u = queue.popleft()
                queued[u] = False
                for i, (v, cap, cost, _) in enumerate(self.g[u]):
                    if cap > 0 and (dist[v] is None or dist[u] + cost < dist[v]):
                        dist[v] = dist[u] + cost
                        prev[v] = (u, i)
                        if not queued[v]:
                            queue.append(v)
                            queued[v] = True
            if dist[t] is None:
                return
            push, v = None, t
            while v != s:
                u, i = prev[v]
                push = self.g[u][i][1] if push is None else min(push, self.g[u][i][1])
                v = u
            v = t
            while v != s:
                u, i = prev[v]
                edge = self.g[u][i]
                edge[1] -= push
                self.g[v][edge[3]][1] += push
                v = u

    def used(self, ref: tuple[int, int]) -> int:
        u, i = ref
        v, _, _, j = self.g[u][i]
        return self.g[v][j][1]


def subject_rank(subject: str) -> int:
    """Hạng môn khi GVCN bù: môn ưu tiên 0, rồi theo HOMEROOM_FILL_ORDER 1, 2..., môn khác sau cùng."""
    if subject in config.HOMEROOM_PRIORITY:
        return 0
    if subject in config.HOMEROOM_FILL_ORDER:
        return config.HOMEROOM_FILL_ORDER.index(subject) + 1
    return len(config.HOMEROOM_FILL_ORDER) + 1


def _real_teachers(problem: Problem) -> list[str]:
    return [g for g, t in problem.teachers.items() if not t.supplementary]


def teacher_slots(problem: Problem) -> dict[str, int]:
    """GV -> số ô giờ có thể dạy (hợp các ô được phép của những course người đó được dạy, trừ buổi nghỉ). Vd GV
    không chủ nhiệm không dạy tiết 1 (của GVCN) và các ô HĐTN cố định của mọi lớp."""
    from .luat_rieng import day_cap
    from .solver import allowed_slots, session_of  # solver nhập module này: nhập muộn để tránh vòng lặp
    sess = session_of()
    slots: dict[str, set] = {}
    for c in problem.courses:
        dom = allowed_slots(c, problem)
        for g in c.teachers:
            slots.setdefault(g, set()).update(dom)
    out = {}
    for g, s in slots.items():
        t = problem.teachers[g]
        s = {slot for slot in s if (slot[0], sess[slot].name) not in t.off_sessions}
        for name, n in t.off_any:  # nghỉ n buổi bất kỳ: bớt n buổi có ít ô nhất
            per = Counter((slot[0], sess[slot].name) for slot in s if name is None or sess[slot].name == name)
            s -= {slot for key in sorted(per, key=lambda k: (per[k], k))[:n]
                  for slot in s if (slot[0], sess[slot].name) == key}
        cap = day_cap(t) if config.CUSTOM_RULES else None  # luật riêng: GV tối đa tiết mỗi ngày
        out[g] = len(s) if cap is None else sum(min(cap, k) for k in Counter(d for d, _ in s).values())
    return out


def _flow(problem: Problem, w: config.Weights, demand: dict[int, int], base_load: Counter,
          homeroom_arcs: bool) -> tuple[dict[Key, int], dict[int, int]]:
    """Giao `demand` (course -> số tiết) cho GV thật; trả về (phân công, tiết thiếu theo course)."""
    teachers = problem.teachers
    real = _real_teachers(problem)
    room = teacher_slots(problem)
    spec = problem.specialist_subjects()
    courses = [problem.courses[cid] for cid in sorted(demand) if demand[cid] > 0]
    source, sink, missing = 0, 1, 2
    node_c = {c.id: 3 + i for i, c in enumerate(courses)}
    node_t = {g: 3 + len(courses) + i for i, g in enumerate(real)}
    mcf = MinCostFlow(3 + len(courses) + len(real))
    arcs: dict[Key, tuple[int, int]] = {}
    miss_arcs: dict[int, tuple[int, int]] = {}
    for c in courses:
        mcf.add(source, node_c[c.id], demand[c.id], 0)
        for g in c.teachers:
            t = teachers[g]
            if t.supplementary or (t.class_name and not homeroom_arcs):
                continue
            cost = w.overtime_subject_order * subject_rank(c.subject) if t.class_name else 0
            cost += keep_cost(t, c.class_name, w)
            if c.subject in spec and t.role not in problem.specialists:
                cost += w.general_on_specialist
            arcs[c.id, g] = mcf.add(node_c[c.id], node_t[g], demand[c.id], cost)
        miss_arcs[c.id] = mcf.add(node_c[c.id], missing, demand[c.id], w.supplement_lesson)
    mcf.add(missing, sink, sum(demand.values()), 0)
    for g in real:
        t = teachers[g]
        if g in problem.manager_load:
            left = problem.manager_load[g] - base_load[g]
            if left > 0:
                mcf.add(node_t[g], sink, left, -MANAGER_BONUS)
            continue
        limit = room.get(g, 0) - base_load[g]  # không dạy quá số ô giờ có thể dạy
        regular = min(t.max_lessons - base_load[g], limit)
        if regular > 0:
            mcf.add(node_t[g], sink, regular, 0)
        first = overtime_cost(t, w)
        for k in range(min(problem.overtime.get(g, 0), limit - max(regular, 0))):  # tiết bù thứ k+1 đắt dần
            mcf.add(node_t[g], sink, 1, first + k * w.overtime_second)
    mcf.run(source, sink)
    lessons = {key: n for key, ref in arcs.items() if (n := mcf.used(ref))}
    miss = {cid: n for cid, ref in miss_arcs.items() if (n := mcf.used(ref))}
    return lessons, miss


# --------------------------------------------------------------------------
# GVCN nhận tiết bù ở lớp mình
# --------------------------------------------------------------------------
def _homeroom_extra(problem: Problem, g: str, x: int, rem: dict[int, int],
                    order: dict[str, int], spec_cap: dict[Key, int]) -> tuple[dict[int, int], int]:
    """Chọn x tiết bù cho GVCN g: (course -> số tiết, số tiết môn ưu tiên phải nhường vì chia chẵn).

    Môn của GV chuyên biệt (config.HOMEROOM_OVERTIME_SPECIALIST) GVCN chỉ nhận đúng phần dự toán giao cho mình
    (`spec_cap`): phần còn lại là của GV chuyên biệt và bộ môn, dự toán đã chia cho khớp giữa các lớp."""
    t = problem.teachers[g]
    grade = grade_of(t.class_name)
    pairs = paired_groups(problem.curriculum[grade], grade)
    spec = problem.specialist_subjects()
    rem = {c.id: min(rem.get(c.id, 0), spec_cap.get((c.id, g), 0)) if c.subject in spec else rem.get(c.id, 0)
           for c in problem.courses if c.class_name == t.class_name}
    own = [c for c in problem.courses if c.class_name == t.class_name and not c.homeroom
           and g in c.teachers and rem.get(c.id, 0) > 0]
    held = Counter()  # nhóm môn -> số tiết GVCN đã dạy trong phần định mức
    for c in problem.class_courses(t.class_name):
        if c.homeroom:
            held[subject_group(c.subject)] += c.lessons
    key = lambda c: (subject_rank(c.subject), order.get(c.subject, 99))  # noqa: E731
    take: dict[int, int] = {}
    skipped = 0
    # 1. Môn ưu tiên trước, theo nhóm môn; nhóm ghép cặp giữ phần của GVCN chẵn.
    groups = sorted({subject_group(c.subject) for c in own if subject_rank(c.subject) == 0},
                    key=lambda grp: min(key(c) for c in own if subject_group(c.subject) == grp))
    for grp in groups:
        cs = sorted((c for c in own if subject_group(c.subject) == grp), key=key)
        want = min(x, sum(rem[c.id] for c in cs))
        if grp in pairs and (held[grp] + want) % 2:
            want -= 1
            skipped += 1
        for c in cs:
            n = min(want, rem[c.id])
            if n:
                take[c.id] = n
                want -= n
                x -= n
    # 2. Còn lại: các môn trọn vẹn, tổng vừa khít, ít hạng nhất (không chia môn nếu tránh được).
    rest = sorted((c for c in own if c.id not in take and subject_rank(c.subject) > 0), key=key)
    if x > 0:
        best = None
        for k in range(1, min(len(rest), 6) + 1):
            for combo in combinations(rest, k):
                if sum(rem[c.id] for c in combo) != x:
                    continue
                grp_add = Counter()
                for c in combo:
                    grp_add[subject_group(c.subject)] += rem[c.id]
                if any((held[grp] + n) % 2 for grp, n in grp_add.items() if grp in pairs):
                    continue
                cost = (sum(subject_rank(c.subject) * rem[c.id] for c in combo), k, [c.id for c in combo])
                if best is None or cost < best[0]:
                    best = (cost, combo)
        if best:
            for c in best[1]:
                take[c.id] = rem[c.id]
            x = 0
    for c in rest:  # không có tổ hợp vừa khít: lấy theo hạng, môn ghép cặp lấy chẵn
        if x <= 0:
            break
        n = min(x, rem[c.id])
        if subject_group(c.subject) in pairs and n % 2:
            n -= 1
        if n > 0:
            take[c.id] = take.get(c.id, 0) + n
            x -= n
    for c in rest:  # hết cách: chấp nhận lẻ
        if x <= 0:
            break
        n = min(x, rem[c.id] - take.get(c.id, 0))
        if n > 0:
            take[c.id] = take.get(c.id, 0) + n
            x -= n
    return take, skipped


def _balance_parity(problem: Problem, totals: dict[str, int], rem: dict[int, int], order: dict[str, int],
                    spec_cap: dict[Key, int]) -> None:
    """GVCN phải nhường môn ưu tiên vì chia chẵn (vd bù +1 vào nhóm TV ghép cặp) thì đổi mức bù với một GVCN
    khác không bị vướng: tổng tiết bù giữ nguyên."""
    for _ in range(len(totals)):
        stuck = [g for g in sorted(totals, key=lambda g: class_sort_key(problem.teachers[g].class_name))
                 if _homeroom_extra(problem, g, totals[g], rem, order, spec_cap)[1]
                 and totals[g] < problem.overtime.get(g, 0)]
        if not stuck:
            return
        g = stuck[0]
        more, more_skipped = _homeroom_extra(problem, g, totals[g] + 1, rem, order, spec_cap)
        if more_skipped or sum(more.values()) != totals[g] + 1:
            return
        for h in sorted(totals, key=lambda h: class_sort_key(problem.teachers[h].class_name)):
            if h == g or totals[h] <= 0:
                continue
            if not _homeroom_extra(problem, h, totals[h] - 1, rem, order, spec_cap)[1]:
                totals[h] -= 1
                totals[g] += 1
                break
        else:
            return


# --------------------------------------------------------------------------
# Tìm kiếm cục bộ cho GV không chủ nhiệm, không quản lý
# --------------------------------------------------------------------------
class _Local:
    def __init__(self, problem: Problem, lessons: dict[Key, int], w: config.Weights):
        self.p, self.w = problem, w
        teachers = problem.teachers
        self.movable = [g for g in _real_teachers(problem)
                        if not teachers[g].class_name and g not in problem.manager_load]
        self.mov = set(self.movable)
        self.role_members: dict[str, list[str]] = {}
        for g in self.movable:
            self.role_members.setdefault(teachers[g].role, []).append(g)
        self.spec = problem.specialist_subjects()
        self.pairs = {g: paired_groups(req, g) for g, req in problem.curriculum.items()}
        self.share: dict[int, dict[str, int]] = {}
        self.fixed: dict[Key, int] = {}
        self.load = Counter()
        self.tcls: dict[str, Counter] = {g: Counter() for g in self.movable}
        self.tgrade: dict[str, Counter] = {g: Counter() for g in self.movable}
        self.tgroup: dict[str, Counter] = {g: Counter() for g in self.movable}  # (lớp, nhóm môn) -> số tiết
        for (cid, g), n in lessons.items():
            self.load[g] += n
            if g in self.mov:
                self.share.setdefault(cid, {})[g] = n
                self._count(cid, g, n)
            else:
                self.fixed[cid, g] = n
        self.cap = {g: max(teachers[g].max_lessons, self.load[g]) for g in self.movable}

    def _count(self, cid: int, g: str, n: int) -> None:
        c = self.p.courses[cid]
        for cnt, key in ((self.tcls[g], c.class_name), (self.tgrade[g], c.grade),
                         (self.tgroup[g], (c.class_name, subject_group(c.subject)))):
            cnt[key] += n
            if cnt[key] == 0:
                del cnt[key]

    def _shift(self, cid: int, g: str, n: int) -> None:
        sh = self.share.setdefault(cid, {})
        sh[g] = sh.get(g, 0) + n
        if sh[g] == 0:
            del sh[g]
        self.load[g] += n
        self._count(cid, g, n)

    def _part(self, cids: list[int], gs: list[str]) -> int:
        w, teachers = self.w, self.p.teachers
        cost = 0
        for cid in cids:
            sh = self.share.get(cid, {})
            cost += w.course_split * max(0, len(sh) - 1)
            if self.p.courses[cid].subject in self.spec:
                cost += w.general_on_specialist * sum(n for g, n in sh.items()
                                                      if teachers[g].role not in self.p.specialists)
        for role in sorted({teachers[g].role for g in gs}):
            members = self.role_members[role]
            if len(members) >= 2:
                cost += w.load_balance * max(teachers[m].max_lessons - self.load[m] for m in members)
        for g in gs:
            cost += sum(keep_cost(teachers[g], cls, w) * n for cls, n in self.tcls[g].items())
            cost += w.group_grade * len(self.tgrade[g]) + w.group_class * len(self.tcls[g])
            cost += w.odd_pair_share * sum(1 for (cls, grp), n in self.tgroup[g].items()
                                           if n % 2 and grp in self.pairs[grade_of(cls)])
        return cost

    def _try(self, ops: list[tuple[int, str, int]], cids: list[int], gs: list[str]) -> bool:
        before = self._part(cids, gs)
        for cid, g, n in ops:
            self._shift(cid, g, n)
        if all(self.load[g] <= self.cap[g] for g in gs) and self._part(cids, gs) < before:
            return True
        for cid, g, n in reversed(ops):
            self._shift(cid, g, -n)
        return False

    def run(self, max_rounds: int = 30) -> None:
        courses = self.p.courses
        for _ in range(max_rounds):
            improved = False
            # Chuyển trọn phần của một người sang người khác.
            for cid in sorted(self.share):
                for g1 in sorted(self.share[cid]):
                    if g1 not in self.share[cid]:
                        continue
                    x = self.share[cid][g1]
                    for g2 in courses[cid].teachers:
                        if g2 != g1 and g2 in self.mov and self._try([(cid, g1, -x), (cid, g2, x)], [cid], [g1, g2]):
                            improved = True
                            break
            # Đổi chéo trọn phần của hai người ở hai course.
            entries = sorted((cid, g) for cid, sh in self.share.items() for g in sh)
            for i, (c1, g1) in enumerate(entries):
                for c2, g2 in entries[i + 1:]:
                    if c1 == c2 or g1 == g2 or g1 not in self.share.get(c1, {}) or g2 not in self.share.get(c2, {}):
                        continue
                    if g2 not in courses[c1].teachers or g1 not in courses[c2].teachers:
                        continue
                    x1, x2 = self.share[c1][g1], self.share[c2][g2]
                    if self._try([(c1, g1, -x1), (c1, g2, x1), (c2, g2, -x2), (c2, g1, x2)], [c1, c2], [g1, g2]):
                        improved = True
            # Gộp môn bị chia: người giữ nhận nốt phần của người kia ở course a, trả lại đúng ngần ấy tiết ở course b.
            for a in sorted(self.share):
                done = False
                for keep in sorted(self.share[a]):
                    for give in sorted(self.share[a]):
                        if done or keep == give or keep not in self.share[a] or give not in self.share[a]:
                            continue
                        x = self.share[a][give]
                        for b in sorted(self.share):
                            if b != a and self.share[b].get(keep, 0) >= x and give in courses[b].teachers and \
                                    self._try([(a, give, -x), (a, keep, x), (b, keep, -x), (b, give, x)],
                                              [a, b], [keep, give]):
                                improved = done = True
                                break
            if not improved:
                return

    def odd(self) -> list[tuple[str, str, str]]:
        """(lớp, nhóm môn, GV) mà GV dạy số tiết lẻ trong một nhóm môn ghép cặp (khó xếp thành cặp)."""
        return [(cls, grp, g) for g in self.movable for (cls, grp), n in sorted(self.tgroup[g].items())
                if n % 2 and grp in self.pairs[grade_of(cls)]]

    def repair(self, max_rounds: int = 30) -> None:
        """Sửa phần lẻ trong nhóm môn ghép cặp mà `run` để lại (vd luật riêng "Học 2 tiết liền" với định mức lẻ):
        hai GV cùng lẻ ở một lớp-nhóm môn chuyển cho nhau 1 tiết ở đó, người nhận trả lại 1 tiết ở một course khác (tải
        mỗi người không đổi). Không được thì nhờ GV thứ ba có tiết ở nhóm môn không ghép cặp: người đó nhường 1 tiết lẻ
        cho mỗi người và nhận lại một cặp 2 tiết (vd định mức lẻ 23 mà các lớp đều học 2 tiết liền). Chỉ chạy khi còn
        phần lẻ, nên phân công khác không đổi."""
        courses = self.p.courses
        paired = lambda cid: subject_group(courses[cid].subject) in self.pairs[courses[cid].grade]  # noqa: E731

        def via_third(a: int, g1: str, g2: str) -> bool:
            for g3 in self.movable:
                if g3 in (g1, g2):
                    continue
                spare = [cid for cid, sh in sorted(self.share.items()) if sh.get(g3) and not paired(cid)]
                n1 = next((c for c in spare if g1 in courses[c].teachers), None)
                n2 = next((c for c in spare if g2 in courses[c].teachers
                           and self.share[c][g3] >= (2 if c == n1 else 1)), None)
                if n1 is None or n2 is None:
                    continue
                for pc in sorted(cid for cid, sh in self.share.items() if sh.get(g2, 0) >= 2 and paired(cid)
                                 and g3 in courses[cid].teachers and cid != a):
                    ops = [(a, g1, -1), (a, g2, 1), (n1, g3, -1), (n1, g1, 1), (pc, g2, -2), (pc, g3, 2),
                           (n2, g3, -1), (n2, g2, 1)]
                    if self._try(ops, sorted({a, n1, n2, pc}), [g1, g2, g3]):
                        return True
            return False

        for _ in range(max_rounds):
            improved = False
            odd = self.odd()
            for i, (cls, grp, g1) in enumerate(odd):
                for cls2, grp2, g2 in odd[i + 1:]:
                    if (cls2, grp2) != (cls, grp) or self.tgroup[g1].get((cls, grp), 0) % 2 == 0 or \
                            self.tgroup[g2].get((cls, grp), 0) % 2 == 0:
                        continue
                    moved = False
                    for a in sorted(cid for cid, sh in self.share.items() if sh.get(g1)
                                    and courses[cid].class_name == cls and subject_group(courses[cid].subject) == grp
                                    and g2 in courses[cid].teachers):
                        for b in sorted(cid for cid, sh in self.share.items() if sh.get(g2) and g1 in courses[cid].teachers
                                        and cid != a):
                            if self._try([(a, g1, -1), (a, g2, 1), (b, g2, -1), (b, g1, 1)], [a, b], [g1, g2]):
                                improved = moved = True
                                break
                        if moved:
                            break
                        if via_third(a, g1, g2) or via_third(a, g2, g1) if self.share[a].get(g2) else via_third(a, g1, g2):
                            improved = moved = True
                            break
            if not improved:
                return

    def lessons(self) -> dict[Key, int]:
        out = dict(self.fixed)
        for cid, sh in self.share.items():
            for g, n in sh.items():
                out[cid, g] = n
        return out


# --------------------------------------------------------------------------
# Phân công
# --------------------------------------------------------------------------
@dataclass
class PhanCong:
    lessons: dict[Key, int]  # (course, GV thật) -> số tiết, gồm cả phần GVCN và tiết bù
    extra: dict[Key, int]  # phần vượt định mức (tiết bù) của từng người theo course
    overtime: dict[str, int]  # GV -> số tiết bù
    overtime_cap: dict[str, int]  # GVCN/bộ môn -> số tiết bù tối đa có thể dùng
    missing: dict[int, int]  # course -> số tiết không ai dạy được, kể cả khi đã bù tối đa
    odd_pairs: list[tuple[str, str, str]] = field(default_factory=list)  # (lớp, nhóm môn, GV) chia lẻ

    def missing_total(self) -> int:
        return sum(self.missing.values())


def phan_cong(problem: Problem, w: config.Weights) -> PhanCong:
    """Dự toán + phân công (xem đầu module). `problem` là bài toán chế độ bù (GVCN được nhận tiết ở lớp mình)."""
    teachers = problem.teachers
    order = {s: i for i, s in enumerate(problem.subject_order)}
    lessons: dict[Key, int] = {}
    base = Counter()
    demand: dict[int, int] = {}
    for c in problem.courses:
        if c.homeroom:
            lessons[c.id, c.teachers[0]] = c.lessons
            base[c.teachers[0]] += c.lessons
        else:
            demand[c.id] = c.lessons
    # 1. Dự toán: mỗi GVCN bù bao nhiêu tiết.
    first, _ = _flow(problem, w, demand, base, homeroom_arcs=True)
    totals = Counter()
    for (cid, g), n in first.items():
        if teachers[g].class_name:
            totals[g] += n
    totals = {g: totals[g] for g in sorted(totals, key=lambda g: class_sort_key(teachers[g].class_name))}
    spec = problem.specialist_subjects()
    spec_cap = {(cid, g): n for (cid, g), n in first.items()
                if teachers[g].class_name and problem.courses[cid].subject in spec}
    _balance_parity(problem, totals, demand, order, spec_cap)
    # 2. GVCN nhận tiết bù ở lớp mình.
    rem = dict(demand)
    for g, x in totals.items():
        take, _ = _homeroom_extra(problem, g, x, rem, order, spec_cap)
        for cid, n in take.items():
            lessons[cid, g] = n
            rem[cid] -= n
    # 3. Phần còn lại cho bộ môn, GV chuyên biệt, quản lý; rồi tìm kiếm cục bộ.
    second, missing = _flow(problem, w, rem, base, homeroom_arcs=False)
    local = _Local(problem, second, w)
    local.run()
    if local.odd():
        local.repair()
    lessons.update(local.lessons())

    load = Counter()
    for (cid, g), n in lessons.items():
        load[g] += n
    overtime = {g: load[g] - teachers[g].max_lessons for g in problem.overtime if load[g] > teachers[g].max_lessons}
    extra: dict[Key, int] = {}
    for (cid, g), n in lessons.items():  # GVCN: mọi tiết ngoài phần định mức là tiết bù
        if teachers[g].class_name and not problem.courses[cid].homeroom:
            extra[cid, g] = n
    for g, k in overtime.items():  # bộ môn bù: lấy từ các lớp cuối theo thứ tự lớp
        if teachers[g].class_name:
            continue
        own = sorted((cid for (cid, h) in lessons if h == g),
                     key=lambda cid: class_sort_key(problem.courses[cid].class_name), reverse=True)
        for cid in own:
            n = min(k, lessons[cid, g])
            if n:
                extra[cid, g] = n
                k -= n
    cap: dict[str, int] = {}
    for g, allow in problem.overtime.items():
        if teachers[g].class_name:
            cap[g] = min(allow, sum(demand[cid] for cid in demand if g in problem.courses[cid].teachers))
        else:
            cap[g] = allow
    odd = []
    for g in sorted(load):
        per = Counter()
        for (cid, h), n in lessons.items():
            if h == g:
                c = problem.courses[cid]
                per[c.class_name, subject_group(c.subject)] += n
        for (cls, grp), n in sorted(per.items()):
            if n % 2 and grp in paired_groups(problem.curriculum[grade_of(cls)], grade_of(cls)):
                odd.append((cls, grp, g))
    return PhanCong(lessons=lessons, extra=extra, overtime=overtime, overtime_cap=cap, missing=missing,
                    odd_pairs=odd)


# --------------------------------------------------------------------------
# Tiết bù (và tiết thiếu) -> người tuyển mới
# --------------------------------------------------------------------------
def _hire_role(problem: Problem, course: Course) -> str:
    """Chức vụ tuyển cho tiết thiếu: bộ môn nếu được dạy môn này, không thì GV chuyên biệt của môn."""
    roles = roles_for_subject(course.subject, problem.specialists)
    return config.ROLE_GENERAL if config.ROLE_GENERAL in roles else sorted(roles)[0]


def tach_tiet_bu(problem: Problem, plan: PhanCong, staff: list[Teacher],
                 include_missing: bool) -> dict[str, list[list[tuple[int, str, int]]]]:
    """Chức vụ -> người tuyển mới (số nhỏ nhận nhiều tiết hơn), mỗi người là các (course, người bù, số tiết);
    người bù "" là tiết thiếu. Mỗi người tối đa định mức GV cùng chức vụ và một cặp tiết mỗi buổi. Tiết bù
    của một người ở một lớp giao trọn cho một người mới."""
    units: dict[str, dict[tuple[str, str], list[tuple[int, str, int]]]] = {}
    for (cid, owner), n in sorted(plan.extra.items()):
        c = problem.courses[cid]
        units.setdefault(config.ROLE_GENERAL, {}).setdefault((owner, c.class_name), []).append((cid, owner, n))
    if include_missing:
        for cid, n in sorted(plan.missing.items()):
            c = problem.courses[cid]
            role = _hire_role(problem, c)
            units.setdefault(role, {}).setdefault(("", c.class_name), []).append((cid, "", n))
    max_pairs = sessions_per_week()
    result: dict[str, list[list[tuple[int, str, int]]]] = {}
    for role in sorted(units):
        cap = supplement_capacity(role, staff)
        items = []
        for (owner, cls), parts in units[role].items():
            per = Counter()
            for cid, _, n in parts:
                per[subject_group(problem.courses[cid].subject)] += n
            pairs = sum(n // 2 for grp, n in per.items()
                        if grp in paired_groups(problem.curriculum[grade_of(cls)], grade_of(cls)))
            items.append((sum(n for _, _, n in parts), pairs, cls, owner, parts))
        items.sort(key=lambda it: (-it[1], class_sort_key(it[2]), it[3]))
        total = sum(it[0] for it in items)
        count = max(1, -(-total // cap), -(-sum(it[1] for it in items) // max_pairs))
        while True:
            load, pairs, groups = [0] * count, [0] * count, [[] for _ in range(count)]
            ok = True
            for n, pc, _, _, parts in items:
                fits = [i for i in range(count) if load[i] + n <= cap and pairs[i] + pc <= max_pairs]
                if not fits:
                    ok = False
                    break
                i = min(fits, key=lambda i: (pairs[i] if pc else 0, load[i], i))
                load[i] += n
                pairs[i] += pc
                groups[i].extend(parts)
            if ok:
                break
            count += 1
        order = sorted(range(count), key=lambda i: (-load[i], i))
        result[role] = [groups[i] for i in order if groups[i]]
    return result
