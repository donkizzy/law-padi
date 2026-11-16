// The specs that talk to the real backend, database and mail catcher. Every
// other spec stubs its API calls with `page.route` and runs through
// `playwright.mocked.config.ts`, which needs no backend. `playwright.config.ts`
// runs only these, so each spec belongs to exactly one configuration.
export const backendSpecs = /(?:login|sign-up|reset-password)\.spec\.ts$/
