import { existsSync, readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig, type Plugin } from "vite"

const localesDir = path.resolve(import.meta.dirname, "./src/locales")

/** Every string in a catalogue, keyed by its dotted path. */
function leaves(value: unknown, prefix = "", out = new Map<string, unknown>()) {
  if (value && typeof value === "object")
    for (const [key, child] of Object.entries(value))
      leaves(child, prefix ? `${prefix}.${key}` : key, out)
  else out.set(prefix, value)
  return out
}

/** Placeholders a translation must keep: {{values}} and <tags>. */
const placeholders = (text: string) =>
  [...text.matchAll(/\{\{\s*[\w.]+\s*\}\}|<\/?\w+\s*\/?>/g)]
    .map((match) => match[0].replace(/\s/g, ""))
    .sort()
    .join(" ")

/** Languages whose catalogues have every English string, with placeholders intact. */
function completeLanguages(log: (message: string) => void) {
  const namespaces = readdirSync(path.join(localesDir, "en")).filter((file) =>
    file.endsWith(".json"),
  )
  const english = new Map(
    namespaces.map((file) => [
      file,
      leaves(
        JSON.parse(readFileSync(path.join(localesDir, "en", file), "utf8")),
      ),
    ]),
  )
  const languages = readdirSync(localesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name !== "en")
    .map((entry) => entry.name)
  return languages.filter((language) => {
    const gaps: string[] = []
    for (const [file, source] of english) {
      const target = path.join(localesDir, language, file)
      if (!existsSync(target)) {
        gaps.push(`${file} is missing`)
        continue
      }
      let translated: Map<string, unknown>
      try {
        translated = leaves(JSON.parse(readFileSync(target, "utf8")))
      } catch {
        gaps.push(`${file} is not valid JSON`)
        continue
      }
      for (const [key, text] of source) {
        const value = translated.get(key)
        if (typeof value !== "string" || !value.trim())
          gaps.push(`${file}: ${key}`)
        else if (placeholders(value) !== placeholders(String(text)))
          gaps.push(`${file}: ${key} (placeholders differ)`)
      }
    }
    if (gaps.length)
      log(
        `[locales] ${language} is hidden from the language picker until it is complete (${gaps.length} gaps, first: ${gaps.slice(0, 3).join("; ")})`,
      )
    return gaps.length === 0
  })
}

/** `virtual:locale-manifest` lists the languages the picker may offer. */
function localeManifest(): Plugin {
  const id = "virtual:locale-manifest"
  return {
    name: "locale-manifest",
    resolveId: (source) => (source === id ? `\0${id}` : undefined),
    load(source) {
      if (source !== `\0${id}`) return
      for (const entry of readdirSync(localesDir, { recursive: true }))
        if (String(entry).endsWith(".json"))
          this.addWatchFile(path.join(localesDir, String(entry)))
      const complete = completeLanguages((message) => this.warn(message))
      return `export const completeLanguages = ${JSON.stringify(["en", ...complete])}`
    },
    configureServer(server) {
      // New, edited or deleted catalogues can change which languages are complete.
      const refresh = (file: string) => {
        if (!file.startsWith(localesDir)) return
        const module = server.moduleGraph.getModuleById(`\0${id}`)
        if (module) server.moduleGraph.invalidateModule(module)
      }
      for (const event of ["add", "change", "unlink"] as const)
        server.watcher.on(event, refresh)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    outDir: "../backend/app/frontend",
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    localeManifest(),
    react(),
    tailwindcss(),
  ],
})
