import { completeLanguages } from "virtual:locale-manifest"
import i18n, { type BackendModule, type ResourceKey } from "i18next"
import { initReactI18next } from "react-i18next"

import { readPreferences } from "@/hooks/useWorkspacePreferences"
import type { LanguageValue } from "@/lib/languages"
import { setEditionTranslator } from "@/lib/legal-provisions"
import { workspaceStorageEvent } from "@/lib/storage-keys"

export const namespaces = [
  "common",
  "landing",
  "chat",
  "legal",
  "edition",
  "settings",
  "auth",
  "privacy",
  "pages",
] as const

/** Preference values mapped to BCP 47 codes. `auto` follows the device. */
export const languageCodes: Record<Exclude<LanguageValue, "auto">, string> = {
  english: "en",
  pidgin: "pcm",
  yoruba: "yo",
  igbo: "ig",
  hausa: "ha",
}

// English ships with the app: it is the default and the fallback for any gap.
const english = import.meta.glob<ResourceKey>("../locales/en/*.json", {
  eager: true,
  import: "default",
})
// Every other language loads one namespace file at a time, on first use.
const catalogues = import.meta.glob<ResourceKey>(
  ["../locales/*/*.json", "!../locales/en/*.json"],
  { import: "default" },
)

const lazyCatalogues: BackendModule = {
  type: "backend",
  init: () => undefined,
  read(language, namespace, callback) {
    const load = catalogues[`../locales/${language}/${namespace}.json`]
    if (!load) return callback(null, {})
    load().then(
      (resources) => callback(null, resources),
      (error) => callback(error, null),
    )
  },
}

/** Whether the picker may offer a language: drafts must be complete. */
export function isLanguageAvailable(value: LanguageValue) {
  return value === "auto" || completeLanguages.includes(languageCodes[value])
}

/** The catalogue to show for a saved preference. */
export function resolveLanguage(value: LanguageValue) {
  if (value !== "auto")
    return isLanguageAvailable(value) ? languageCodes[value] : "en"
  for (const tag of navigator.languages ?? [navigator.language]) {
    const code = tag.toLowerCase().split("-")[0]
    if (completeLanguages.includes(code)) return code
  }
  return "en"
}

/** Locales for Intl formatting, falling back to Nigerian English. */
export function intlLocales(language = i18n.resolvedLanguage ?? "en") {
  return [`${language}-NG`, language, "en-NG"]
}

i18n.on("languageChanged", (language) => {
  document.documentElement.lang = language
})

function followPreference() {
  const language = resolveLanguage(readPreferences().language)
  if (language !== i18n.language) void i18n.changeLanguage(language)
}

/** Load the chosen language before first render, then follow later changes. */
export async function initI18n() {
  const resources = Object.fromEntries(
    Object.entries(english).map(([file, catalogue]) => [
      file.replace(/^.*\/(\w+)\.json$/, "$1"),
      catalogue,
    ]),
  )
  await i18n
    .use(lazyCatalogues)
    .use(initReactI18next)
    .init({
      lng: resolveLanguage(readPreferences().language),
      fallbackLng: "en",
      supportedLngs: Object.values(languageCodes),
      ns: namespaces,
      defaultNS: "common",
      resources: { en: resources },
      partialBundledLanguages: true,
      interpolation: { escapeValue: false },
      // Every namespace for the language is loaded before it is shown.
      react: { useSuspense: false },
    })
  setEditionTranslator((key, values) =>
    String(i18n.t(`edition:${key}` as never, values as never)),
  )
  document.documentElement.lang = i18n.language
  window.addEventListener("storage", followPreference)
  window.addEventListener(workspaceStorageEvent, followPreference)
}

export default i18n
