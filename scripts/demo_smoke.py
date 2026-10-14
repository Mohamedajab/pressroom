"""Exercise the opt-in visitor demo against a running local server."""

import argparse
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base_url + "/demo/")
        page.screenshot(path=str(output / "demo-start.png"), full_page=True)
        page.get_by_role("button", name="Start my demo").click()
        dashboard = page.url
        page.screenshot(path=str(output / "demo-workspace.png"), full_page=True)
        page.get_by_role("link", name="New page").click()
        slug = "demo-smoke-" + uuid4().hex[:8]
        page.get_by_label("Title").fill("A browser-tested story")
        page.get_by_label("Slug").fill(slug)
        page.get_by_label("Body").fill(
            "## Browser verification\n\nOnly approved content becomes public."
        )
        page.get_by_role("button", name="Save draft").click()
        detail = page.url
        workspace_slug = dashboard.split("/workspace/")[1].strip("/")
        public = args.base_url + "/sites/" + workspace_slug + "/" + slug + "/"
        assert context.request.get(public).status == 404
        page.get_by_role("button", name="Send for review").click()
        page.get_by_role("button", name="Switch to editor").click()
        page.goto(detail)
        page.get_by_role("button", name="Approve & publish").click()
        page.screenshot(path=str(output / "demo-review.png"), full_page=True)
        response = context.request.get(public)
        assert response.status == 200
        assert "Only approved content becomes public." in response.text()
        page.get_by_role("link", name="Edit draft").click()
        page.get_by_label("Body").fill("A private edit that has not been approved.")
        page.get_by_role("button", name="Save draft").click()
        assert "private edit" not in context.request.get(public).text()
        other = browser.new_context()
        other_page = other.new_page()
        other_page.goto(args.base_url + "/demo/")
        other_page.get_by_role("button", name="Start my demo").click()
        assert other_page.url != dashboard
        assert other.request.get(dashboard).status == 403
        other.close()
        page.goto(dashboard)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "demo-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        expect(page.get_by_role("button", name="Switch to author")).to_be_visible()
        browser.close()
    print(
        "Visitor demo passed: draft, review, publish, private edits, isolation and mobile layout."
    )


if __name__ == "__main__":
    main()
