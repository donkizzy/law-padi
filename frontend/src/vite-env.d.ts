/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_PUBLIC_SITE_URL?: string
  /** Shown on the privacy page when set. */
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module "virtual:locale-manifest" {
  /** Language codes whose catalogues are complete, English first. */
  export const completeLanguages: string[]
}
