from playwright.sync_api import Page, expect, sync_playwright
import time

def verify_ui(page: Page):
    # 1. Arrange: Go to the app homepage.
    page.goto("http://127.0.0.1:5000")

    # 2. Assert: Check if the title is correct.
    expect(page).to_have_title("SnappBot Control")

    # 3. Assert: Check if the header and status are visible.
    expect(page.locator("h1")).to_contain_text("SnappBot Control Center")
    expect(page.get_by_text("Stopped")).to_be_visible()

    # 4. Assert: Check for the new controls.
    expect(page.get_by_role("button", name="Start Bot")).to_be_visible()

    # 5. Screenshot: Capture the UI.
    page.screenshot(path="/home/jules/verification/ui_verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_ui(page)
        finally:
            browser.close()
