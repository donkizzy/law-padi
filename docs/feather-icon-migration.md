# Feather icon migration

Reviewed application icons on 17 October 2026. Feather icons are supplied by
the existing `react-icons/fi` package entry point; no dependency changes are needed.
Catalogue reference: [Feather](https://feathericons.com/).

## Completed replacements

| Previous icon | Feather icon | UI location |
| --- | --- | --- |
| `LiaArchiveSolid` | `FiArchive` | Historical legal-status badges in `frontend/src/lib/law-padi-data.ts` |
| `LiaCircleNotchSolid` | `FiLoader` (static) | Proposed legal-status badges in `frontend/src/lib/law-padi-data.ts` |
| `LiaCalendarAltSolid` | `FiCalendar` | Amendment year in `frontend/src/components/LawPadi/AmendmentsView.tsx` |
| `LiaDatabaseSolid` | `FiDatabase` | Admin workspace → Production metric |
| `LiaShieldAltSolid` | `FiShield` | Sidebar → Legal admin; admin workspace → Queue depth metric |

Other application UI icons already use Feather, including navigation, chat,
settings, authentication, tables, dialogs, and toast notifications.

## Awaiting replacement direction

These five Line Awesome icons remain in place because Feather has no close
visual equivalent. The suggestions below change the visual metaphor and have
not been applied.

| Current icon | Where it appears | Source | Possible Feather alternative |
| --- | --- | --- | --- |
| `LiaBalanceScaleSolid` (balance scales) | Saved provisions → “Nothing saved yet” and “Nothing matches that search” empty states | `frontend/src/components/LawPadi/primitives.tsx`, shared `EmptyState`; used by `frontend/src/components/LawPadi/SavedProvisions.tsx` | `FiBookOpen` for legal content, or `FiBookmark` for saved content |
| `LiaGavelSolid` (gavel) | Amendment cards → legislative stage label | `frontend/src/components/LawPadi/AmendmentsView.tsx`, `AmendmentSection` | `FiFlag` for a stage/milestone |
| `LiaFileContractSolid` (contract document) | Admin workspace → Active runs metric | `frontend/src/components/LawPadi/AdminWorkspace.tsx` | `FiActivity` for processing, or `FiFileText` for a source document |
| `LiaClipboardCheckSolid` (clipboard with checkmark) | Admin workspace → Review issues metric | `frontend/src/components/LawPadi/AdminWorkspace.tsx` | `FiClipboard` for review, or `FiCheckSquare` for a check |
| `LiaFlaskSolid` (flask) | Admin workspace → Embedding metric | `frontend/src/components/LawPadi/AdminWorkspace.tsx` | `FiCpu` for computation, or `FiActivity` for progress |

The constitution.ng logo/symbol (`frontend/src/components/Common/Logo.tsx`)
and favicon/home-screen assets in `frontend/public/` are custom brand artwork
and remain unchanged. Admin source-page images are document previews.

## Validation

- Frontend TypeScript check and production build passed (`bun run --filter frontend build`).
- Biome check passed for all four changed source files, run from `frontend/`.
