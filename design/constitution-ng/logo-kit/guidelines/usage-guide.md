# constitution.ng — Open Clause

**Logo usage guide · 12 October 2026**

The open **C** identifies Constitution. Its vertical split gives the mark a green–white–green reference while suggesting access to shared constitutional knowledge.

## Choose the right file

| Use | Artwork | Minimum screen width |
|---|---|---:|
| Website header and first encounters | `constitution-ng-horizontal-green.svg` | 240 px |
| Square layout with the full name | `constitution-ng-stacked-green.svg` | 200 px |
| Name alone | `constitution-ng-wordmark-green.svg` | 180 px |
| Avatar or compact navigation | `constitution-ng-symbol-green.svg` | 24 px |
| Very small symbol | `constitution-ng-symbol-small-green.svg` | 16 px |
| Browser tab | `web/favicon.svg` or `web/favicon.ico` | 16 px |

For smaller spaces, switch from a full-name layout to the symbol. Print starting points: horizontal 45 mm wide; stacked 35 mm; standalone symbol 6 mm. Test the actual material and reproduction process.

## Space and backgrounds

Keep at least **one C stroke-width** clear around the visible artwork. The reference unit is 42 on the symbol's 256-unit drawing, approximately one fifth of its visible height. This margin scales with the logo; canvas padding may provide part of it.

Use green on white, white on green or dark ink, and black on white. The white symbol is slightly thinner to balance its appearance on dark surfaces. On photography, place the logo on a quiet white or green panel. The vertical split is transparent, so the background shows through.

## Colour

| Colour | HEX | RGB | Approx. CMYK |
|---|---|---|---|
| Constitution green | `#008751` | 0, 135, 81 | 100, 0, 40, 47 |
| White | `#FFFFFF` | 255, 255, 255 | 0, 0, 0, 0 |
| Supporting ink | `#172B23` | 23, 43, 35 | 47, 0, 19, 83 |

Green and white are the identity colours; ink is for surrounding content. The calculated green/white contrast is **4.58:1**. CMYK values are approximate arithmetic conversions, not colour-profile-specific press values. For spot-colour printing, match a physical swatch with the printer; no verified Pantone match is supplied. This palette is a brand choice, not an assertion of an official flag colour specification.

## Lettering and care

The wordmark is based on **Public Sans SemiBold**, with custom spacing and a square period. All logo letters are outlined: use the supplied artwork rather than retyping the name. Public Sans can support interface text; the project's Source Serif 4 can support longer reading and editorial headings. Public Sans's license notice is included.

Scale proportionally. Keep the established spacing, orientation and colours. Preserve the open split. Avoid shadows, gradients, outlines and added symbols. Use the dedicated small version rather than shrinking the stacked logo into an icon.

## Web assets

The `web/` folder contains favicons, Apple touch and PWA icons, a maskable icon, `site.webmanifest` and `head-snippet.html`. Copy its contents to the site root or adjust the paths. The manifest assumes deployment at `/`. The full square PWA assets let each platform apply its own shape; `app-icon.svg` is the rounded preview. The favicon has a green background for visibility in both light and dark browser tabs.

The artwork has been rendered and inspected. A professional trademark/resemblance search is recommended before launch; this kit does not establish trademark clearance or domain ownership. The presentation's example copy and product materials are illustrative.
