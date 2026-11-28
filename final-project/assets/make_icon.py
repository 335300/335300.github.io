"""Draw the Personal Centwise app icon (1024x1024 PNG) — source of truth for icon.icns.

A rounded violet square with a white "C" and a small teal coin.
Usage:  python assets/make_icon.py assets/icon-1024.png   (needs Pillow)
"""

import sys

from PIL import Image, ImageDraw

SIZE = 1024
VIOLET = (109, 40, 217)    # logo  #6D28D9
TEAL = (45, 212, 191)      # dark-theme secondary, bright enough on violet
WHITE = (255, 255, 255)


def draw(path: str) -> None:
    scale = 4  # draw large, then downsample for smooth edges
    s = SIZE * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = int(s * 0.09)
    d.rounded_rectangle([margin, margin, s - margin, s - margin], radius=int(s * 0.2), fill=VIOLET)
    # The "C": a thick arc opening to the right.
    box = [int(s * 0.27), int(s * 0.27), int(s * 0.73), int(s * 0.73)]
    d.arc(box, start=40, end=320, fill=WHITE, width=int(s * 0.085))
    # The coin.
    r = int(s * 0.06)
    cx, cy = int(s * 0.715), int(s * 0.5)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=TEAL)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path)


if __name__ == "__main__":
    draw(sys.argv[1] if len(sys.argv) > 1 else "icon-1024.png")
