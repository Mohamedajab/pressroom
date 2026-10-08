"""Local browser smoke test; requires a running server with seed_demo content."""

import argparse
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    screenshots = root / "docs" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, device_scale_factor=1
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{args.base_url}/accounts/login/")
        page.screenshot(path=str(screenshots / "login.png"), full_page=True)

        def login(username):
            page.goto(f"{args.base_url}/accounts/login/")
            page.get_by_label("Username").fill(username)
            page.get_by_label("Password").fill(args.password)
            page.get_by_role("button", name="Sign in to Pressroom").click()
            expect(page.get_by_role("heading", name="Good ideas live here.")).to_be_visible()

        login("author")
        page.screenshot(path=str(screenshots / "dashboard.png"), full_page=True)
        page.get_by_role("link", name="New page").click()
        expect(page.get_by_role("heading", name="Start something good.")).to_be_visible()
        slug = f"browser-smoke-{uuid4().hex[:8]}"
        page.get_by_label("Title").fill("A browser-tested publishing journey")
        page.get_by_label("Slug").fill(slug)
        page.get_by_label("Excerpt").fill(
            "Written, reviewed and published through the real user interface."
        )
        page.get_by_label("Body").fill(
            "## A working workflow\n\nThis story travelled from **draft** to publication."
        )
        page.get_by_role("button", name="Save draft").click()
        detail_url = page.url
        page.get_by_role("button", name="Send for review").click()
        expect(page.locator(".workflow-panel .badge")).to_have_text("In review")
        page.get_by_role("button", name="Sign out").click()
        login("editor")
        page.goto(detail_url)
        page.screenshot(path=str(screenshots / "review.png"), full_page=True)
        page.get_by_role("button", name="Approve & publish").click()
        expect(page.locator(".workflow-panel .badge")).to_have_text("Published")
        page.goto(f"{args.base_url}/sites/fieldnotes/{slug}/")
        expect(
            page.get_by_role("heading", name="A browser-tested publishing journey")
        ).to_be_visible()
        expect(page.locator(".prose strong")).to_have_text("draft")
        page.goto(f"{args.base_url}/sites/fieldnotes/")
        page.screenshot(path=str(screenshots / "publication.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{args.base_url}/workspace/fieldnotes/")
        expect(page.get_by_role("link", name="New page")).to_be_visible()
        page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
            "Mobile document overflows"
        )
        # Archive the smoke article after the public-read assertion.
        page.goto(detail_url)
        page.get_by_role("button", name="Archive and unpublish").click()
        response = page.goto(f"{args.base_url}/sites/fieldnotes/{slug}/")
        assert response.status == 404
        assert not errors, errors
        browser.close()
    print(
        "Browser smoke passed: author create/submit, editor publish, public read, archive, mobile layout."
    )


if __name__ == "__main__":
    main()
