import { siteOrigin } from "./seo"
export const publicOrigin = siteOrigin(import.meta.env.VITE_PUBLIC_SITE_URL)
