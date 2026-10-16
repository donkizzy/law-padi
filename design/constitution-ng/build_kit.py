"""Rebuild the selected Open Clause kit from geometry and the saved outlined wordmark.

Uses only Python's standard library; SVG/PNG exports use the logo-design skill tools.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'logo-kit'
GREEN = '#008751'
INK = '#172B23'
WHITE = '#FFFFFF'
NS = '{http://www.w3.org/2000/svg}'
for folder in ['svg', 'png', 'web', 'guidelines', 'presentation/slides', 'licenses']:
    (KIT / folder).mkdir(parents=True, exist_ok=True)


def mark(small=False, reverse=False):
    """Three true circular segments, a transparent vertical split, exact 45-degree ends."""
    cx, cy = 144, 128
    outer = 112 if small else 104
    inner = (66 if reverse else 64) if small else (63.5 if reverse else 62)
    left, right = (128, 160) if small else ((123.25, 160.75) if reverse else (124, 160))
    def y(radius, x, upper=True):
        return cy + (-1 if upper else 1) * math.sqrt(radius**2 - (x-cx)**2)
    def p(x, yy):
        return f'{x:.2f} {yy:.2f}'
    ox, oy = cx+outer/math.sqrt(2), cy-outer/math.sqrt(2)
    ix, iy = cx+inner/math.sqrt(2), cy-inner/math.sqrt(2)
    d = (f'M{p(left,y(outer,left))} A{outer} {outer} 0 0 0 {p(left,y(outer,left,False))} '
         f'L{p(left,y(inner,left,False))} A{inner} {inner} 0 0 1 {p(left,y(inner,left))} Z '
         f'M{p(right,y(outer,right))} A{outer} {outer} 0 0 1 {p(ox,oy)} '
         f'L{p(ix,iy)} A{inner} {inner} 0 0 0 {p(right,y(inner,right))} Z '
         f'M{p(right,y(inner,right,False))} A{inner} {inner} 0 0 0 {p(ix,256-iy)} '
         f'L{p(ox,256-oy)} A{outer} {outer} 0 0 1 {p(right,y(outer,right,False))} Z')
    return f'<path d="{d}"/>'


def document(title, body, w=256, h=256):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="logo-title">\n<title id="logo-title">{escape(title)}</title>\n'
            f'{body}\n</svg>\n')


source = ET.parse(ROOT/'concepts/a-open-clause-v2-lockup.svg')
word_d = source.find(f'.//{NS}g[@id="wordmark"]/{NS}path').attrib['d']
word = f'<path d="{word_d}"/>'


def logo(layout, colour, reverse=False):
    symbol = mark(small=layout == 'symbol-small', reverse=reverse)
    if layout in ('symbol', 'symbol-small'):
        body, w = f'<g fill="{colour}">{symbol}</g>', 256
    elif layout == 'horizontal':
        body = (f'<g id="symbol" fill="{colour}" transform="translate(8 32) scale(.75)">{symbol}</g>'
                f'<g id="wordmark" fill="{colour}">{word}</g>')
        w = 1242
    elif layout == 'wordmark':
        body, w = f'<g fill="{colour}" transform="translate(-192 0)">{word}</g>', 1050
    elif layout == 'stacked':
        body = (f'<g id="symbol" fill="{colour}" transform="translate(35.84 -3) scale(.72)">{symbol}</g>'
                f'<g id="wordmark" fill="{colour}" transform="translate(-36.36 180) scale(.225)">{word}</g>')
        w = 256
    else:
        raise ValueError(layout)
    return document(f'constitution.ng — {layout.replace("-", " ")} logo', body, w)


for layout in ('symbol','symbol-small','horizontal','stacked','wordmark'):
    for name, colour in [('green', GREEN), ('black','#000000'), ('white', WHITE)]:
        (KIT/'svg'/f'constitution-ng-{layout}-{name}.svg').write_text(logo(layout, colour, reverse=name=='white'))


def tile(kind):
    favicon = kind == 'favicon'
    scale = 1 if favicon else (.68 if kind == 'maskable' else .8)
    offset = (256-256*scale)/2
    radius = 48 if favicon else (56 if kind == 'app-preview' else 0)
    return document('constitution.ng',
        f'<rect width="256" height="256" rx="{radius}" fill="{GREEN}"/>'
        f'<g fill="{WHITE}" transform="translate({offset:g} {offset:g}) scale({scale:g})">'
        f'{mark(small=favicon,reverse=True)}</g>')


for filename, kind in [('favicon.svg','favicon'), ('app-icon.svg','app-preview'),
                       ('icon-square.svg','app'),('maskable.svg','maskable')]:
    (KIT/'web'/filename).write_text(tile(kind))

manifest = {
    'name':'constitution.ng', 'short_name':'constitution.ng', 'id':'/', 'start_url':'/', 'scope':'/',
    'display':'standalone', 'background_color':WHITE, 'theme_color':GREEN,
    'icons': [
        {'src':'./icon-192.png','sizes':'192x192','type':'image/png','purpose':'any'},
        {'src':'./icon-512.png','sizes':'512x512','type':'image/png','purpose':'any'},
        {'src':'./maskable-512.png','sizes':'512x512','type':'image/png','purpose':'maskable'},
    ]
}
(KIT/'web/site.webmanifest').write_text(json.dumps(manifest,indent=2)+'\n')
(KIT/'web/head-snippet.html').write_text('''<!-- Copy the web folder contents to the site root, or adjust these paths. -->
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#008751">
''')

spec = {
    'brand':'constitution.ng', 'date':'2026-10-12', 'deck_title':'Open Clause identity',
    'tagline':'Your Constitution, within reach.',
    'brief':'A welcoming identity for everyday Nigerians seeking clear explanations and traceable constitutional sources.',
    'adjectives':['Calm','Credible','Approachable','Nigerian'],
    'criteria':'An open C, a clear white passage and a green-and-white palette. A compact symbol for small screens; the full name for first encounters.',
    'industry':'consumer-app', 'nav':['Ask','Browse','Saved'],
    'mockups':['website','favicon-tab','app-icon','social','sticker','readme'],
    'brand_color':GREEN, 'greyscale':False, 'final':True,
    'concepts':[{
        'name':'Open Clause',
        'symbol':'../svg/constitution-ng-symbol-green.svg',
        'lockup':'../svg/constitution-ng-horizontal-green.svg',
        'stacked':'../svg/constitution-ng-stacked-green.svg',
        'avatar':'../svg/constitution-ng-symbol-small-green.svg',
        'symbol_on_tile':'../svg/constitution-ng-symbol-white.svg',
        'symbol_on_dark':'../svg/constitution-ng-symbol-white.svg',
        'lockup_on_dark':'../svg/constitution-ng-horizontal-white.svg',
        'stacked_on_tile':'../svg/constitution-ng-stacked-white.svg',
        'stacked_on_dark':'../svg/constitution-ng-stacked-white.svg',
        'idea':'A C opens around a white passage: constitutional knowledge made accessible, with a Nigerian flag reference.',
        'rationale':['Circular geometry feels calm and approachable.','The white split remains a real opening in every variant.','Green and white establish the Nigerian identity.','Outlined lettering works without installed fonts.']
    }],
    'recommendation':'Use the green horizontal logo on white for the main identity, white on green or dark ink, and the dedicated tile for browser tabs.',
    'next_steps':['SVG and transparent PNG artwork supplied.','Web icons and a ready-to-copy manifest supplied.','See the usage guide for clear space and minimum sizes.','Application mockups illustrate the identity; they are not implemented product screens.']
}
(KIT/'presentation/spec.json').write_text(json.dumps(spec,indent=2)+'\n')

def luminance(h):
    s=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in s]
    return sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722)))
contrast = (luminance(WHITE)+.05)/(luminance(GREEN)+.05)
(KIT/'guidelines/palette.json').write_text(json.dumps({
    'green':{'hex':GREEN,'rgb':[0,135,81],'cmyk_estimate':[100,0,40,47]},
    'white':{'hex':WHITE,'rgb':[255,255,255],'cmyk_estimate':[0,0,0,0]},
    'ink':{'hex':INK,'rgb':[23,43,35],'cmyk_estimate':[47,0,19,83]},
    'green_white_contrast':round(contrast,2),
    'print_note':'CMYK values are mathematical approximations, not profile-converted press specifications. Match spot ink with a physical swatch; no Pantone match is asserted.'
},indent=2)+'\n')
print(f'Built 15 logo SVGs, 4 web SVGs, manifest, palette and presentation specification. Green/white contrast: {contrast:.2f}:1.')
