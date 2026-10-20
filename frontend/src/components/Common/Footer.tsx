import { useTranslation } from "react-i18next"

export function Footer() {
  const { t } = useTranslation()
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t py-4 px-6">
      <p className="text-center text-muted-foreground text-sm sm:text-left">
        constitution.ng · {t("footer.tagline")} · {currentYear}
      </p>
    </footer>
  )
}
