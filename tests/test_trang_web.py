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
    đổi được thì báo lỗi, viền đỏ; Hoàn tác thì hết lỗi."""
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
    page.select_option("#tkb-view", index=page.locator("#tkb-view option").count() - 1)  # theo giáo viên
    assert page.locator("#tkb-grid td.cell[data-cell]").count() > 0
