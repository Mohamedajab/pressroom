"""Exercise the opt-in visitor demo against a running local server."""

import argparse
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def activate(page, target):
    """Reach the real control through the tab order, then activate it."""
    for _ in range(60):
        if target.evaluate("element => element === document.activeElement"):
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.keyboard.press("Enter")
            return
        page.keyboard.press("Tab")
    raise AssertionError("Control could not be reached by keyboard")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--record-video", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(slow_mo=150 if args.record_video else 0)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            record_video_dir=str(output.parent / "recordings") if args.record_video else None,
            record_video_size={"width": 1280, "height": 900},
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base_url + "/demo/")
        page.screenshot(path=str(output / "demo-start.jpg"), full_page=True)
        activate(page, page.get_by_role("button", name="Start my demo"))
        dashboard = page.url
        page.screenshot(path=str(output / "dashboard.jpg"), full_page=True)
        activate(page, page.get_by_role("link", name="New page"))
        slug = "demo-smoke-" + uuid4().hex[:8]
        page.get_by_label("Title").fill("A browser-tested story")
        page.get_by_label("Slug").fill(slug)
        page.get_by_label("Body").fill(
            "## Browser verification\n\nOnly approved content becomes public."
        )
        activate(page, page.get_by_role("button", name="Save draft"))
        detail = page.url
        workspace_slug = dashboard.split("/workspace/")[1].strip("/")
        public = args.base_url + "/sites/" + workspace_slug + "/" + slug + "/"
        assert context.request.get(public).status == 404
        activate(page, page.get_by_role("button", name="Send for review"))
        activate(page, page.get_by_role("button", name="Switch to editor"))
        page.goto(detail)
        activate(page, page.get_by_role("button", name="Approve & publish"))
        page.screenshot(path=str(output / "review.jpg"), full_page=True)
        response = context.request.get(public)
        assert response.status == 200
        assert "Only approved content becomes public." in response.text()
        page.get_by_role("link", name="Edit draft").click()
        page.get_by_label("Body").fill("A private edit that has not been approved.")
        activate(page, page.get_by_role("button", name="Save draft"))
        assert "private edit" not in context.request.get(public).text()
        # Two tabs loaded the same revision; saving one must not discard the other's text.
        edit_url = detail + "edit/"
        page.goto(edit_url)
        stale = context.new_page()
        stale.goto(edit_url)
        page.get_by_label("Body").fill("Newer private draft")
        activate(page, page.get_by_role("button", name="Save draft"))
        stale.get_by_label("Body").fill("Keep this unsaved text")
        with stale.expect_response(
            lambda response: response.url == edit_url and response.request.method == "POST"
        ) as conflict:
            activate(stale, stale.get_by_role("button", name="Save draft"))
        assert conflict.value.status == 409
        expect(stale.get_by_label("Body")).to_have_value("Keep this unsaved text")
        expect(stale.get_by_role("alert")).to_contain_text("Copy your unsaved text")
        expect(stale.locator("#form-errors")).to_be_focused()
        assert "private" not in context.request.get(public).text()
        stale.screenshot(path=str(output / "edit-conflict.jpg"), full_page=True)
        stale.close()

        # A duplicate slug reaches server validation with all submitted text retained.
        page.goto(dashboard + "new/")
        page.get_by_label("Title").fill("Another story")
        page.get_by_label("Slug").fill(slug)
        page.get_by_label("Body").fill("Keep this duplicate-slug draft")
        activate(page, page.get_by_role("button", name="Save draft"))
        expect(page.get_by_role("alert")).to_be_visible()
        expect(page.get_by_label("Body")).to_have_value("Keep this duplicate-slug draft")
        expect(page.locator("#form-errors")).to_be_focused()

        public_page = context.new_page()
        public_page.goto(public)
        expect(public_page.get_by_text("Only approved content becomes public.")).to_be_visible()
        public_page.screenshot(path=str(output / "publication.jpg"), full_page=True)
        public_page.close()
        other = browser.new_context()
        other_page = other.new_page()
        other_page.goto(args.base_url + "/demo/")
        activate(other_page, other_page.get_by_role("button", name="Start my demo"))
        assert other_page.url != dashboard
        assert other.request.get(dashboard).status == 403
        other.close()
        page.goto(dashboard)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "demo-mobile.jpg"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        expect(page.get_by_role("button", name="Switch to author")).to_be_visible()
        video = page.video
        context.close()
        if args.record_video:
            video.save_as(output.parent / "recordings" / "publishing-workflow.webm")
            # Auxiliary tabs are not part of the walkthrough.
            for recording in (output.parent / "recordings").glob("*.webm"):
                if recording.name != "publishing-workflow.webm":
                    recording.unlink()
        browser.close()
    print(
        "Visitor demo passed: draft, review, publish, private edits, conflicts, validation, keyboard controls, isolation and mobile layout."
    )


if __name__ == "__main__":
    main()
