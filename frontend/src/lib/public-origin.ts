import { siteOrigin } from "./seo"

// Cloudflare builds always set VITE_PUBLIC_SITE_URL (deployment/cloudflare/build.sh
// refuses to run without it). The fallback only serves local development.
export const publicOrigin = siteOrigin(
  import.meta.env.VITE_PUBLIC_SITE_URL ?? "https://constitution.ng",
)
