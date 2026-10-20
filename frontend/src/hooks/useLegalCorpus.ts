import { useQuery } from "@tanstack/react-query"
import { AxiosError } from "axios"
import { LegalService } from "@/client"
import i18n from "@/lib/i18n"

export function useLegalRelease() {
  return useQuery({
    queryKey: ["legal", "release"],
    queryFn: async ({ signal }) =>
      (await LegalService.readCurrentRelease({ signal })).data,
    retry: false,
    staleTime: 30_000,
  })
}

export function useLegalInstruments(releaseVersion?: string) {
  return useQuery({
    queryKey: ["legal", "instruments", releaseVersion],
    queryFn: async ({ signal }) =>
      (
        await LegalService.readLegalInstruments({
          query: { release_version: releaseVersion },
          signal,
        })
      ).data,
    retry: false,
    staleTime: 30_000,
  })
}

export function useLegalSearch(
  query: string,
  mode: "auto" | "semantic" = "auto",
  attempt = 0,
  releaseVersion?: string,
  instrument?: string,
) {
  return useQuery({
    queryKey: [
      "legal",
      "search",
      query,
      mode,
      attempt,
      releaseVersion,
      instrument,
    ],
    queryFn: async ({ signal }) =>
      (
        await LegalService.searchLegal({
          body: {
            query,
            mode,
            top_k: 10,
            index_kind: "enacted",
            release_version: releaseVersion,
            instrument,
          },
          signal,
        })
      ).data,
    enabled: Boolean(query),
    retry: false,
  })
}

export function provisionQueryOptions(path: string, release?: string) {
  return {
    queryKey: ["legal", "provision", path, release],
    queryFn: async ({ signal }: { signal: AbortSignal }) =>
      (
        await LegalService.readCurrentProvision({
          path: { canonical_path: path },
          query: { release_version: release },
          signal,
        })
      ).data.data[0],
    staleTime: 30_000,
    retry: false as const,
  }
}

export function useProvision(path: string, release?: string) {
  return useQuery({
    ...provisionQueryOptions(path, release),
    enabled: Boolean(path),
  })
}

export function treeQueryOptions(
  parent?: string,
  release?: string,
  instrument?: string,
) {
  return {
    queryKey: ["legal", "tree", parent, release, instrument],
    queryFn: async ({ signal }: { signal: AbortSignal }) =>
      (
        await LegalService.readProvisionTree({
          query: { parent_path: parent, release_version: release, instrument },
          signal,
        })
      ).data,
    staleTime: 30_000,
    retry: false as const,
  }
}

export function useProvisionTree(
  parent?: string,
  release?: string,
  instrument?: string,
) {
  return useQuery(treeQueryOptions(parent, release, instrument))
}

export function useProvisionHistory(
  path: string,
  release: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["legal", "history", path, release],
    queryFn: async ({ signal }) =>
      (
        await LegalService.readProvisionHistory({
          query: { canonical_path: path, release_version: release },
          signal,
        })
      ).data,
    enabled,
    retry: false,
  })
}

export function legalError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response?.status === 404) return i18n.t("legalError.notFound")
    if (error.response?.status === 503) return i18n.t("legalError.unavailable")
  }
  return i18n.t("legalError.generic")
}
