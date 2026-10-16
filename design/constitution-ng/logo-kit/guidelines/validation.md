# Export validation

Completed on 12 October 2026.

- Parsed all 19 logo/web SVG artworks. Confirmed valid viewBoxes and absence of live text, raster images, filters, masks, clipping paths and strokes. The symbol uses three closed circular segments within one compound path; its gaps are transparent.
- Inspected the regular and small symbols, the optically thinned white mark, the horizontal/stacked/wordmark layouts, the final overview and one-page guide.
- Rendered and inspected each of the five presentation slides. Six application contexts are shown: website, browser tab, mobile icon, social profile, source-sharing card and civic guide cover. Mockup copy is illustrative.
- Inspected final artwork at its documented screen minima: horizontal 240 px, stacked 200 px, wordmark 180 px, regular symbol 24 px and small symbol/favicon 16 px. Inspected actual 16/24/32 px favicon exports at enlarged nearest-neighbour scale; the central split stays open.
- Verified transparent alpha in all logo PNGs. Backgrounds are intentionally opaque in the PWA/touch assets.
- Verified the 16/24/32/48/64 px favicon PNG dimensions and the ICO's separate 16, 32 and 48 px frames.
- Verified all manifest icon references exist and match their declared dimensions. Confirmed the maskable symbol stays within the circular 80% safe zone.
- Computed green/white contrast at 4.58:1 using linearised sRGB luminance.

The symbol and small symbol score 100/100 in the bundled structural audit. Horizontal layouts score 98 and wordmark-only layouts 99. The stacked logo triggers heuristic complexity/tiny-detail warnings because it contains a long outlined name: it is documented for 200 px and above, with separate symbol files for small applications. The scores do not establish trademark distinctiveness or print certification.

Earlier concept tests included mirrored/rotated views, blur, backgrounds and peer comparison. The selected design preserves that form, with optical centring, reversed weight and small-size refinements.

No application code, dependencies, lockfiles or deployment settings were changed for this identity kit. No application build or test suite was needed. Print colours are approximate and need a physical proof; no Pantone equivalence, domain ownership or trademark clearance is asserted.
