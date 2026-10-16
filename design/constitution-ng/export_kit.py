"""Render deliverables and build the presentation from the selected SVGs."""
from pathlib import Path
import base64
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
SKILL = Path('/Users/amosgodwin/.codex/skills/logo-design')
sys.path.insert(0, str(SKILL/'scripts'))
import render_png
from concept_sheet import embed

ROOT = Path(__file__).resolve().parent
KIT = ROOT/'logo-kit'

for src in (KIT/'svg').glob('*.svg'):
    vb = [float(n) for n in ET.parse(src).getroot().attrib['viewBox'].split()]
    w = 2400 if vb[2] > 256 else (64 if 'small' in src.name else 1024)
    h = round(w * vb[3] / vb[2])
    dst = KIT/'png'/src.with_suffix('.png').name
    assert render_png.render(str(src), str(dst), w, h), src

for src, filename, size in [
    ('favicon.svg','favicon-16.png',16),('favicon.svg','favicon-24.png',24),('favicon.svg','favicon-32.png',32),
    ('favicon.svg','favicon-48.png',48),('favicon.svg','favicon-64.png',64),
    ('icon-square.svg','apple-touch-icon.png',180),('icon-square.svg','icon-192.png',192),
    ('icon-square.svg','icon-512.png',512),('maskable.svg','maskable-512.png',512),
    ('app-icon.svg','app-icon-1024.png',1024),
]:
    assert render_png.render(str(KIT/'web'/src),str(KIT/'web'/filename),size,size)
render_png.write_ico([str(KIT/'web'/f'favicon-{s}.png') for s in (16,32,48)],str(KIT/'web/favicon.ico'))


def logo(filename, key, x, y, w, h):
    return embed(str(KIT/'svg'/filename),key,x,y,w,h)


font='font-family="Helvetica,Arial,sans-serif"'
def text(x,y,txt,size=20,colour='#172B23',weight=400):
    from xml.sax.saxutils import escape
    return f'<text x="{x}" y="{y}" {font} font-size="{size}" fill="{colour}" font-weight="{weight}">{escape(txt)}</text>'


parts=[
    '<rect width="1600" height="1160" fill="#F4F6F3"/>',
    text(64,61,'CONSTITUTION.NG / OPEN CLAUSE',17,'#426451',700),
    text(64,119,'A clear identity. A shared Constitution.',42,'#172B23',700),
    '<rect x="60" y="164" width="1080" height="276" rx="20" fill="#FFFFFF"/>',
    logo('constitution-ng-horizontal-green.svg','primary',86,182,1030,226),
    '<rect x="1164" y="164" width="376" height="276" rx="20" fill="#008751"/>',
    logo('constitution-ng-symbol-white.svg','hero-symbol',1242,178,220,220),
    text(1242,421,'THE OPEN CLAUSE',13,'#FFFFFF',700),
    '<rect x="60" y="464" width="728" height="230" rx="20" fill="#008751"/>',
    text(88,501,'WHITE ON GREEN',13,'#FFFFFF',700),
    logo('constitution-ng-horizontal-white.svg','reverse',86,517,676,153),
    '<rect x="812" y="464" width="728" height="230" rx="20" fill="#FFFFFF"/>',
    text(840,501,'ONE COLOUR',13,'#52665A',700),
    logo('constitution-ng-horizontal-black.svg','black',838,517,676,153),
    '<rect x="60" y="718" width="440" height="374" rx="20" fill="#FFFFFF"/>',
    text(88,757,'STACKED LAYOUT',13,'#52665A',700),
    logo('constitution-ng-stacked-green.svg','stacked',136,777,290,290),
    '<rect x="524" y="718" width="468" height="374" rx="20" fill="#FFFFFF"/>',
    text(552,757,'COLOUR PALETTE',13,'#52665A',700),
    '<rect x="552" y="790" width="126" height="106" rx="10" fill="#008751"/>',
    '<rect x="696" y="790" width="126" height="106" rx="10" fill="#FFFFFF" stroke="#DBE4DD"/>',
    '<rect x="840" y="790" width="124" height="106" rx="10" fill="#172B23"/>',
    text(552,925,'Green',17),text(696,925,'White',17),text(840,925,'Ink',17),
    text(552,952,'#008751',15,'#52665A'),text(696,952,'#FFFFFF',15,'#52665A'),text(840,952,'#172B23',15,'#52665A'),
    text(552,1002,'Green + white lead the identity.',18),
    text(552,1033,'Ink supports surrounding content.',18,'#52665A'),
    '<rect x="1016" y="718" width="524" height="374" rx="20" fill="#FFFFFF"/>',
    text(1044,757,'MADE FOR SMALL SCREENS',13,'#52665A',700),
]
for size,x in [(16,1044),(24,1100),(32,1164),(64,1240)]:
    # Use a raster at its exact device size, with a text label below.
    raw = (KIT/'web'/f'favicon-{size}.png').read_bytes()
    parts.append(f'<image x="{x}" y="{838-size}" width="{size}" height="{size}" href="data:image/png;base64,{base64.b64encode(raw).decode()}"/>')
    parts.append(text(x,868,str(size)+' px',13,'#52665A'))
parts += [embed(str(KIT/'web/app-icon.svg'),'app',1360,780,132,132),
          text(1044,959,'A stronger small-size cut.',20),
          text(1044,993,'A thinner white version.',20),
          text(1044,1034,'SVG masters + transparent PNGs.',17,'#52665A'),
          text(64,1132,'Selected direction A · Logo kit · 12 October 2026',15,'#52665A')]
overview = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1160">'+''.join(parts)+'</svg>'
(KIT/'identity-overview.svg').write_text(overview)
assert render_png.render(str(KIT/'identity-overview.svg'),str(KIT/'identity-overview.png'),1600,1160)

subprocess.run([sys.executable,str(SKILL/'scripts/presentation_board.py'),str(KIT/'presentation/spec.json'),
                '-o',str(KIT/'presentation/presentation.html')],check=True)
html_path = KIT/'presentation/presentation.html'
html = html_path.read_text()
html = html.replace('https://constitutionng.com','constitution.ng')
html = html.replace('@constitutionng ·','Nigerian Constitution guide ·')
favicon_uri = 'data:image/svg+xml;base64,'+base64.b64encode((KIT/'web/favicon.svg').read_bytes()).decode()
html = re.sub(r'(<div class="tab"><img class="[^"]*" src=")[^"]+("[^>]*>)',
              lambda m:m.group(1)+favicon_uri+m.group(2),html)
green_logo = 'data:image/svg+xml;base64,'+base64.b64encode((KIT/'svg/constitution-ng-horizontal-green.svg').read_bytes()).decode()
white_logo = 'data:image/svg+xml;base64,'+base64.b64encode((KIT/'svg/constitution-ng-horizontal-white.svg').read_bytes()).decode()
source_card = f'''<div class="m" style="background:#E7EEE8"><div style="background:white;border-radius:14px;padding:24px;width:300px;box-shadow:0 8px 22px #17332315"><img src="{green_logo}" style="width:170px"><div style="font-size:10px;letter-spacing:1px;color:#008751;margin-top:20px">SOURCE REFERENCE</div><b style="display:block;font-size:20px;margin:10px 0">Your source, in context.</b><div style="font-size:12px;color:#52665A">Exact wording. Clear references.</div><div style="height:5px;background:#E7EEE8;margin-top:18px"></div><div style="height:5px;background:#E7EEE8;width:75%;margin-top:8px"></div></div><span class="lbl">Source sharing card · illustrative</span></div>'''
cover = f'''<div class="m" style="background:#E4E9E3"><div style="width:178px;height:224px;padding:20px;background:#008751;color:white;box-shadow:12px 10px 0 #143D2420;display:flex;flex-direction:column"><img src="{white_logo}" style="width:138px"><div style="font-size:25px;line-height:1.13;margin-top:33px;font-weight:650">Know your<br>Constitution.</div><div style="font-size:11px;margin-top:auto">A guide for everyday questions.</div></div><span class="lbl">Civic education guide · illustrative</span></div>'''
# Replace the two template contexts with product-relevant civic materials.
html=re.sub(r'<div class="m" style="background:#e1e3e6">.*?<span class="lbl">Laptop sticker</span></div>',lambda _:source_card,html,flags=re.S)
html=re.sub(r'<div class="m" style="background:#e6e8eb">.*?<span class="lbl">GitHub README</span></div>',lambda _:cover,html,flags=re.S)
# Keep the final cover's wordmark clear of its heading.
html=html.replace('right:64px;top:50%;transform:translateY(-50%);width:520px;',
                  'left:64px;top:410px;transform:none;width:720px;')
html_path.write_text(html)
print('Exported logo PNGs, favicon/PWA assets, identity overview and five-slide presentation.')
