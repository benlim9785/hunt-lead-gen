#!/usr/bin/env python3
"""
Vision-check a specific diagram on a rendered HTML page.

PROBLEM this solves:
When using `scrollIntoView({block: 'center'})` on a SHORT image (<400px tall)
inside a 900px viewport, the image lands in the middle BUT the screenshot
captures ~640px of adjacent content above and below it. If a TALLER neighbor
diagram sits just above, vision_analyze will describe THAT diagram instead and
report your target as "not present" — leading to false-negative loops.

THE FIX: measure the image's actual bounding box, then scroll so the image
is centered in the viewport with equal headroom above and below. For images
shorter than the viewport, this still bleeds neighbors but you can shrink
the viewport height to match the image height + 100px padding.

USAGE:
    python3 vision_check_diagram.py <url> <img_filename> <output_png> [viewport_h]

EXAMPLE:
    python3 vision_check_diagram.py \\
        https://my-tunnel.trycloudflare.com/index.html \\
        leadgen-bouncers.png \\
        /tmp/check.png \\
        500
"""
import sys
from playwright.sync_api import sync_playwright


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    url = sys.argv[1]
    img_filename = sys.argv[2]
    output = sys.argv[3]
    viewport_h = int(sys.argv[4]) if len(sys.argv) > 4 else 900

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": viewport_h})
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")

        box = page.evaluate(f"""() => {{
            const img = document.querySelector('img[src="{img_filename}"]');
            if (!img) return null;
            const rect = img.getBoundingClientRect();
            return {{
                top: rect.top + window.scrollY,
                height: rect.height,
                width: rect.width
            }};
        }}""")

        if not box:
            print(f"ERROR: img[src='{img_filename}'] not found on page", file=sys.stderr)
            sys.exit(2)

        print(f"Image: top={box['top']:.0f} height={box['height']:.0f} width={box['width']:.0f}")
        print(f"Viewport height: {viewport_h}")

        # Center the image in the viewport
        target_scroll = box["top"] - (viewport_h - box["height"]) / 2
        target_scroll = max(0, target_scroll)
        page.evaluate(f"window.scrollTo(0, {target_scroll})")
        page.wait_for_timeout(500)

        # If image is much shorter than viewport, warn about adjacent-content bleed
        if box["height"] < viewport_h * 0.5:
            print(
                f"WARNING: image is short ({box['height']:.0f}px) relative to viewport "
                f"({viewport_h}px). Adjacent content WILL bleed into screenshot. "
                f"Re-run with viewport_h={int(box['height']) + 100} for tight crop.",
                file=sys.stderr,
            )

        page.screenshot(path=output)
        print(f"Saved: {output}")
        b.close()


if __name__ == "__main__":
    main()
