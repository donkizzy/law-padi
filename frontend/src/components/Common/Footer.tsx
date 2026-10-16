export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t py-4 px-6">
      <p className="text-center text-muted-foreground text-sm sm:text-left">
        constitution.ng · Nigeria&apos;s Constitution in plain English ·{" "}
        {currentYear}
      </p>
    </footer>
  )
}
