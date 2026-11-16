"""Tiny geometry kit for hand-built logo SVGs.

Shapes are built in math coordinates (y up) as lists of subpaths. Each subpath is a list of
segments: ("M", x, y) | ("L", x, y) | ("A", rx, ry, large, ccw, x, y) | ("Z",).
`to_svg` maps them to SVG space with a translate/scale/y-flip baked into the coordinates.
"""

import math


def f(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pol(cx, cy, r, a):
    t = math.radians(a)
    return cx + r * math.cos(t), cy + r * math.sin(t)


def ell_pt(cx, cy, rx, ry, a):
    t = math.radians(a)
    c, s = math.cos(t), math.sin(t)
    r = 1 / math.sqrt((c / rx) ** 2 + (s / ry) ** 2)
    return cx + r * c, cy + r * s


def rect(x0, y0, x1, y1):
    return [[("M", x0, y0), ("L", x1, y0), ("L", x1, y1), ("L", x0, y1), ("Z",)]]


def circle(cx, cy, r, ccw=True):
    a = ("A", r, r, 0, ccw)
    if ccw:
        return [[("M", cx + r, cy), (*a, cx - r, cy), (*a, cx + r, cy), ("Z",)]]
    return [[("M", cx + r, cy), (*a, cx - r, cy), (*a, cx + r, cy), ("Z",)]]


def ellipse(cx, cy, rx, ry, ccw=True):
    a = ("A", rx, ry, 0, ccw)
    return [[("M", cx + rx, cy), (*a, cx - rx, cy), (*a, cx + rx, cy), ("Z",)]]


def ring(cx, cy, ro, rix, riy=None):
    riy = rix if riy is None else riy
    return circle(cx, cy, ro, True) + ellipse(cx, cy, rix, riy, False)


def sector(cx, cy, ro, rix, a0, a1, riy=None, rox=None, roy=None):
    """Annular sector swept counter-clockwise from a0 to a1 (degrees)."""
    riy = rix if riy is None else riy
    rox = ro if rox is None else rox
    roy = ro if roy is None else roy
    large = 1 if (a1 - a0) > 180 else 0
    o0 = ell_pt(cx, cy, rox, roy, a0)
    o1 = ell_pt(cx, cy, rox, roy, a1)
    i1 = ell_pt(cx, cy, rix, riy, a1)
    i0 = ell_pt(cx, cy, rix, riy, a0)
    return [
        [
            ("M", *o0),
            ("A", rox, roy, large, True, *o1),
            ("L", *i1),
            ("A", rix, riy, large, False, *i0),
            ("Z",),
        ]
    ]


def xform(subpaths, fn_pt, fn_r=None, flips=False):
    """Apply a point transform. fn_r maps (rx, ry) -> (rx, ry). flips=True for reflections."""
    out = []
    for sp in subpaths:
        nsp = []
        for seg in sp:
            if seg[0] in ("M", "L"):
                nsp.append((seg[0], *fn_pt(seg[1], seg[2])))
            elif seg[0] == "A":
                rx, ry = (fn_r or (lambda a, b: (a, b)))(seg[1], seg[2])
                ccw = (not seg[4]) if flips else seg[4]
                nsp.append(("A", rx, ry, seg[3], ccw, *fn_pt(seg[5], seg[6])))
            elif seg[0] == "C":
                nsp.append(
                    (
                        "C",
                        *fn_pt(seg[1], seg[2]),
                        *fn_pt(seg[3], seg[4]),
                        *fn_pt(seg[5], seg[6]),
                    )
                )
            else:
                nsp.append(seg)
        out.append(nsp)
    return out


def translate(sps, dx, dy):
    return xform(sps, lambda x, y: (x + dx, y + dy))


def scale(sps, s, cx=0, cy=0, sy=None):
    sy = s if sy is None else sy
    return xform(
        sps,
        lambda x, y: (cx + (x - cx) * s, cy + (y - cy) * sy),
        lambda rx, ry: (rx * s, ry * sy),
        flips=(s * sy) < 0,
    )


def rotate180(sps, cx, cy):
    return xform(sps, lambda x, y: (2 * cx - x, 2 * cy - y))


def mirror_x(sps, cx):
    return xform(sps, lambda x, y: (2 * cx - x, y), flips=True)


def reverse(sp):
    """Reverse a single closed subpath's direction."""
    start = None
    cur = None
    segs = []
    for seg in sp:
        if seg[0] == "M":
            start = cur = (seg[1], seg[2])
        elif seg[0] == "L":
            segs.append(("L", None, cur, (seg[1], seg[2])))
            cur = (seg[1], seg[2])
        elif seg[0] == "A":
            segs.append(("A", seg[1:5], cur, (seg[5], seg[6])))
            cur = (seg[5], seg[6])
        elif seg[0] == "Z":
            if cur != start and start is not None:
                segs.append(("L", None, cur, start))
    out = [("M", *start)]
    for kind, data, a, b in reversed(segs):
        if kind == "L":
            out.append(("L", *a))
        else:
            rx, ry, large, ccw = data
            out.append(("A", rx, ry, large, not ccw, *a))
    out.append(("Z",))
    return out


def sample(sp, n=24):
    pts = []
    cur = None
    for seg in sp:
        if seg[0] == "M":
            cur = (seg[1], seg[2])
            pts.append(cur)
        elif seg[0] == "L":
            cur = (seg[1], seg[2])
            pts.append(cur)
        elif seg[0] == "A":
            rx, ry, large, ccw, x, y = seg[1:]
            pts.extend(arc_points(cur, (x, y), rx, ry, large, ccw, n))
            cur = (x, y)
        elif seg[0] == "C":
            x1, y1, x2, y2, x, y = seg[1:]
            x0, y0 = cur
            for k in range(1, n + 1):
                t = k / n
                u = 1 - t
                pts.append(
                    (
                        u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x,
                        u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y,
                    )
                )
            cur = (x, y)
    return pts


def arc_points(p0, p1, rx, ry, large, ccw, n):
    # Endpoint -> centre parameterisation (math coords, axis-aligned ellipse).
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    x1p, y1p = dx, dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0, num / den)) if den else 0
    if bool(large) == bool(ccw):
        co = -co
    cxp = co * rx * y1p / ry
    cyp = -co * ry * x1p / rx
    cx = cxp + (x0 + x1) / 2
    cy = cyp + (y0 + y1) / 2
    t0 = math.atan2((y0 - cy) / ry, (x0 - cx) / rx)
    t1 = math.atan2((y1 - cy) / ry, (x1 - cx) / rx)
    dt = t1 - t0
    if ccw and dt < 0:
        dt += 2 * math.pi
    if not ccw and dt > 0:
        dt -= 2 * math.pi
    return [
        (cx + rx * math.cos(t0 + dt * k / n), cy + ry * math.sin(t0 + dt * k / n))
        for k in range(1, n + 1)
    ]


def area(sp):
    pts = sample(sp)
    a = 0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


def bbox(sps):
    xs, ys = [], []
    for sp in sps:
        for x, y in sample(sp, 48):
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def to_d(sps, ox=0.0, oy=0.0, s=1.0):
    """Math coords -> SVG d string. SVG point = (ox + s*x, oy - s*y)."""
    parts = []
    for sp in sps:
        for seg in sp:
            if seg[0] in ("M", "L"):
                parts.append(f"{seg[0]}{f(ox + s * seg[1])} {f(oy - s * seg[2])}")
            elif seg[0] == "A":
                rx, ry, large, ccw, x, y = seg[1:]
                sweep = 0 if ccw else 1  # y-flip: math ccw == SVG sweep 0
                parts.append(
                    f"A{f(rx * s)} {f(ry * s)} 0 {large} {sweep} {f(ox + s * x)} {f(oy - s * y)}"
                )
            elif seg[0] == "C":
                x1, y1, x2, y2, x, y = seg[1:]
                parts.append(
                    f"C{f(ox + s * x1)} {f(oy - s * y1)} {f(ox + s * x2)} {f(oy - s * y2)} {f(ox + s * x)} {f(oy - s * y)}"
                )
            else:
                parts.append("Z")
    return "".join(parts)


def svg(paths, vb, title, extra=""):
    """paths: list of (d, fill, fill_rule|None)."""
    w, h = vb[2], vb[3]
    body = []
    for d, fill, rule in paths:
        r = f' fill-rule="{rule}"' if rule else ""
        body.append(f'  <path fill="{fill}"{r} d="{d}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(f(v) for v in vb)}" '
        f'width="{f(w)}" height="{f(h)}" role="img" aria-labelledby="title">\n'
        f'  <title id="title">{title}</title>\n'
        + extra
        + "\n".join(body)
        + "\n</svg>\n"
    )
