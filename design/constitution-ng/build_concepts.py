"""Build review SVGs; fontTools and the two OFL fonts are temporary tooling.

PYTHONPATH=/private/tmp/constitution-logo-python python3 build_concepts.py 1
Font sources and license records are in brief.md and review/font-notes.md.
"""
from pathlib import Path
import math
import sys
from xml.sax.saxutils import escape

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parent
FONTS = Path('/private/tmp/constitution-logo-fonts')
VERSION = int(sys.argv[1]) if len(sys.argv) > 1 else 1
BLACK = '#000000'


def svg(title, body, width=256):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} 256" '
            f'role="img" aria-labelledby="logo-title">\n'
            f'<title id="logo-title">{escape(title)}</title>\n'
            f'<g fill="{BLACK}">{body}</g>\n</svg>\n')


def path(d):
    return f'<path d="{d}"/>'


def outline_word(fontfile, x, baseline, size=142, tracking=-1.3):
    font = TTFont(FONTS / fontfile)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font['head'].unitsPerEm
    pen = SVGPathPen(glyphs, ntos=lambda n: str(round(n, 2)))
    for char in 'constitution.ng':
        name = cmap[ord(char)]
        # The period is a deliberately drawn square, echoing the compact national stripe.
        if char == '.':
            advance = font['hmtx'][name][0] * scale
            side = 14
            left = x + (advance - side) / 2
            pen.moveTo((left, baseline - side))
            pen.lineTo((left + side, baseline - side))
            pen.lineTo((left + side, baseline))
            pen.lineTo((left, baseline))
            pen.closePath()
        else:
            glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        x += font['hmtx'][name][0] * scale + tracking
    return path(pen.getCommands()), x


def open_clause():
    # Exact circular arcs; flag band is a true hole, with no white patch.
    outer, inner = 104, 62
    left, right = (110, 140) if VERSION == 1 else (108, 144)
    def y(radius, x, upper=True):
        return 128 + (-1 if upper else 1) * math.sqrt(radius**2 - (x-128)**2)
    def pt(x, yy):
        return f'{x:.2f} {yy:.2f}'
    left_part = (
        f'M{pt(left,y(outer,left))} A{outer} {outer} 0 0 0 {pt(left,y(outer,left,False))} '
        f'L{pt(left,y(inner,left,False))} A{inner} {inner} 0 0 1 {pt(left,y(inner,left))} Z'
    )
    angle = math.radians(40 if VERSION == 1 else 45)
    ox, oy = 128+outer*math.cos(angle), 128-outer*math.sin(angle)
    ix, iy = 128+inner*math.cos(angle), 128-inner*math.sin(angle)
    top = (f'M{pt(right,y(outer,right))} A{outer} {outer} 0 0 1 {pt(ox,oy)} '
           f'L{pt(ix,iy)} A{inner} {inner} 0 0 0 {pt(right,y(inner,right))} Z')
    bottom = (f'M{pt(right,y(inner,right,False))} A{inner} {inner} 0 0 0 {pt(ix,256-iy)} '
              f'L{pt(ox,256-oy)} A{outer} {outer} 0 0 1 {pt(right,y(outer,right,False))} Z')
    drawing = path(left_part) + path(top) + path(bottom)
    return drawing if VERSION == 1 else f'<g transform="translate(10 0)">{drawing}</g>'


def peoples_quote():
    if VERSION == 1:
        one = 'M32 80 Q32 40 72 40 H100 V156 L48 208 H32 V80 Z'
        two = 'M156 80 Q156 40 196 40 H224 V156 L172 208 H156 V80 Z'
    else:
        # Equal 64-unit positive / negative / positive flag bands; a restrained shoulder.
        one = 'M32 72 Q32 40 64 40 H96 V160 L48 208 H32 V72 Z'
        two = 'M160 72 Q160 40 192 40 H224 V160 L176 208 H160 V72 Z'
    return path(one) + path(two)


def shared_initials():
    if VERSION == 1:
        # n and g join at a common upright; g's counter is wound oppositely.
        body = ('M24 164 V56 H56 V72 C66 58 82 52 100 52 C119 52 131 60 140 74 '
                'C150 60 165 52 184 52 C216 52 236 74 236 106 V166 '
                'C236 208 212 232 172 232 H132 V200 H170 C191 200 204 189 204 170 V160 '
                'C196 170 184 174 170 174 C146 174 128 163 116 146 '
                'V104 C116 90 108 82 94 82 C71 82 56 98 56 118 V164 H24 Z '
                'M204 112 C204 94 194 82 177 82 C160 82 150 94 150 112 '
                'C150 132 160 144 177 144 C194 144 204 132 204 112 Z')
    else:
        # Raised visual centre and a wider counter avoid a heavy descending footprint.
        body = ('M24 164 V56 H56 V72 C66 57 80 50 98 50 C117 50 130 58 140 72 '
                'C150 57 165 50 183 50 C215 50 236 72 236 106 V162 '
                'C236 201 213 224 175 224 H138 V194 H173 C194 194 205 184 205 166 V156 '
                'C196 166 185 170 171 170 C146 170 126 159 116 142 '
                'V102 C116 87 108 80 94 80 C71 80 56 97 56 117 V164 H24 Z '
                'M205 110 C205 91 195 79 178 79 C160 79 149 91 149 110 '
                'C149 130 160 142 178 142 C195 142 205 130 205 110 Z')
    return path(body)


concepts = [
    ('a-open-clause', 'Open Clause', open_clause(), 'PublicSans-SemiBold.ttf'),
    ('b-peoples-quote', "People’s Quote", peoples_quote(), 'PublicSans-SemiBold.ttf'),
    ('c-shared-initials', 'Shared Initials', shared_initials(), 'SourceSerif4-Semibold.ttf'),
]

for key, name, symbol, font in concepts:
    base = ROOT / 'concepts' / f'{key}-v{VERSION}'
    base.with_name(base.name+'-symbol.svg').write_text(svg(f'constitution.ng — {name} concept', symbol))
    word, right = outline_word(font, 284 if VERSION == 1 else 220, 168, size=142, tracking=-1.5)
    lockup = f'<g id="symbol" transform="translate(8 32) scale(.75)">{symbol}</g><g id="wordmark">{word}</g>'
    base.with_name(base.name+'-lockup.svg').write_text(svg(f'constitution.ng — {name} wordmark concept', lockup, right+28))
    print(base.name)
