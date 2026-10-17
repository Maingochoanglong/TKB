"""Trang web của giao diện chạy trên trình duyệt thật (Chromium qua Playwright), với trường mẫu tên giả: các luồng chính
của tkb/giao_dien/static/app.js (trang bắt đầu, dấu từng bước, hoàn tác, tạm tắt luật, ô tìm, xem và đổi ô TKB).

Cần Playwright: pip install -r requirements-test-ui.txt rồi python -m playwright install chromium (CI Linux làm sẵn).
Máy không có thì bỏ qua."""
import glob
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tkb.giao_dien.server import make_server  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            found = p.chromium.launch()
        except sync_api.Error:  # trình duyệt của Playwright chưa cài: thử Chromium có sẵn trên máy
            paths = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
            if not paths:
                pytest.skip("chưa cài trình duyệt cho Playwright (python -m playwright install chromium)")
            found = p.chromium.launch(executable_path=paths[-1])
        yield found
        found.close()


@pytest.fixture
def page(browser, tmp_path):
    httpd, app, url = make_server(port=0, out_dir=tmp_path / "ket_qua")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    yield page
    context.close()
    app.shutdown()
    httpd.shutdown()
    httpd.server_close()
    assert errors == [], errors  # không có lỗi JavaScript nào


def _mark(page, tab):
    return page.locator(f'.tabs [data-tab="{tab}"] .mark')


def _wait_mark(page, tab, text):
    page.wait_for_function(f"""() => (document.querySelector('.tabs [data-tab="{tab}"] .mark') || {{}})
        .textContent?.startsWith("{text}")""", timeout=30000)


def test_sample_steps_undo_switch_and_search(page):
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    page.wait_for_function("document.querySelector('#count-gv').textContent === '45'")
    for tab in ("khung", "mon", "chucvu", "gv", "luat", "xep"):
        _wait_mark(page, tab, "✓")
    # Sửa sai số tiết một giáo viên: bước Giáo viên có dấu ⚠, Ctrl+Z (ngoài ô chữ) thì hết.
    page.click('.tabs [data-tab="gv"]')
    cell = page.locator('#staff-table input[data-k="lessons"]').nth(2)
    cell.fill("")
    cell.press("Tab")
    _wait_mark(page, "gv", "⚠")
    page.evaluate("document.activeElement.blur()")
    page.wait_for_timeout(700)
    page.keyboard.press("Control+z")
    _wait_mark(page, "gv", "✓")
    # Ô tìm: chỉ hiện dòng khớp.
    page.fill("#staff-search", "Bộ Môn 2")
    assert page.locator("#staff-table tbody tr:not([hidden])").count() == 1
    page.fill("#staff-search", "")
    # Tạm tắt một luật bằng ô Dùng: số luật đang dùng giảm, luật mờ đi; Hoàn tác thì dùng lại.
    page.click('.tabs [data-tab="luat"]')
    page.wait_for_selector("#rule-list .rule-item .tag")
    total = int(page.text_content("#count-luat"))
    page.locator('#rule-list [data-act="toggle-rule"]').nth(3).click()
    assert int(page.text_content("#count-luat")) == total - 1
    assert page.locator("#rule-list .rule-item.off").count() == 1
    page.locator("#notice button", has_text="Hoàn tác").click()
    assert int(page.text_content("#count-luat")) == total
    page.fill("#rule-search", "Toán")
    assert 0 < page.locator("#rule-list .rule-item").count() < total


def test_timetable_view_swap_and_undo(page, small_updated):
    """Bước 7 với TKB đã xếp của trường nhỏ: lưới đúng mọi luật; chọn một ô thì có ô viền xanh / mờ; đổi với ô không
    đổi được thì báo lỗi, viền đỏ; Hoàn tác thì hết lỗi; đổi người dạy ghi luật Chỉ giáo viên dạy."""
    page.wait_for_selector("#start:not([hidden])")
    page.set_input_files("#file-open", str(small_updated))
    page.wait_for_selector("#import-dialog[open]")
    page.click("#import-apply")
    page.click('.tabs [data-tab="tkb"]')
    page.wait_for_selector("#tkb-grid table.tkb")
    _wait_mark(page, "tkb", "✓")
    assert page.locator("#tkb-grid td.cell[data-cell]").count() == 2 * 32  # 2 lớp × 32 giờ học
    page.click('#tkb-grid [data-cell="3/1|0|2"]')
    page.wait_for_function("!document.querySelector('#tkb-pick').textContent.includes('Đang tìm')", timeout=30000)
    bad = page.locator("#tkb-grid td.no").first.get_attribute("data-cell")
    page.click(f'#tkb-grid [data-cell="{bad}"]')
    _wait_mark(page, "tkb", "⚠")
    assert page.locator("#tkb-grid td.bad").count() > 0 and page.locator("#tkb-grid .lock").count() == 2
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Control+z")
    _wait_mark(page, "tkb", "✓")
    assert page.locator("#tkb-grid .lock").count() == 0
    # Đổi người dạy Âm nhạc lớp 3/1: ghi luật Chỉ giáo viên dạy, TKB đang có báo sai luật đó; Hoàn tác thì bỏ luật.
    rules = int(page.text_content("#count-luat"))
    cell = page.locator("#tkb-grid td.cell", has_text="Âm nhạc").first.get_attribute("data-cell")
    assert cell.startswith("3/1|")
    page.click(f'#tkb-grid [data-cell="{cell}"]')
    page.select_option('#tkb-pick select[data-tkb="teacher"]', "Chủ Nhiệm 3/1")  # ngay, trước khi thử đổi xong
    _wait_mark(page, "tkb", "⚠")
    assert int(page.text_content("#count-luat")) == rules + 1 and "chỉ do" in page.text_content("#tkb-status")
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Control+z")
    _wait_mark(page, "tkb", "✓")
    assert int(page.text_content("#count-luat")) == rules
    page.select_option("#tkb-view", index=page.locator("#tkb-view option").count() - 1)  # theo giáo viên
    assert page.locator("#tkb-grid td.cell[data-cell]").count() > 0


def test_free_time_frame(page):
    """Bước Khung giờ: thêm ngày (Thứ 7), thêm và đặt tên buổi (Tối), mỗi ngày số tiết riêng; bảng Tiết theo ngày dài
    nhất, hộp thoại Buổi Nghỉ có buổi mới; kiểm tra vẫn ✓ và kịch bản ghi đúng khung giờ."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    _wait_mark(page, "khung", "✓")
    page.click('.tabs [data-tab="khung"]')
    page.click('[data-act="day-add"]')
    assert page.input_value('#day-table input[data-f="day-name"] >> nth=5') == "Thứ 7"
    page.fill('#day-table input[data-f="day-count"][data-i="5"][data-j="1"]', "")  # Thứ 7 chỉ học sáng
    page.locator('#day-table input[data-f="day-count"][data-i="5"][data-j="1"]').press("Tab")
    page.click('[data-act="session-add"]')
    name = page.locator('#day-table input[data-f="session-name"][data-j="2"]')
    name.fill("Tối")
    name.press("Tab")
    count = page.locator('#day-table input[data-f="day-count"][data-i="3"][data-j="2"]')  # Thứ 5 có 2 tiết buổi tối
    count.fill("2")
    count.press("Tab")
    frame = page.evaluate("({sessions: st.scenario.sessions, days: st.scenario.days.map((d) => [d.name, d.periods])})")
    assert frame["sessions"] == ["Sáng", "Chiều", "Tối"]
    assert frame["days"][3] == ["Thứ 5", {"Sáng": 4, "Chiều": 3, "Tối": 2}]
    assert frame["days"][5][0] == "Thứ 7" and frame["days"][5][1]["Sáng"] == 4 and not frame["days"][5][1]["Chiều"]
    rows = page.locator("#period-table tbody tr")
    assert rows.count() == 9 and rows.nth(8).locator("td").nth(1).text_content() == "Tối"
    # Hộp thoại Buổi Nghỉ của một giáo viên không chủ nhiệm: có cột Thứ 7, hàng Tối (chỉ Thứ 5 có buổi tối).
    page.click('.tabs [data-tab="gv"]')
    row = next(i for i, role in enumerate(page.evaluate("st.scenario.staff.map((t) => t.role)")) if role == "Bộ Môn")
    page.click(f'[data-act="edit-staff"][data-i="{row}"]')
    grid = page.locator("#off-box .off-grid")
    assert grid.locator("thead th").last.text_content() == "Thứ 7"
    page.check('#off-box input[data-f="off-fixed"][data-d="3"][data-s="Tối"]')
    assert page.evaluate(f"st.scenario.staff[{row}].off") == "Tối T5"
    page.keyboard.press("Escape")
    _wait_mark(page, "khung", "✓")
    _wait_mark(page, "gv", "✓")


def test_class_step(page):
    """Bước Lớp: lấy lớp từ các Chủ Nhiệm, thêm khối tên chữ và một lớp chưa có Chủ Nhiệm, đổi tên khối thì số tiết
    của môn và khối của lớp đổi theo; Chủ Nhiệm chọn Lớp trong danh sách; lỗi của sheet LỚP về đúng bước, đúng dòng."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    _wait_mark(page, "lop", "✓")
    page.click('.tabs [data-tab="lop"]')
    assert "Chưa ghi lớp nào" in page.text_content("#class-summary")
    page.click('[data-act="classes-from-homeroom"]')
    assert page.text_content("#count-lop") == "29"
    page.fill("#new-grade", "Lá")
    page.click('[data-act="add-grade"]')
    page.click('[data-act="add-class"]')
    name = page.locator('#class-table [data-f="class"][data-i="29"][data-k="name"]')
    name.fill("Lá 1")
    name.press("Tab")
    page.select_option('#class-table [data-f="class"][data-i="29"][data-k="grade"]', "Lá")
    assert "1 lớp chưa có Chủ Nhiệm" in page.text_content("#class-summary")
    grade = page.locator('#grade-list [data-f="grade"]').last
    grade.fill("Mầm")
    grade.press("Tab")
    sc = page.evaluate("({grades: st.scenario.grades, cls: st.scenario.classes[29], lessons: st.scenario.subjects[0].lessons})")
    assert sc["grades"] == [1, 2, 3, 4, 5, "Mầm"] and sc["cls"] == {"name": "Lá 1", "grade": "Mầm", "campus2": False}
    assert "Mầm" in sc["lessons"] and "Lá" not in sc["lessons"]
    _wait_mark(page, "lop", "✓")
    # Chủ Nhiệm ghi lớp không có trong danh sách: lỗi ở bước Giáo viên; xóa lớp 1/1 khỏi danh sách cũng vậy.
    page.click('#class-table [data-act="del-class"][data-i="0"]')
    _wait_mark(page, "gv", "⚠")
    assert "1/1" in page.text_content("#tab-gv .step-errors")
    page.click('.tabs [data-tab="gv"]')
    options = page.evaluate("[...document.querySelectorAll('#class-list option')].map((o) => o.value)")
    assert "Lá 1" in options and "1/1" not in options and len(options) == 29
    page.click("#btn-undo")
    _wait_mark(page, "gv", "✓")
