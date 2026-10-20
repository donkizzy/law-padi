import { useId } from "react"
import { useTranslation } from "react-i18next"
import { FiGlobe } from "react-icons/fi"

import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  readPreferences,
  savePreferences,
  useWorkspacePreferences,
} from "@/hooks/useWorkspacePreferences"
import { isLanguageAvailable, languageCodes } from "@/lib/i18n"
import { type LanguageValue, languageOptions } from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

/** The saved language and the languages whose catalogues are complete. */
export function useLanguagePreference() {
  const { t } = useTranslation()
  const { preferences } = useWorkspacePreferences()
  const options = languageOptions
    .filter((option) => isLanguageAvailable(option.value))
    .map((option) => ({
      ...option,
      label: option.value === "auto" ? t("language.auto") : option.label,
      lang: option.value === "auto" ? undefined : languageCodes[option.value],
    }))
  const value = isLanguageAvailable(preferences.language)
    ? preferences.language
    : "english"
  // Applied straight away; other preferences keep their saved values.
  const setLanguage = (language: LanguageValue) =>
    savePreferences({ ...readPreferences(), language })
  return { value, options, setLanguage }
}

/** Compact header control. */
export function LanguageMenu({ className }: { className?: string }) {
  const { t, i18n } = useTranslation()
  const { value, options, setLanguage } = useLanguagePreference()
  if (options.length <= 2) return null
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <SquircleButton
          aria-label={t("language.menuLabel", {
            language: options.find((option) => option.value === value)?.label,
          })}
          className={cn("min-w-10 gap-1.5 px-2", className)}
          data-testid="language-menu"
          size="sm"
          type="button"
          variant="ghost"
        >
          <FiGlobe aria-hidden className="size-4" />
          <span aria-hidden className="hidden text-label uppercase sm:inline">
            {i18n.resolvedLanguage}
          </span>
        </SquircleButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-48">
        <DropdownMenuLabel>{t("language.title")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={value}
          onValueChange={(next) => setLanguage(next as LanguageValue)}
        >
          {options.map((option) => (
            <DropdownMenuRadioItem
              key={option.value}
              lang={option.lang}
              value={option.value}
            >
              {option.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Full list for the Settings page. */
export function LanguageChoice() {
  const { t } = useTranslation()
  const { value, options, setLanguage } = useLanguagePreference()
  const name = useId()
  return (
    <fieldset className="grid gap-2">
      <legend className="sr-only">{t("language.title")}</legend>
      {options.map((option) => (
        <label
          className={cn(
            "sq-md flex min-h-11 cursor-pointer items-center gap-3 border px-3 py-2 text-body",
            "focus-within:ring-[3px] focus-within:ring-ring/25",
            value === option.value
              ? "border-primary/40 bg-accent text-accent-foreground"
              : "border-border hover:bg-secondary",
          )}
          key={option.value}
        >
          <input
            checked={value === option.value}
            className="accent-[color:var(--primary)]"
            name={name}
            onChange={() => setLanguage(option.value)}
            type="radio"
            value={option.value}
          />
          <span lang={option.lang}>{option.label}</span>
        </label>
      ))}
    </fieldset>
  )
}
