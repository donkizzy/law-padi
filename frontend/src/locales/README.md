# Interface catalogues

User-facing interface text for constitution.ng, one folder per language and one
JSON file per namespace.

| Folder | Language          | Status                                        |
| ------ | ----------------- | --------------------------------------------- |
| `en`   | English           | Source text. Default and fallback.            |
| `pcm`  | Nigerian Pidgin   | **Draft.** Not reviewed by a native speaker.  |
| `yo`   | Yorùbá            | **Draft.** Not reviewed by a native speaker.  |
| `ha`   | Hausa             | **Draft.** Not reviewed by a native speaker.  |
| `ig`   | Igbo              | **Draft.** Not reviewed by a native speaker.  |

The `pcm`, `yo`, `ha` and `ig` catalogues were drafted without native reviewers.
Treat every string as a draft until a fluent reviewer has signed it off, and
record the review here (reviewer, date, namespaces covered) when it happens.

## How catalogues are used

- `en` is bundled with the app. Every other language is loaded one namespace file
  at a time when that language is chosen (`src/lib/i18n.ts`).
- The language picker (header and Settings) only offers a language whose
  catalogues are **complete**: every English key exists, is non-empty, and keeps
  the same `{{placeholders}}` and `<tags>`. `vite.config.ts` checks this at build
  and dev time and warns with the first gaps it finds.
- English keys are typed (`src/i18next.d.ts`), so a component can't use a key
  that `en` doesn't define.
- `en/landing.json` (FAQ), `en/edition.json` and `en/pages.json` are also the
  English source for the Cloudflare Worker pages, which stay English in v1.

## Namespaces

| File           | Covers                                                        |
| -------------- | ------------------------------------------------------------- |
| `common.json`  | Header, sidebar, shared buttons, errors, form validation       |
| `landing.json` | `/welcome` landing page and its FAQ                            |
| `chat.json`    | Ask and Find: chat home, composer, answers, search results     |
| `legal.json`   | Browse, provision pages, source panels, saved sections         |
| `edition.json` | Edition names and caveats from `lib/legal-provisions.ts`       |
| `settings.json`| Settings page and account forms                                |
| `auth.json`    | Log in, sign up, password recovery and email confirmation      |
| `privacy.json` | Privacy notice                                                 |
| `pages.json`   | About and methodology pages                                    |

## Rules for translators

- Official constitutional and statutory wording is never translated here. It is
  shown in English with `lang="en"`. Keep "English" where a string says the
  official text is English.
- Keep references such as `Section 37`, `ACJA s.9`, Act titles, `constitution.ng`
  and company names (DeepSeek, Cloudflare, Render, Neon) as they are. Search and
  citation parsing expect `Section` in English.
- Keep every `{{placeholder}}` and `<tag>…</tag>` exactly; translate only the text
  around and inside them.
- Plural keys come in pairs (`_one`, `_other`). Provide both even if the language
  doesn't distinguish them.
- Follow the product voice: answer-first, plain and calm. Never mention "AI" or
  describe answers as machine-generated.
- To hide a language while it is being revised, leave a key out: the picker drops
  it until the catalogue is complete again.
