export type LanguageValue =
  | "auto"
  | "english"
  | "pidgin"
  | "yoruba"
  | "igbo"
  | "hausa"

export const languageOptions: { label: string; value: LanguageValue }[] = [
  { label: "Auto", value: "auto" },
  { label: "English", value: "english" },
  { label: "Pidgin", value: "pidgin" },
  { label: "Yorùbá", value: "yoruba" },
  { label: "Igbo", value: "igbo" },
  { label: "Hausa", value: "hausa" },
]
