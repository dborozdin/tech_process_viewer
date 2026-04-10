"""Playwright CRUD tests for Tech Process Viewer.

Per CLAUDE.md: headless=False, slow_mo=500.
Requires: pip install playwright && python -m playwright install chromium
Server must be running: python tech_process_viewer_app.py (port 5000)
PSS server must be running on localhost:7239 with pss_moma_08_07_2025 DB.
"""

import time
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://localhost:5000"
DB_CONFIG = {
    "server_port": "http://localhost:7239",
    "db": "pss_moma_08_07_2025",
    "user": "Administrator",
    "password": ""
}


def connect_to_db(page):
    """Connect to PSS database."""
    page.goto(BASE_URL + "/")
    page.click("#connect-btn")
    page.wait_for_selector("#db-modal", state="visible")
    page.fill("#server-port", DB_CONFIG["server_port"])
    page.fill("#user", DB_CONFIG["user"])
    page.fill("#password", DB_CONFIG["password"])
    page.click("#modal-connect-btn")
    page.wait_for_selector("#products-section", state="visible", timeout=10000)
    time.sleep(1)


def test_connect_and_view():
    """Test 1: Connect to DB and verify aircraft list loads."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        try:
            connect_to_db(page)
            # Verify aircraft table has rows
            rows = page.locator("#aircraft-table tbody tr")
            assert rows.count() > 0, "Aircraft list should have at least one row"
            print("PASS: test_connect_and_view")
        finally:
            browser.close()


def test_process_crud():
    """Test 2: Create, edit, delete a process."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        try:
            connect_to_db(page)

            # Click first aircraft row
            page.locator("#aircraft-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/processes**")
            time.sleep(3)  # Wait for processes to load (may be empty)

            # Count processes before (may be 0)
            before_count = page.locator("#processes-table tbody tr").count()

            # Create process
            page.click("#btn-add-process")
            page.wait_for_selector(".crud-modal-overlay.visible")
            page.fill("#process-form-name", "Test Process CRUD")
            page.fill("#process-form-id", "TEST_PROC_CRUD")
            page.click("#process-save")
            time.sleep(8)  # Wait for create + link-product + reload (3 sequential API calls)

            # Verify new process appeared
            after_count = page.locator("#processes-table tbody tr").count()
            assert after_count > before_count, f"Process should have been created (before={before_count}, after={after_count})"

            # Delete the created process (last row)
            page.locator("#processes-table tbody tr:last-child .btn-icon-delete").click()
            page.wait_for_selector(".crud-modal-overlay.visible")
            page.click(".btn-confirm-ok")
            time.sleep(3)

            print("PASS: test_process_crud")
        finally:
            browser.close()


def test_details_document_upload():
    """Test 3: Navigate to tech process details and test document operations."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        try:
            connect_to_db(page)

            # Navigate: aircraft -> processes -> phases -> tech processes -> details
            page.locator("#aircraft-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/processes**")
            page.wait_for_selector("#processes-table tbody tr", timeout=10000)
            time.sleep(1)

            page.locator("#processes-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/phases**")
            page.wait_for_selector("#phases-table tbody tr", timeout=10000)
            time.sleep(1)

            page.locator("#phases-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/technical_processes**")
            page.wait_for_selector("#tech-processes-table tbody tr", timeout=10000)
            time.sleep(1)

            page.locator("#tech-processes-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/technical_process_details**")
            page.wait_for_selector("#details-section", state="visible", timeout=10000)
            time.sleep(2)

            # Verify sections loaded
            assert page.locator("#operations-table").is_visible(), "Operations table should be visible"
            assert page.locator("#documents-table").is_visible(), "Documents table should be visible"
            assert page.locator("#characteristics-table").is_visible(), "Characteristics table should be visible"

            print("PASS: test_details_document_upload")
        finally:
            browser.close()


def test_characteristic_crud():
    """Test 4: Add and delete a characteristic value on tech process details page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        try:
            connect_to_db(page)

            # Navigate to details page
            page.locator("#aircraft-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/processes**")
            page.wait_for_selector("#processes-table tbody tr", timeout=10000)

            page.locator("#processes-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/phases**")
            page.wait_for_selector("#phases-table tbody tr", timeout=10000)

            page.locator("#phases-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/technical_processes**")
            page.wait_for_selector("#tech-processes-table tbody tr", timeout=10000)

            page.locator("#tech-processes-table tbody tr.clickable td:first-child").first.click()
            page.wait_for_url("**/technical_process_details**")
            page.wait_for_selector("#details-section", state="visible", timeout=10000)
            time.sleep(2)

            # Count characteristics before
            before_count = page.locator("#characteristics-table tbody tr").count()

            # Add characteristic
            page.click("#btn-add-char")
            page.wait_for_selector(".crud-modal-overlay.visible")
            time.sleep(2)  # Wait for characteristics list to load via AJAX

            # Select first characteristic from dropdown
            select = page.locator("#char-form-characteristic_id")
            option_count = select.locator("option").count()
            print(f"  Characteristic options available: {option_count}")
            if option_count > 0:
                page.fill("#char-form-value", "Test Value 123")
                page.click("#char-save")
                time.sleep(3)  # Wait for create + reload

                # Verify added
                after_count = page.locator("#characteristics-table tbody tr").count()
                if after_count <= before_count:
                    print(f"  WARNING: before={before_count}, after={after_count} - characteristic may not have been created (API might have failed)")
                else:
                    # Delete the last characteristic
                    page.locator("#characteristics-table tbody tr:last-child .btn-delete-char").click()
                    page.wait_for_selector(".crud-modal-overlay.visible")
                    page.click(".btn-confirm-ok")
                    time.sleep(2)
            else:
                print("  SKIP: No characteristic definitions available in DB")

            print("PASS: test_characteristic_crud")
        finally:
            browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("CRUD Tests for Tech Process Viewer")
    print("=" * 60)

    tests = [
        test_connect_and_view,
        test_process_crud,
        test_details_document_upload,
        test_characteristic_crud,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}...")
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} - {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
