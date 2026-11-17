export function formatMetric(value?: number | null): string {
  if (typeof value !== "number") return "0"
  return new Intl.NumberFormat().format(value)
}

export function formatCurrency(value?: number | null): string {
  if (typeof value !== "number") return "Pending"
  return new Intl.NumberFormat("en", {
    currency: "USD",
    maximumFractionDigits: 2,
    style: "currency",
  }).format(value)
}

export function formatPercent(value?: number | null): string {
  if (typeof value !== "number") return "0%"
  return `${Math.round(value * 100)}%`
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "None"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Unknown"
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(date)
}

export function labelize(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

export function shortId(value: string): string {
  return value.slice(0, 8)
}
