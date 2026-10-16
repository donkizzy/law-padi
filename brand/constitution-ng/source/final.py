"""constitution.ng — final Open Book artwork: symbol, small-size cut, wordmark and lockups."""

import math
import os
import sys

import wordmark as wmod
from geo import bbox, mirror_x, scale, svg, to_d, translate

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

GREEN = "#0A6B4B"
GREEN_LIGHT = "#6CC79A"
INK = "#14201B"
WHITE = "#FFFFFF"


# ------------------------------------------------------------------ symbol geometry
def book_page(outer_x, spine_x, top_o, top_s, bot_o, bot_s, r, tail=None):
    """Left page in math coords (y up), described with SVG-space y values (y down, 256 canvas).

    tail = (base_x, depth, left_angle, right_angle) — a speech tail hanging off the bottom edge.
    """
    Y = lambda y: 256 - y  # noqa: E731
    W = spine_x - outer_x
    dip = top_s - top_o
    sp = [("M", spine_x, Y(top_s))]
    # top edge: rises steeply out of the gutter, then runs level to the outer corner
    sp.append(("C", spine_x - 0.128 * W, Y(top_s - 0.625 * dip), spine_x - 0.404 * W, Y(top_o),
               outer_x + 0.255 * W, Y(top_o)))
    sp.append(("L", outer_x + r, Y(top_o)))
    sp.append(("A", r, r, 0, True, outer_x, Y(top_o + r)))
    sp.append(("L", outer_x, Y(bot_o - r)))
    sp.append(("A", r, r, 0, True, outer_x + r, Y(bot_o)))
    if tail:
        base_x, depth, a_left, a_right = tail
        tip_x = base_x - depth / math.tan(math.radians(a_left))
        right_x = tip_x + depth / math.tan(math.radians(a_right))
        sp += [("L", base_x, Y(bot_o)), ("L", tip_x, Y(bot_o + depth)), ("L", right_x, Y(bot_o))]
    curve_start = outer_x + 0.40 * W
    sp.append(("L", curve_start, Y(bot_o)))
    # bottom edge: level, then easing down into the gutter
    sp.append(("C", spine_x - 0.30 * W, Y(bot_o), spine_x - 0.16 * W, Y(bot_o + 0.2 * (bot_s - bot_o)),
               spine_x, Y(bot_s)))
    sp.append(("Z",))
    return [sp]


def book(gutter=20.0, outer=24.0, top_o=60.0, top_s=92.0, bot_o=200.0, bot_s=214.0, r=16.0,
         tail=(48.0, 32.0, 75.0, 40.0), lift=14.0):
    spine = 128 - gutter / 2
    left = book_page(outer, spine, top_o, top_s, bot_o, bot_s, r, tail)
    right = mirror_x(book_page(outer, spine, top_o, top_s, bot_o, bot_s, r, None), 128)
    return translate(left, 0, lift), translate(right, 0, lift)


def symbol_master():
    return book()


def symbol_reversed():
    # white on dark blooms (irradiation): open the gutter a little
    return book(gutter=23.0)


def symbol_small():
    # 16–32 px cut: wider gutter, shallower curves, bigger tail, fills the canvas
    return book(gutter=40.0, outer=8.0, top_o=34.0, top_s=56.0, bot_o=192.0, bot_s=202.0, r=20.0,
                tail=(30.0, 42.0, 75.0, 40.0), lift=8.0)


# ------------------------------------------------------------------ writers
def write(name, layers, vb, title):
    """layers: list of (subpaths_in_math_coords_already_placed, fill). Coordinates flip with oy=vb height."""
    H = vb[3]
    paths = [(to_d(sps, 0, H), fill, None) for sps, fill in layers]
    with open(os.path.join(OUT, name), "w") as fh:
        fh.write(svg(paths, vb, title))


def wordmark_shapes(weight_delta=0.0, split_ng=False):
    wmod.set_weight_delta(weight_delta)
    glyphs, _ = wmod.build()
    wmod.set_weight_delta(0.0)
    if not split_ng:
        return [sp for _, s in glyphs for sp in s], []
    head = [sp for ch, s in glyphs[:12] for sp in s]
    tail = [sp for ch, s in glyphs[12:] for sp in s]
    return head, tail


def place_horizontal(sym_l, sym_r, wm_parts, page_top=130.0, gap=62.0):
    """Symbol spans ascender (page tops at t-height) to baseline; the tail hangs like a descender."""
    # symbol space: page outer top y_svg = 60 - lift, outer bottom = 200 - lift -> in math y: 256-46=210 .. 256-186=70
    sx0, sy0, sx1, sy1 = bbox(sym_l + sym_r)
    # outer page band in math coords (from the master construction)
    top_m, bot_m = 256 - (60 - 14), 256 - (200 - 14)
    s = page_top / (top_m - bot_m)
    sym = [translate(scale(translate(p, -sx0, -bot_m), s), 0, 0) for p in (sym_l, sym_r)]
    sw = (sx1 - sx0) * s
    wx0 = min(bbox(part)[0] for part in wm_parts if part)
    wm = [translate(part, sw + gap - wx0, 0) for part in wm_parts]
    return sym, wm


def frame(groups, pad_x=24, height=256):
    allsp = [sp for g in groups for sp in g]
    x0, y0, x1, y1 = bbox(allsp)
    W = math.ceil(x1 - x0 + 2 * pad_x)
    vpad = (height - (y1 - y0)) / 2
    dx, dy = -x0 + pad_x, -y0 + vpad
    return [translate(g, dx, dy) for g in groups], (0, 0, W, height)


def frame_free(groups, pad=24):
    allsp = [sp for g in groups for sp in g]
    x0, y0, x1, y1 = bbox(allsp)
    W = math.ceil(x1 - x0 + 2 * pad)
    H = math.ceil(y1 - y0 + 2 * pad)
    dx = -x0 + (W - (x1 - x0)) / 2
    dy = -y0 + (H - (y1 - y0)) / 2
    return [translate(g, dx, dy) for g in groups], (0, 0, W, H)


if __name__ == "__main__":
    L, R = symbol_master()
    write("constitution-ng-symbol.svg", [(L + R, GREEN)], (0, 0, 256, 256), "constitution.ng")
    write("constitution-ng-symbol-black.svg", [(L + R, "#000000")], (0, 0, 256, 256), "constitution.ng")
    Lr, Rr = symbol_reversed()
    write("constitution-ng-symbol-reversed.svg", [(Lr + Rr, WHITE)], (0, 0, 256, 256), "constitution.ng")
    Ls, Rs = symbol_small()
    write("constitution-ng-symbol-small.svg", [(Ls + Rs, GREEN)], (0, 0, 256, 256), "constitution.ng")

    # wordmark alone
    wm, _ = wordmark_shapes()
    (wm_f,), vb = frame_free([wm], pad=0)
    write("constitution-ng-wordmark.svg", [(wm_f, INK)], vb, "constitution.ng")

    # horizontal lockups
    head, tail = wordmark_shapes(split_ng=True)
    (sl, sr), (h, t) = place_horizontal(L, R, [head, tail])
    groups, vb = frame([sl + sr, h, t])
    write("constitution-ng-horizontal.svg", [(groups[0], GREEN), (groups[1] + groups[2], INK)], vb,
          "constitution.ng")
    write("constitution-ng-horizontal-ng-green.svg",
          [(groups[0], GREEN), (groups[1], INK), (groups[2], GREEN)], vb, "constitution.ng")
    write("constitution-ng-horizontal-black.svg", [(groups[0] + groups[1] + groups[2], "#000000")], vb,
          "constitution.ng")

    # reversed horizontal: opened gutter + lighter wordmark
    rhead, rtail = wordmark_shapes(weight_delta=0.8, split_ng=True)
    (rsl, rsr), (rh, rt) = place_horizontal(Lr, Rr, [rhead, rtail])
    rgroups, rvb = frame([rsl + rsr, rh, rt])
    write("constitution-ng-horizontal-reversed.svg", [(rgroups[0], GREEN_LIGHT), (rgroups[1] + rgroups[2], WHITE)],
          rvb, "constitution.ng")
    write("constitution-ng-horizontal-white.svg", [(rgroups[0] + rgroups[1] + rgroups[2], WHITE)], rvb,
          "constitution.ng")

    # stacked lockup: symbol centred over the wordmark
    sx0, sy0, sx1, sy1 = bbox(L + R)
    wx0, wy0, wx1, wy1 = bbox(wm)
    ww = wx1 - wx0
    s = (0.30 * ww) / (sx1 - sx0)
    sym = translate(scale(translate(L + R, -(sx0 + sx1) / 2, -sy0), s), (wx0 + wx1) / 2, wy1 + 80)
    groups, vb = frame_free([sym, wm], pad=24)
    write("constitution-ng-stacked.svg", [(groups[0], GREEN), (groups[1], INK)], vb, "constitution.ng")
    write("constitution-ng-stacked-black.svg", [(groups[0] + groups[1], "#000000")], vb, "constitution.ng")
    symr = translate(scale(translate(Lr + Rr, -(sx0 + sx1) / 2, -sy0), s), (wx0 + wx1) / 2, wy1 + 80)
    rwm, _ = wordmark_shapes(weight_delta=0.8)
    groups, vb2 = frame_free([symr, rwm], pad=24)
    write("constitution-ng-stacked-reversed.svg", [(groups[0], GREEN_LIGHT), (groups[1], WHITE)], vb2,
          "constitution.ng")
    print("ok")
