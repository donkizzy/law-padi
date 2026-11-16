# JRB citation and reader fixes

5 November 2026, Africa/Lagos. The user authorised two scoped application fixes and focused regression tests after source and page-scope approval. This authorisation applies to the code and tests. The wording and publication decisions remain separate.

- The citation registry now recognises the full statutory title, the short title emitted by the app and “JRB Act”. A qualified reference to JRB Section 41 matches the JRB path. A wrong year or an unknown parenthesised Act name returns an explicit reference error in the tested citation forms. The English error copy reflects the updated recognition rules. The publication gate still determines whether a recognised Act has public content.
- The reader formatter preserves blank lines separating definitions or other paragraphs, while joining single source line wraps. Numbered paragraphs and provisos retain their breaks. The formatter lives in a module that the regression tests can load independently of browser or locale setup. The existing reader imports still use the same formatter through the original module.

## Verification

The citation suite passed 74 cases in the existing Python runtime, loading only the changed workspace modules in a temporary test process. Pytest used `--noconftest` because the repository fixtures reset a test database. The run used an unused loopback DSN and made no database connection. Ruff lint and format checks passed on the three changed Python files.

Both reader regression cases passed using the Playwright runner without browser fixtures or project setup. The actual JRB Section 60 working draft retained all 12 definition breaks in a direct formatter probe. The frontend TypeScript check and Biome checks on the four changed files passed. The initial tests exposed a comma-delimited unknown title and a locale JSON import that the standalone test runner could not load. The final checks cover the corrected paths.

## Ingestion checkpoint

The fixes are in the workspace. The running Compose image still needs the updated code for the eventual live release checks. This pass left the local services and database alone. Natural-language schedule citation parsing was outside the approved section-lookup fix. Canonical-path schedule checks remain part of release validation.

The [approved source and page scope](round5-ingestion-jrb-source-scope-2026-11-05-v2.md) and [wording checkpoint](round5-ingestion-jrb-checkpoint-2026-11-05-v3.json) remain the basis for the next work. Finish collation of the 31 included pages, reconcile the complete candidate graph and the 15 open blockers, and present a separate wording packet bound to live review versions. Live runtime and release checks are due before promotion.
