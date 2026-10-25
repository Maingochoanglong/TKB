"""Trang web của giao diện chạy trên trình duyệt thật (Chromium qua Playwright), với trường mẫu tên giả: các luồng chính
của tkb/giao_dien/static/app.js (trang bắt đầu, dấu từng bước, hoàn tác, tạm tắt luật, ô tìm, xem và đổi ô TKB).

Cần Playwright: pip install -r requirements-test-ui.txt rồi python -m playwright install chromium (CI Linux làm sẵn).
Máy không có thì bỏ qua."""
import glob
import json
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tkb.giao_dien import server  # noqa: E402
from tkb.giao_dien.server import make_server  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            found = p.chromium.launch()
        except sync_api.Error:  # trình duyệt của Playwright chưa cài: thử Chromium có sẵn trên máy
            paths = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
            if not paths:
                pytest.skip("chưa cài trình duyệt cho Playwright (python -m playwright install chromium)")
            found = p.chromium.launch(executable_path=paths[-1])
        yield found
        found.close()


@pytest.fixture
def page(browser, tmp_path):
    httpd, app, url = make_server(port=0, out_dir=tmp_path / "ket_qua")
    # Các test soạn dữ liệu dùng giao diện đầy đủ (lựa chọn của trang lưu ở máy chủ, file trang.json của app.data);
    # test của giao diện gọn đặt lại "1".
    app.data.mkdir(parents=True)
    (app.data / server.STORE_NAME).write_text(json.dumps({"tkb-gon": "0"}), encoding="utf-8")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.app = app  # _solved giữ khóa của máy chủ
    page.httpd = httpd  # test tắt chương trình giữa chừng
    page.goto(url)
    yield page
    context.close()
    app.shutdown()
    httpd.shutdown()
    httpd.server_close()
    assert errors == [], errors  # không có lỗi JavaScript nào


def _mark(page, tab):
    return page.locator(f'.tabs [data-tab="{tab}"] .mark')


MARKS = {"✓": "good", "⚠": "bad", "?": "wait"}  # dấu của bước (biểu tượng SVG) theo lớp: đạt, có lỗi, chưa kiểm


def _wait_mark(page, tab, text):
    page.wait_for_function(f"""() => (document.querySelector('.tabs [data-tab="{tab}"] .mark') || {{}})
        .classList?.contains("{MARKS[text]}")""", timeout=30000)


def _solved(page, make):
    """File vào cập nhật sau một lần xếp TKB ngay trong tiến trình test: `make()` ghi file vào (thư mục tmp_path), rồi
    xếp ra thư mục ra/ cạnh đó. Giữ khóa của máy chủ trang (App.lock) trong lúc đó: rules.applied đổi config chung
    của tiến trình, trang đang kiểm tra nhanh cùng lúc thì hai bên khôi phục config sai cho nhau (lệch cả các test
    sau)."""
    from tkb.__main__ import main
    with page.app.lock:
        source = make()
        out = source.parent / "ra"
        assert main([str(source), "-o", str(out / "TKB.xlsx"), "--time-limit", "10", "--workers", "4"]) == 0
    return out / f"{source.stem}_cap_nhat.xlsx"


def _wait_text(page, selector, text):
    """Chờ phần tử có chữ `text` (vd bảng vẽ lại sau sự kiện close của hộp thoại, sự kiện này chạy sau Escape)."""
    page.wait_for_function("([sel, text]) => (document.querySelector(sel)?.textContent || '').includes(text)",
                           arg=[selector, text], timeout=10000)


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


def test_simple_mode_has_three_steps(page, tmp_path):
    """Giao diện gọn (mặc định): trang bắt đầu chỉ có Mở file Excel; mở file xong là tới bước Kiểm tra & xếp, chỉ có ba
    bước; lỗi của dữ liệu về bước Mở file Excel. Tệp › Hiện đủ các bước soạn thì có đủ tám bước, tải lại vẫn giữ."""
    from tkb.truong_mau import write_sample_input
    page.evaluate("async () => { store.setItem('tkb-gon', '1'); await store.flush(); }")
    page.reload()
    page.wait_for_selector("#start:not([hidden])")
    assert page.locator('[data-start="open"]').first.is_visible()
    assert page.locator('[data-start="sample"]').is_hidden()
    page.set_input_files("#file-open", str(write_sample_input(tmp_path / "Truong_mau.xlsx")))
    page.wait_for_selector("#import-dialog[open]")
    page.click("#import-apply")
    page.wait_for_function("document.querySelector('.tabs button.active')?.dataset.tab === 'xep'")
    shown = "() => [...document.querySelectorAll('.tabs button')].filter((b) => b.offsetParent).map((b) => b.dataset.tab)"
    assert page.evaluate(shown) == ["mo", "xep", "tkb"]
    # Bước Xếp TKB: tự kiểm tra dữ liệu; chỉ còn nút Xếp TKB, cài đặt gấp lại sau nút Cài đặt…
    _wait_text(page, "#check-result", "Dữ liệu hợp lệ")
    assert page.locator("#btn-check").is_hidden() and page.locator("#run-settings").is_hidden()
    page.click("#btn-settings")
    assert page.locator("#run-settings").is_visible()
    page.click("#btn-settings")
    _wait_mark(page, "mo", "✓")
    # Một giáo viên sai số tiết: bước Mở file Excel báo lỗi, ghi chỗ trong file thay cho liên kết tới bước soạn.
    page.evaluate("() => { st.scenario.staff[2].lessons = null; changed(); }")  # như sửa trong Excel rồi mở lại
    _wait_mark(page, "mo", "⚠")
    page.click('.tabs [data-tab="mo"]')
    assert "NHÂN SỰ" in page.text_content("#tab-mo .step-errors")
    assert page.locator("#tab-mo .step-errors a").count() == 0
    page.click("#file-menu summary")
    page.click("#btn-gon")
    assert len(page.evaluate(shown)) == 8
    assert page.evaluate("document.querySelector('.tabs button.active').dataset.tab") == "khung"
    page.reload()
    page.wait_for_function("!document.body.classList.contains('gon')")
    assert len(page.evaluate(shown)) == 8


def test_banner_when_program_stops_and_restarts(page, tmp_path):
    """Cửa sổ dòng lệnh bị đóng: trang tự thấy (hỏi /api/ping định kỳ) và hiện dải báo cách mở lại. Mở lại chương
    trình trên cùng cổng (mã trang mới): dải báo đổi thành nút Tải lại trang, tải lại thì trang chạy bình thường."""
    page.wait_for_selector("#start:not([hidden])")
    assert page.locator("#offline").is_hidden()
    port = page.httpd.server_port
    page.httpd.shutdown()
    page.httpd.server_close()
    page.locator("#offline").wait_for(state="visible", timeout=15000)
    assert "Chương trình đã tắt" in page.text_content("#offline")
    httpd, app, _ = make_server(port=port, out_dir=tmp_path / "lan_hai")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        if httpd.server_port != port:
            pytest.skip("cổng cũ chưa trả lại, không mở lại được trên cùng cổng")
        _wait_text(page, "#offline", "vừa được mở lại")
        page.locator("#offline button", has_text="Tải lại trang").click()
        page.wait_for_selector("#start:not([hidden])")
        assert page.locator("#offline").is_hidden()
    finally:
        app.shutdown()
        httpd.shutdown()
        httpd.server_close()


def test_forget_data_on_a_shared_machine(page):
    """Tệp › Xóa dữ liệu trên máy này: Hủy thì giữ nguyên; Xóa thì mất bản nháp, hoàn tác và TKB máy chủ đang giữ,
    trang về màn hình Bắt đầu và chỉ thư mục kết quả (file trong đó để nguyên)."""
    draft = "JSON.parse(store.getItem('tkb-ban-nhap-v1') || 'null')"
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    page.wait_for_function("document.querySelector('#count-gv').textContent === '45'")
    page.wait_for_function(f"({draft}?.scenario.staff || []).length === 45")
    page.app.grid = ("cu", None)  # như đã xem TKB ở bước 8
    page.click("#file-menu summary")
    page.click("#btn-forget")
    page.wait_for_selector("#forget-dialog[open]")
    assert page.text_content("#forget-dir") == str(page.app.out_dir)
    page.locator("#forget-dialog button", has_text="Hủy").click()
    assert page.text_content("#count-gv") == "45" and page.app.grid is not None
    page.click("#file-menu summary")
    page.click("#btn-forget")
    page.click("#forget-ok")
    _wait_text(page, "#notice", "Đã xóa dữ liệu đang soạn")
    assert page.locator("#start").is_visible()
    assert "#" not in page.url
    assert page.locator("#btn-undo").is_disabled()
    assert page.evaluate(f"({draft}?.scenario.staff || []).length") == 0
    assert page.app.grid is None and page.app.job is None
    page.wait_for_timeout(500)  # bản nháp trống của trang mới đã lưu: vẫn không có ai
    assert page.evaluate(f"({draft}?.scenario.staff || []).length") == 0
    saved = json.loads((page.app.data / server.STORE_NAME).read_text(encoding="utf-8"))
    assert not json.loads(saved.get("tkb-ban-nhap-v1") or "null") or not json.loads(saved["tkb-ban-nhap-v1"])["scenario"]["staff"]


def test_page_keeps_nothing_in_the_browser(page):
    """Bản nháp và lựa chọn của trang ở file trang.json trong thư mục chương trình (app.data), không ở bộ nhớ của
    trình duyệt: tải lại trang thì đọc lại từ file; xóa thư mục chương trình là không còn gì."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    page.wait_for_function("document.querySelector('#count-gv').textContent === '45'")
    path = page.app.data / server.STORE_NAME

    def staff_in_file():
        draft = json.loads(path.read_text(encoding="utf-8")).get("tkb-ban-nhap-v1")
        return len(json.loads(draft)["scenario"]["staff"]) if draft else 0
    for _ in range(50):  # bản nháp ghi sau 0,3 giây (saveDraft) rồi gửi máy chủ
        if staff_in_file() == 45:
            break
        page.wait_for_timeout(100)
    assert staff_in_file() == 45
    assert page.evaluate("localStorage.length + sessionStorage.length") == 0
    page.reload()
    page.wait_for_function("document.querySelector('#count-gv').textContent === '45'")


def test_board_import(page, tmp_path):
    """Tệp › Nhập TKB đang dùng: file TKB toàn trường của trường mẫu (data/Output_Template_TKB_Toan_Truong_V8.xlsx),
    đổi các ô "Toán" thành "T" như cách viết tắt của trường: hộp thoại hỏi chữ "T", chọn Toán rồi Đọc lại, Nhập thì
    sang bước 8 với TKB đó, đúng mọi luật bắt buộc."""
    from pathlib import Path
    import openpyxl
    data = Path(__file__).resolve().parents[1] / "data"
    wb = openpyxl.load_workbook(data / "Output_Template_TKB_Toan_Truong_V8.xlsx")
    for row in wb.active.iter_rows():
        for cell in row:
            if cell.value == "Toán":
                cell.value = "T"
    board = tmp_path / "tkb_dang_dung.xlsx"
    wb.save(board)
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    page.wait_for_function("document.querySelector('#count-gv').textContent === '45'")
    page.set_input_files("#board-open", str(board))
    page.wait_for_selector("#board-dialog[open]")
    assert "'T'" in page.text_content("#board-lines")
    page.select_option('#board-map select[data-token="T"]', "Toán")
    page.click("#board-again")
    page.wait_for_function("!document.querySelector('#board-map select')")
    assert page.text_content("#board-lines").startswith("Đọc 928 ô của 29 lớp")
    page.click("#board-apply")
    page.wait_for_selector("#tkb-grid table.tkb", timeout=60000)
    _wait_mark(page, "tkb", "✓")
    assert "Đã nhập TKB đang dùng" in page.text_content("#notice")


def test_timetable_view_swap_and_undo(page, small_updated):
    """Bước 7 với TKB đã xếp của trường nhỏ: lưới đúng mọi luật; chọn một ô thì có ô viền xanh / mờ; đổi với ô không
    đổi được thì báo lỗi, viền đỏ; Hoàn tác thì hết lỗi; đổi người dạy ghi luật Chỉ giáo viên dạy."""
    page.wait_for_selector("#start:not([hidden])")
    page.set_input_files("#file-open", str(small_updated))
    page.wait_for_selector("#import-dialog[open]")
    assert "5 ngày học" in page.text_content("#import-dialog")  # bảng Ngày của khung giờ tự do (trước: 0 ngày học)
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
    assert sc["grades"] == [1, 2, 3, 4, 5, "Mầm"] and sc["cls"] == {"name": "Lá 1", "grade": "Mầm", "campus": ""}
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


def test_new_from_empty_preset(page):
    """Trang bắt đầu, Soạn mới bộ Trống: chưa có môn nào, các luật có sẵn theo quy ước Tạm tắt (bật lại bằng ô Dùng);
    bộ Tiểu học Việt Nam có đủ các môn mặc định."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="new"][data-mau="trong"]')
    page.wait_for_selector("#start", state="hidden")
    sc = page.evaluate("({subjects: st.scenario.subjects.length, off: st.scenario.rules.filter((r) => r.off).length,"
                       " rules: st.scenario.rules.length})")
    assert sc["subjects"] == 0 and sc["off"] == 14 and sc["rules"] == 23
    assert page.text_content("#count-luat") == "9"
    _wait_mark(page, "mon", "⚠")  # chưa có môn nào: bước Môn học báo
    page.click("#file-menu summary")
    page.click("#btn-new")
    page.click('[data-start="new"][data-mau="tieu_hoc_vn"]')
    page.wait_for_function("document.querySelector('#count-mon').textContent === '15'")
    assert page.evaluate("st.scenario.rules.filter((r) => r.off).length") == 0


def test_extra_roles_picker(page):
    """Hộp thoại giáo viên: cột Chức Vụ Thêm chọn bằng ô đánh dấu (Bộ Môn và các chức vụ của bước Chức vụ, trừ chức vụ
    chính), ghi theo thứ tự danh sách; bảng nhân sự hiện thành nhãn và kiểm tra vẫn ✓."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    _wait_mark(page, "gv", "✓")
    page.click('.tabs [data-tab="gv"]')
    roles = page.evaluate("st.scenario.staff.map((t) => t.role)")
    row = roles.index("Chủ Nhiệm")
    page.click(f'[data-act="edit-staff"][data-i="{row}"]')
    boxes = page.locator('#extra-box input[data-f="extra"]')
    names = [boxes.nth(k).get_attribute("data-r") for k in range(boxes.count())]
    assert names[0] == "Bộ Môn" and "Tiếng Anh" in names and "Chủ Nhiệm" not in names
    page.check('#extra-box input[data-r="Tiếng Anh"]')
    page.check('#extra-box input[data-r="Bộ Môn"]')
    assert page.evaluate(f"st.scenario.staff[{row}].extra_roles") == "Bộ Môn, Tiếng Anh"
    page.keyboard.press("Escape")
    _wait_text(page, f'#staff-table tr[data-row="{row + 2}"]', "Chức Vụ Thêm: Bộ Môn, Tiếng Anh")
    _wait_mark(page, "gv", "✓")


def test_tags_in_rule_dialog(page):
    """Cột Nhãn: nhãn lớp, tên cơ sở ghi ở bước Lớp, nhãn giáo viên ghi trong hộp thoại giáo viên hiện trong gợi ý cột
    Lớp, cột Giáo viên của hộp thoại luật; kiểm tra vẫn ✓."""
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    _wait_mark(page, "lop", "✓")
    page.click('.tabs [data-tab="lop"]')
    page.click('[data-act="classes-from-homeroom"]')
    tags = page.locator('#class-table [data-f="class"][data-i="0"][data-k="tags"]')
    tags.fill("Song ngữ")
    tags.press("Tab")
    campus = page.locator('#class-table [data-f="class"][data-i="1"][data-k="campus"]')
    campus.fill("Điểm Tân Phú")
    campus.press("Tab")
    assert page.evaluate("st.scenario.classes[1].campus") == "Điểm Tân Phú"
    page.click('.tabs [data-tab="gv"]')
    page.click('[data-act="edit-staff"][data-i="0"]')
    field = page.locator('#detail-body [data-f="staff"][data-i="0"][data-k="tags"]')
    field.fill("Tổ Một, Bán thời gian")
    field.press("Tab")
    page.keyboard.press("Escape")
    _wait_text(page, '#staff-table tr[data-row="2"]', "Nhãn: Tổ Một, Bán thời gian")
    page.click('.tabs [data-tab="luat"]')
    page.click("#btn-add-rule")
    page.click('#pick-body [data-pick="0"]')
    options = lambda sel: page.evaluate(  # noqa: E731
        f"[...document.querySelectorAll('{sel} option')].map((o) => o.value)")
    assert {"Song ngữ", "1/1", "Điểm Tân Phú", "Cơ sở 1"} <= set(options("#rule-class-list"))
    assert {"Tổ Một", "Bán thời gian", "Bộ Môn"} <= set(options("#teacher-list"))
    page.keyboard.press("Escape")
    _wait_mark(page, "lop", "✓")
    _wait_mark(page, "gv", "✓")


def test_add_rule_as_a_sentence_and_pick_a_level(page):
    """Thêm luật: chọn một câu (Môn … không học vào …), điền môn ngay trong câu và tiết ở ô Giờ nào, chọn mức độ;
    không có ô Điểm. Luật ưu tiên có sẵn mở ra chỉ có mức độ (ô Số chỉ khi số là tham số của luật), Sửa chi tiết mở cả
    câu luật."""
    from tkb.bo_mau import TIN_HOC
    page.wait_for_selector("#start:not([hidden])")
    page.click('[data-start="sample"]')
    page.click('.tabs [data-tab="luat"]')
    page.wait_for_selector("#rule-list .rule-item .tag")
    total = page.evaluate("st.scenario.rules.length")
    assert page.evaluate("st.scenario.rules.every((r) => r.points == null)")  # luật có sẵn ghi bằng mức
    page.click("#btn-add-rule")
    page.click('#pick-body [data-pick="0"]')
    assert page.locator("#rule-errors li").count() == 0  # chưa điền gì: chưa báo thiếu
    subject = page.locator('#rule-body .sentence [data-k="subject"]')
    subject.fill(TIN_HOC)
    page.fill('#rule-body [data-k="periods"]', "1")
    _wait_text(page, "#rule-time", "tiết 1")
    page.select_option('#rule-body [data-k="mode"]', "Cao")
    _wait_text(page, "#rule-say", f"{TIN_HOC} không xếp vào tiết 1 (ưu tiên cao)")
    assert page.locator('#rule-body [data-k="points"]').count() == 0
    page.click('#rule-dialog button[value="ok"]')
    # luật vào kịch bản ở sự kiện close của hộp thoại, chạy sau cú bấm
    page.wait_for_function(f"st.scenario.rules.length === {total + 1}", timeout=10000)
    rule = page.evaluate("st.scenario.rules.at(-1)")
    assert (rule["kind"], rule["subject"], rule["periods"], rule["hard"], rule["level"], rule["points"]) == \
        ("Không xếp vào", TIN_HOC, "1", False, "Cao", None)
    # Luật ưu tiên có sẵn: chỉ mức độ; luật "tối đa n tiết một nhóm môn mỗi buổi": có ô Số.
    item = page.locator("#rule-list .rule-item", has_text="tiết trống xen giữa")
    item.locator('[data-act="edit-rule"]').click()
    assert page.locator('#rule-body [data-k="number"]').count() == 0
    assert page.locator('#rule-body [data-k="mode"]').input_value() == "Thấp"
    page.click("#rule-full")
    assert page.locator('#rule-body [data-k="type"]').count() == 1
    page.keyboard.press("Escape")
    item = page.locator("#rule-list .rule-item", has_text="Mỗi buổi, một lớp học tối đa")
    item.locator('[data-act="edit-rule"]').click()
    assert page.locator('#rule-body [data-k="number"]').count() == 1
    page.keyboard.press("Escape")


def test_rooms_step(page, tmp_path):
    """Sheet PHÒNG trên trang: ô TKB ghi tên phòng, xem được TKB theo phòng; bảng Phòng học dùng chung ở bước Lớp:
    ghi môn không có thì bước Lớp ⚠ và dòng phòng viền đỏ, sửa lại thì ✓."""
    from .test_phong import ART, _file
    updated = _solved(page, lambda: _file(tmp_path, [ART], name="phong"))
    page.wait_for_selector("#start:not([hidden])")
    page.set_input_files("#file-open", str(updated))
    page.wait_for_selector("#import-dialog[open]")
    page.click("#import-apply")
    page.click('.tabs [data-tab="tkb"]')
    page.wait_for_selector("#tkb-grid table.tkb")
    _wait_mark(page, "tkb", "✓")
    assert page.locator("#tkb-grid small.room", has_text="Phòng nghệ thuật").count() == 4
    page.select_option("#tkb-view", "r:Phòng nghệ thuật")
    assert page.locator("#tkb-grid td.cell[data-cell]").count() == 4
    page.click('.tabs [data-tab="lop"]')
    subjects = page.locator('#room-table [data-f="room"][data-i="0"][data-k="subjects"]')
    assert subjects.input_value() == "Âm nhạc, Mỹ thuật"
    subjects.fill("Hóa học")
    subjects.press("Tab")
    _wait_mark(page, "lop", "⚠")
    assert page.locator('#room-table tr[data-row="p2"].has-error').count() == 1
    assert "Phòng nghệ thuật: không có môn hay nhãn môn 'Hóa học'" in page.text_content("#tab-lop")
    subjects.fill("Âm nhạc")
    subjects.press("Tab")
    _wait_mark(page, "lop", "✓")
    page.click('[data-act="add-room"]')
    assert page.evaluate("st.scenario.rooms.length") == 2


def test_split_group_cells(page, tmp_path):
    """Học cùng giờ trên trang: ô hai môn hiện "Âm nhạc / Mỹ thuật"; theo giáo viên Mỹ thuật chỉ thấy Mỹ thuật; khóa ô
    thì cả hai cặp "môn, Mã GV" có dấu khóa; kiểu luật Học cùng giờ có trong hộp thoại luật."""
    from tkb import bo_mau

    from .test_cung_gio import ART, _file
    updated = _solved(page, lambda: _file(tmp_path, [ART], name="nhom", assistant=False))
    page.wait_for_selector("#start:not([hidden])")
    page.set_input_files("#file-open", str(updated))
    page.wait_for_selector("#import-dialog[open]")
    page.click("#import-apply")
    page.click('.tabs [data-tab="tkb"]')
    page.wait_for_selector("#tkb-grid table.tkb")
    _wait_mark(page, "tkb", "✓")
    shared = page.locator("#tkb-grid td.cell", has_text=f"{bo_mau.AM_NHAC} / {bo_mau.MY_THUAT}")
    assert shared.count() == 2  # xem theo khối 3: hai lớp, mỗi lớp một ô Âm nhạc / Mỹ thuật
    cell = shared.first.get_attribute("data-cell")
    page.click(f'#tkb-grid [data-cell="{cell}"]')
    page.wait_for_function("!document.querySelector('#tkb-pick').textContent.includes('Đang tìm')", timeout=30000)
    page.click('#tkb-pick [data-tkb="lock"]')
    text = page.evaluate(f"savedGet(tkb.byKey.get({cell!r}))")
    assert text.count("(khóa)") == 2, text
    page.select_option("#tkb-view", "t:Mỹ Thuật 1")
    texts = page.locator("#tkb-grid td.cell small").all_text_contents()
    assert texts and set(texts) == {bo_mau.MY_THUAT}
    page.click('.tabs [data-tab="luat"]')
    page.click("#btn-add-rule")
    assert "học cùng giờ" in page.text_content("#rule-pick")


def test_merged_cells(page, tmp_path):
    """Ghép lớp trên trang: ô ghi "ghép 3/2"; theo giáo viên Thể dục một ô ghi "3/1, 3/2", không tô đỏ trùng giờ; chọn
    ô ghép thì báo không đổi tay được, bấm ô khác cùng lớp không đổi."""
    from .test_ghep_lop import MERGE, TD, _file
    updated = _solved(page, lambda: _file(tmp_path, [MERGE], name="ghep"))
    page.wait_for_selector("#start:not([hidden])")
    page.set_input_files("#file-open", str(updated))
    page.wait_for_selector("#import-dialog[open]")
    page.click("#import-apply")
    page.click('.tabs [data-tab="tkb"]')
    page.wait_for_selector("#tkb-grid table.tkb")
    _wait_mark(page, "tkb", "✓")
    merged = page.locator("#tkb-grid td.cell", has_text="ghép 3/2")
    assert merged.count() == 2
    cell = merged.first.get_attribute("data-cell")
    before = page.evaluate("JSON.stringify(st.scenario.saved)")
    page.click(f'#tkb-grid [data-cell="{cell}"]')
    assert "không đổi tay được" in page.text_content("#tkb-pick")
    # Bấm một ô khác của lớp đó (không ghép): không đổi gì.
    other = page.evaluate("(cls) => [...document.querySelectorAll('#tkb-grid td.cell')].map((e) => e.dataset.cell)"
                          ".find((k) => k.startsWith(cls + '|') && !tkb.byKey.get(k).merged"
                          " && tkb.byKey.get(k).subject)", cell.split("|")[0])
    page.click(f'#tkb-grid [data-cell="{other}"]')
    assert page.evaluate("JSON.stringify(st.scenario.saved)") == before
    page.select_option("#tkb-view", "t:Thể Dục 1")
    cells = page.locator("#tkb-grid td.cell:not(.empty)")
    assert cells.count() == 2 and page.locator("#tkb-grid td.cell.bad").count() == 0
    assert set(cells.locator("b").all_text_contents()) == {"3/1, 3/2"}
    assert set(cells.locator("small").all_text_contents()) == {TD}
