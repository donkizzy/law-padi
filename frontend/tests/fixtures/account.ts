import type {
  PreferencesPublic,
  SavedProvisionPublic,
  UserPublic,
} from "../../src/client"

// Bodies of the account endpoints, typed against the generated client.

export function userPublic(overrides: Partial<UserPublic> = {}): UserPublic {
  return {
    id: "99999999-9999-4999-8999-999999999999",
    email: "reader@example.test",
    full_name: "Test Reader",
    is_active: true,
    is_superuser: false,
    created_at: "2026-10-01T00:00:00Z",
    email_verified_at: null,
    ...overrides,
  }
}

export function preferencesPublic(
  overrides: Partial<PreferencesPublic> = {},
): PreferencesPublic {
  return {
    enter_to_send: true,
    follow_latest: true,
    open_sources: false,
    language: null,
    ...overrides,
  }
}

export function savedProvision(
  overrides: Partial<SavedProvisionPublic> = {},
): SavedProvisionPublic {
  return {
    canonical_path: "constitution-1999.chapter4.section37",
    release_version: "published-test",
    saved_at: "2026-10-13T12:00:00Z",
    ...overrides,
  }
}
