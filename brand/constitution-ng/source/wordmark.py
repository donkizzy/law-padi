"""Custom lowercase letterforms for "constitution.ng".

Units: x-height 100, baseline 0, y up. Stems 20; curves 21 at the sides; horizontals ~18.5.
Round letters overshoot by 1.5.
"""

import math

from geo import (
    area, bbox, circle, rect, reverse, ring, rotate180, scale, sector, translate,
)

XH = 100
OV = 1.5
STEM = 20
D = 0.0  # weight delta: thins every stroke by D (D/2 per side) for reversed artwork


def set_weight_delta(d):
    global D
    D = d


def g_o():
    ro = (XH + 2 * OV) / 2  # 51.5
    return ring(ro, 50, ro - D / 2, ro - 21 + D / 2, ro - 19.5 + D / 2)


def g_c(open_deg=46):
    ro = (XH + 2 * OV) / 2
    return sector(ro, 50, ro - D / 2, ro - 21 + D / 2, open_deg, 360 - open_deg, riy=ro - 19.5 + D / 2)


def g_n(w=88):
    r_out = w / 2
    cy = XH + OV - r_out
    h = D / 2
    return (
        rect(h, 0, STEM - h, XH)
        + sector(r_out, cy, r_out - h, r_out - STEM + h, 0, 180, riy=r_out - STEM + 1.5 + h)
        + rect(w - STEM + h, 0, w - h, cy)
    )


def g_u(w=88):
    return rotate180(g_n(w), w / 2, XH / 2)


def g_i():
    h = D / 2
    return rect(h, 0, STEM - h, XH) + circle(STEM / 2, 128, 12.5 - h)


def g_t():
    foot_c = (40, 38.5)
    h = D / 2
    return (
        rect(h, foot_c[1], STEM - h, 128)
        + sector(*foot_c, 40 - h, 20 + h, 180, 270, riy=21.5 + h)
        + [[("M", 40, -OV + h), ("L", 50, -OV + h), ("L", 54, 17 - h), ("L", 40, 17 - h), ("Z",)]]
        + rect(-15, 83 + h, 46, XH - h)
    )


def g_s(w=None, beta=24.0, sx=1.21, term=30.0):
    """Two circles on one axis joined by a straight diagonal spine; then widened by sx."""
    w = 17.5 - D if w is None else w
    yT = XH + OV - w / 2
    yB = -OV + w / 2
    H = yT - yB
    b = math.radians(beta)
    r = H / (2 * (1 + 1 / math.cos(b)))
    y1 = yT - r
    y2 = yB + r
    h = w / 2
    alpha = 270 - beta  # leave C1 here (ccw)
    gamma = 90 - beta  # join C2 here (cw)
    t_top = term
    t_bot = 180 + term

    def P(cx, cy, rr, a):
        t = math.radians(a)
        return cx + rr * math.cos(t), cy + rr * math.sin(t)

    # Right-hand offset (outer on C1, inner on C2)
    a1 = P(0, y1, r + h, t_top)
    a2 = P(0, y1, r + h, alpha)
    a3 = P(0, y2, r - h, gamma)
    a4 = P(0, y2, r - h, t_bot)
    # Left-hand offset (inner on C1, outer on C2)
    b1 = P(0, y1, r - h, t_top)
    b2 = P(0, y1, r - h, alpha)
    b3 = P(0, y2, r + h, gamma)
    b4 = P(0, y2, r + h, t_bot)

    def large(span):
        return 1 if span > 180 else 0

    span1 = alpha - t_top  # ccw
    span2 = (gamma - t_bot) % 360  # cw from gamma down to t_bot
    sp = [
        ("M", *a1),
        ("A", r + h, r + h, large(span1), True, *a2),
        ("L", *a3),
        ("A", r - h, r - h, large(span2), False, *a4),
        ("L", *b4),
        ("A", r + h, r + h, large(span2), True, *b3),
        ("L", *b2),
        ("A", r - h, r - h, large(span1), False, *b1),
        ("Z",),
    ]
    shape = [sp]
    if area(sp) < 0:
        shape = [reverse(sp)]
    shape = scale(shape, sx, 0, 0, 1)
    x0, _, _, _ = bbox(shape)
    return translate(shape, -x0, 0)


def g_dot():
    return circle(12, 11, 12.5 - D / 2)


def g_g():
    ro = (XH + 2 * OV) / 2
    stem_x0 = 2 * ro - STEM
    hook_r = 40
    hook_c = (2 * ro - hook_r, -16.5)
    h = D / 2
    return (
        ring(ro, 50, ro - h, ro - 21 + h, ro - 19.5 + h)
        + rect(stem_x0 + h, hook_c[1], 2 * ro - h, XH)
        + sector(*hook_c, hook_r - h, hook_r - STEM + h, 205, 360, riy=hook_r - STEM + 1.5 + h)
    )


# (glyph builder, left side bearing, right side bearing)
GLYPHS = {
    "c": (g_c, 9, 3),
    "o": (g_o, 9, 9),
    "n": (g_n, 13, 12),
    "s": (g_s, 8, 8),
    "t": (g_t, 3, 1),
    "i": (g_i, 13, 13),
    "u": (g_u, 12, 13),
    ".": (g_dot, 7, 7),
    "g": (g_g, 9, 12),
}

KERN = {
    ("c", "o"): -1,
    ("s", "t"): 0,
    ("t", "i"): 0,
    ("i", "t"): 0,
    ("t", "u"): 0,
    ("u", "t"): 0,
    ("n", "."): -2,
    (".", "n"): -1,
}


def build(text="constitution.ng", tracking=0.0, overrides=None):
    """Return (subpaths per glyph, advance width)."""
    global D
    overrides = overrides or {}
    x = 0.0
    out = []
    prev = None
    for ch in text:
        fn, lsb, rsb = GLYPHS[ch]
        d_now, D = D, 0.0
        x0, _, x1, _ = bbox(overrides.get(ch, fn)())
        D = d_now
        shape = overrides.get(ch, fn)()
        if prev is not None:
            x += KERN.get((prev, ch), 0) + tracking
        x += lsb
        out.append((ch, translate(shape, x - x0, 0)))
        x += (x1 - x0) + rsb
        prev = ch
    # trim leading lsb / trailing rsb so ink starts at 0
    first_lsb = GLYPHS[text[0]][1]
    last_rsb = GLYPHS[text[-1]][2]
    out = [(ch, translate(s, -first_lsb, 0)) for ch, s in out]
    return out, x - first_lsb - last_rsb
