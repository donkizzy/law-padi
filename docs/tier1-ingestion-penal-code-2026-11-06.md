# Penal Code Act (FCT, Abuja): review report (6 November 2026)

Approved by the user on 6 November 2026. Source verified, corrected text materialised and embedded (Recall@10 1.0 on benchmark v2), and included in `composite-2026-11-06-twenty-laws`, composed onto the published nineteen-law release.

| Item | Value |
|---|---|
| Instrument | `penal-code-act-abuja`, Penal Code Act, Chapter 532, Laws of the Federal Capital Territory, Abuja (the copy's cover says Chapter 53, its body Chapter 532) |
| Source | Retyped copy in the ILGA database, circulated by the jewngr blog, `trusted_secondary`, status `needs_review` |
| Run | `b3f0bc13-6403-4e1f-9d03-9cfd74cff395`, ready to publish, parser `act-hierarchy-v3` |
| Pages | 24-149 included; arrangement (1-23) and web navigation (150) excluded |
| Check source | S. S. Richardson, *Notes on the Penal Code Law, 1959*, 2nd edition, 1963, used as a wording check only. None of its text was copied into the Act. |

## Reconciliation

394 Code sections and 6 enabling sections, none missing, unexpected or repeated against the catalogue. The catalogue leaves out the numbers this copy does not hold.

## What is missing

- **ss.197-212:** the rest of Public Nuisance, Lotteries and Gaming Houses, Cruelty to Animals and most of Offences relating to Religion. Chapters XIV and XV are lost entirely.
- **ss.364-365:** the punishment for forgery and forgery of public seals.
- **ss.410-477:** the copy refers these to the Penal Code (Northern States) Federal Provisions Act.
- **s.384(1):** the end of the subsection, with the penalty, is lost. It was not filled from the 1963 Code.

Gap notices sit on ss.196, 213, 363, 366, 384 and 409. Their Pidgin, Yoruba, Hausa and Igbo strings are unreviewed drafts.

## Review counts

- Approved 655. Rejected 12: illustrations parsed as paragraphs. The section text keeps them.
- Revised 200. Issues: all resolved. No override used.
- Chapter numbers XVI, XXI and XXV were added before parsing, because the copy lost them; its own arrangement gives them. Chapter XXII's title comes from its body heading.

## Corrections

- Margin notes run into the wording, removed: for example "of which Judicial it is" in s.9, "or to Likely, cause" in s.19, "this Invalid Penal" in s.39.
- s.346 opening rebuilt: `¥34.`, `c°m.mit`, `hIS`, and stray specks at line ends through ss.345-354.
- Misreads such as `peiform`, `canoy`, `hasvoluntarily`, `mayor may`, `Band C`.
- A line-by-line read after the first materialisation found more: s.59 `all offence`, s.195 `with me`, s.288 `seven or` (now `seven years or`), s.183 `came injury`. Words restored from parallel wording or the 1963 Code include s.18 `believe` and s.163 `in a`.
- s.74 table rebuilt row by row. The row order follows the eight-row scale in the 1963 Code; the amounts are this copy's.

## Limits of the check

This is the weakest law in the corpus.

- **No printed page:** this is a retyped copy with no images, so nothing could be checked against a page.
- **Penalties:** naira amounts and prison terms could not be verified. The 1963 Code is in pounds, and some terms have changed since: s.113 is three years here and one in 1963, s.407 two years here and one in 1963. A rough comparison flagged 21 sections with different prison terms. Five were read side by side, and many of the 21 are extraction noise. The rest are unread. The Abuja figures are kept.
- **Not current law:** this is not a checked consolidation. Amendments after this copy are not folded in, and it is marked historical. The Violence Against Persons (Prohibition) Act 2015 and later Acts affect parts of it in the FCT.
- **Line-by-line read:** the full Act was read once. It could still miss errors that read naturally, because no printed page of this Act exists to compare.

## Provision identity

Historical text cannot be replaced in place, so the corrected text sits under `penal-code-act-abuja.code`. The first import's uncorrected provisions remain in the database, in no release, and cannot be removed through the services.

## Retrieval

- First embedding: Recall@10 0.914 against the uncorrected text. Three fair questions missed, on ss.51, 59 and 384, so "In plain words" phrasing was added. No benchmark question was edited.
- `penal-code-abuja-retrieval-v1` pointed at the old provisions. It was retired with the new `--supersede` option of `scripts/load_retrieval_benchmark.py`, on the user's instruction. Its rows are kept.
- Corrected text with phrasing: Recall@10 1.0.

Benchmark: `docs/penal-code-abuja-retrieval-benchmark.json` (35 questions, version v2).
