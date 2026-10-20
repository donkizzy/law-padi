import "i18next"

import type auth from "./locales/en/auth.json"
import type chat from "./locales/en/chat.json"
import type common from "./locales/en/common.json"
import type edition from "./locales/en/edition.json"
import type landing from "./locales/en/landing.json"
import type legal from "./locales/en/legal.json"
import type pages from "./locales/en/pages.json"
import type privacy from "./locales/en/privacy.json"
import type settings from "./locales/en/settings.json"

// English catalogues define the keys every language must provide.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "common"
    resources: {
      auth: typeof auth
      chat: typeof chat
      common: typeof common
      edition: typeof edition
      landing: typeof landing
      legal: typeof legal
      pages: typeof pages
      privacy: typeof privacy
      settings: typeof settings
    }
  }
}
