#!/usr/bin/env python3
"""
LinkedIn login DOM probe.

Run this when LinkedIn redesigns the login page and the setup script
breaks with a Page.fill timeout. Dumps every <input> on /login with
its name/id/type/placeholder/autocomplete attrs so you can build new
selectors without guessing.

Usage: python3 lk_dom_probe.py
"""
import asyncio
from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROFILE_DIR = "/tmp/lk-dom-probe-profile"


async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=True, user_agent=UA,
            viewport={"width": 1366, "height": 900},
        )
        page = await ctx.new_page()
        await page.goto("https://www.linkedin.com/login",
                        wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"URL: {page.url}")
        print(f"TITLE: {await page.title()}")
        inputs = await page.query_selector_all("input")
        print(f"\nFound {len(inputs)} <input> elements:")
        for i, inp in enumerate(inputs):
            attrs = {}
            for k in ("name", "id", "type", "placeholder", "autocomplete"):
                v = await inp.get_attribute(k)
                if v is not None:
                    attrs[k] = v
            print(f"  [{i}] {attrs}")
        buttons = await page.query_selector_all("button[type='submit']")
        print(f"\nFound {len(buttons)} submit button(s):")
        for i, b in enumerate(buttons):
            txt = (await b.text_content() or "").strip()
            id_ = await b.get_attribute("id")
            print(f"  [{i}] text={txt!r} id={id_!r}")
        await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())
