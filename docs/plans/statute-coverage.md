# Statute coverage plan: Tiers 2 to 4

Which laws to add after the first set of statutes, written on 4 November 2026.
The currency notes were drafted from general knowledge and must be checked
against the National Assembly or the Federal Ministry of Justice before
ingestion; Nigeria passed several replacement Acts in 2025 and 2026.

Covering all Nigerian law (hundreds of Acts plus 36 states) is not achievable at
once. The target is the laws people ask about most, with everything else
labelled "not yet covered" in the interface. Every Act keeps the "As enacted,
may have been amended" label.

Selection rule: prefer born-digital sources (National Assembly, agency or
gazette text PDFs) over scans. OCR cost and misread section numbers (`48` read
as `4g`) are what slowed the ACJA and the Police Act.

Progress since the plan was written is visible in the code rather than here:
a law that has reached review has a section-title catalogue in
`backend/app/legal/data/`, and a law that has a retrieval benchmark has a file in
`eval/datasets/`. Whether a law is in the production release is recorded in the
production database, not in this repository.

## Tier 2: business, money and family

| # | Law | Notes for the source search |
|---|-----|-----------------------------|
| 11 | Companies and Allied Matters Act (CAMA) 2020 | Large. One mirrored page (91) in the tested source. |
| 12 | Tax laws: Nigeria Tax Act 2025, Nigeria Tax Administration Act 2025, and the revenue-body Acts effective 1 January 2026 | They replaced the old CITA, PITA, VAT and CGT Acts, so **do not ingest the old ones**. The Tax Act amends the Cybercrimes Act (s.196(14)) and repeals other Acts; record each cross-law effect. |
| 13 | Pension Reform Act 2014 | |
| 14 | Matrimonial Causes Act and Marriage Act | Cap M7 and M6 LFN 2004. Both are 2004 compilations. |
| 15 | Freedom of Information Act 2011 | |
| 16 | Money Laundering (Prevention and Prohibition) Act 2022 and Terrorism (Prevention and Prohibition) Act 2022 | Two separate Acts. |
| 17 | Electoral Act | Believed to have been replaced in 2026. Confirm which Act is current before sourcing; Electoral Act 2022 may now be historical. |
| 18 | Banks and Other Financial Institutions Act (BOFIA) 2020 and Investments and Securities Act 2025 | Two separate Acts. |

## Tier 3: specialist and procedural

| # | Law | Notes |
|---|-----|-------|
| 19 | Immigration Act 2015 | |
| 20 | Copyright Act 2022, Trade Marks Act, Patents and Designs Act | Section 106(2) of the Copyright Act repeals Criminal Code sections 491-493 and Penal Code sections 426-427. |
| 21 | Arbitration and Mediation Act 2023 | |
| 22 | Sheriffs and Civil Process Act, Legal Practitioners Act, Federal High Court (Civil Procedure) Rules | Rules are court instruments, not Acts. |
| 23 | EFCC Act 2004, ICPC Act 2000, Public Procurement Act 2007 | |
| 24 | Petroleum Industry Act 2021, Electricity Act 2023 | |
| 25 | Firearms Act, Armed Forces Act, Anti-Torture Act 2017, Discrimination Against Persons with Disabilities Act 2018 | |

## Tier 4: later

| # | Item | Notes |
|---|------|-------|
| 26 | Constitution alteration Acts | Our Constitution text is as enacted. Folding in the alterations gives "the law as it is today" and is hard. |
| 27 | State laws | Most useful first: Lagos (Tenancy Law 2011, Criminal Law 2011, Land laws), then Abuja and other large states. |
| 28 | Case law | A separate and much larger project. |

## UI honesty rules

- Say plainly what is not covered: state laws and case law are out of scope for now.
- Nothing is "current consolidated law" unless checked against the latest amendments.
- Tax law: only the 2025 Acts, never the old CITA, PITA, VAT or CGT Acts.
