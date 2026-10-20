import type { IconType } from "react-icons"
import {
  FiAlertTriangle,
  FiArchive,
  FiBookmark,
  FiBookOpen,
  FiCheckCircle,
  FiClock,
  FiLoader,
  FiMessageSquare,
} from "react-icons/fi"

export type LegalStatus = "current" | "proposed" | "historical" | "warning"

export type LanguageValue =
  | "auto"
  | "english"
  | "pidgin"
  | "yoruba"
  | "igbo"
  | "hausa"

export type Provision = {
  id: string
  section: string
  title: string
  chapter: string
  topic: string
  status: LegalStatus
  summary: string
  officialText: string
  citation: string
  sourceTitle: string
  sourceAuthority: string
  sourcePage: string
  history: TimelineEvent[]
  related: string[]
}

export type Chapter = {
  id: string
  number: string
  title: string
  range: string
  description: string
  provisions: Provision[]
}

export type TimelineEvent = {
  marker: string
  title: string
  description: string
  status?: LegalStatus
}

export type Amendment = {
  id: string
  title: string
  status: LegalStatus
  topic: string
  year: string
  stage: string
  summary: string
  affectedSections: string[]
  timeline: TimelineEvent[]
}

export type ReviewItem = {
  id: string
  source: string
  page: string
  targetProvision: string
  confidence: string
  reviewer: string
  status: "needs-review" | "approved" | "needs-correction"
  oldWording: string
  newWording: string
}

export const languageOptions: { label: string; value: LanguageValue }[] = [
  { label: "Auto", value: "auto" },
  { label: "English", value: "english" },
  { label: "Pidgin", value: "pidgin" },
  { label: "Yorùbá", value: "yoruba" },
  { label: "Igbo", value: "igbo" },
  { label: "Hausa", value: "hausa" },
]

export const statusMeta: Record<
  LegalStatus,
  {
    icon: IconType
    label: string
    tone: string
    shortLabel: string
  }
> = {
  current: {
    icon: FiCheckCircle,
    label: "Current law",
    shortLabel: "Current",
    tone: "border-[color:var(--legal-emerald)]/20 bg-[color:var(--legal-emerald-soft)] text-[color:var(--legal-emerald-ink)]",
  },
  proposed: {
    icon: FiLoader,
    label: "Proposed change - not currently in force",
    shortLabel: "Proposed",
    tone: "border-[color:var(--legal-amber)]/25 bg-[color:var(--legal-amber-soft)] text-[color:var(--legal-amber)]",
  },
  historical: {
    icon: FiArchive,
    label: "Previous version - superseded",
    shortLabel: "Historical",
    tone: "border-border bg-secondary text-muted-foreground",
  },
  warning: {
    icon: FiAlertTriangle,
    label: "Unable to verify current source",
    shortLabel: "Verify",
    tone: "border-[color:var(--legal-red)]/25 bg-[color:var(--legal-red-soft)] text-[color:var(--legal-red)]",
  },
}

export const promptSuggestions = [
  "What does the Constitution say about privacy?",
  "Explain freedom of expression.",
  "Who can run for President?",
  "What has recently changed in the Constitution?",
  "Can you explain Section 37?",
]

export const recentConversations = [
  "Can police check my phone?",
  "Who can run for President?",
  "Freedom of expression",
  "Section thirty something about privacy",
]

const section37: Provision = {
  id: "section-37",
  section: "Section 37",
  title: "Right to private and family life",
  chapter: "Chapter IV",
  topic: "Privacy",
  status: "current",
  citation: "1999 Const. § 37",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter IV, Section 37",
  summary:
    "This protects private life, homes, correspondence, phone conversations and telegraphic communications. Interference still needs a lawful basis.",
  officialText:
    "The privacy of citizens, their homes, correspondence, telephone conversations and telegraphic communications is hereby guaranteed and protected.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "No later alteration is recorded for this provision.",
      status: "current",
    },
  ],
  related: ["Section 39", "Section 41", "Section 45"],
}

const section39: Provision = {
  id: "section-39",
  section: "Section 39",
  title: "Right to freedom of expression and the press",
  chapter: "Chapter IV",
  topic: "Expression",
  status: "current",
  citation: "1999 Const. § 39",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter IV, Section 39",
  summary:
    "This protects the freedom to hold opinions and to receive and impart ideas and information.",
  officialText:
    "Every person shall be entitled to freedom of expression, including freedom to hold opinions and to receive and impart ideas and information without interference.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "Displayed as current law in this preview corpus.",
      status: "current",
    },
  ],
  related: ["Section 37", "Section 40", "Section 45"],
}

const section34: Provision = {
  id: "section-34",
  section: "Section 34",
  title: "Right to dignity of human person",
  chapter: "Chapter IV",
  topic: "Human dignity",
  status: "current",
  citation: "1999 Const. § 34",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter IV, Section 34",
  summary:
    "This protects every person from torture, inhuman or degrading treatment, slavery and forced labour.",
  officialText:
    "Every individual is entitled to respect for the dignity of his person, and accordingly no person shall be subjected to torture or to inhuman or degrading treatment.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "Displayed as current law in this preview corpus.",
      status: "current",
    },
  ],
  related: ["Section 35", "Section 36", "Section 46"],
}

const section1: Provision = {
  id: "section-1",
  section: "Section 1",
  title: "Supremacy of the Constitution",
  chapter: "Chapter I",
  topic: "Supremacy",
  status: "current",
  citation: "1999 Const. § 1",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter I, Section 1",
  summary:
    "The Constitution is supreme and has binding force on authorities and people throughout Nigeria.",
  officialText:
    "This Constitution is supreme and its provisions shall have binding force on all authorities and persons throughout the Federal Republic of Nigeria.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "Displayed as current law in this preview corpus.",
      status: "current",
    },
  ],
  related: ["Section 4", "Section 5", "Section 6"],
}

const section4: Provision = {
  id: "section-4",
  section: "Section 4",
  title: "Legislative powers",
  chapter: "Chapter I",
  topic: "National Assembly",
  status: "current",
  citation: "1999 Const. § 4",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter I, Section 4",
  summary:
    "This defines legislative powers of the National Assembly and State Houses of Assembly.",
  officialText:
    "The legislative powers of the Federal Republic of Nigeria shall be vested in a National Assembly for the Federation.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "Displayed as current law in this preview corpus.",
      status: "current",
    },
  ],
  related: ["Section 1", "Section 5", "Section 6"],
}

const section130: Provision = {
  id: "section-130",
  section: "Section 130",
  title: "Establishment of the office of President",
  chapter: "Chapter VI",
  topic: "Executive",
  status: "current",
  citation: "1999 Const. § 130",
  sourceTitle:
    "Constitution of the Federal Republic of Nigeria, 1999 (as amended)",
  sourceAuthority: "Official constitutional document",
  sourcePage: "Chapter VI, Section 130",
  summary:
    "This establishes the office of President as Head of State, Chief Executive and Commander-in-Chief.",
  officialText:
    "There shall be for the Federation a President who shall be the Head of State, the Chief Executive of the Federation and Commander-in-Chief of the Armed Forces of the Federation.",
  history: [
    {
      marker: "1999",
      title: "Original wording",
      description: "Adopted with the 1999 Constitution.",
      status: "historical",
    },
    {
      marker: "Current",
      title: "Active text",
      description: "Displayed as current law in this preview corpus.",
      status: "current",
    },
  ],
  related: ["Section 131", "Section 132", "Section 135"],
}

export const chapters: Chapter[] = [
  {
    id: "chapter-1",
    number: "Chapter I",
    title: "General Provisions",
    range: "Sections 1-13",
    description: "Supremacy, federal structure and fundamental objectives.",
    provisions: [section1, section4],
  },
  {
    id: "chapter-4",
    number: "Chapter IV",
    title: "Fundamental Rights",
    range: "Sections 33-46",
    description: "Core rights and enforcement provisions.",
    provisions: [section34, section37, section39],
  },
  {
    id: "chapter-6",
    number: "Chapter VI",
    title: "The Executive",
    range: "Sections 130-191",
    description: "President, Governors and executive powers.",
    provisions: [section130],
  },
]

export const provisions = chapters.flatMap((chapter) => chapter.provisions)

export const defaultProvision = section37

export const amendments: Amendment[] = [
  {
    id: "first-alteration-2010",
    title: "First Alteration Act, 2010",
    status: "current",
    topic: "Courts and administration of justice",
    year: "2010",
    stage: "Enacted",
    summary:
      "Alterations affecting judicial administration and court powers. Displayed as enacted law in this preview.",
    affectedSections: ["Section 6", "Section 84", "Section 285"],
    timeline: [
      {
        marker: "Introduced",
        title: "National Assembly bill",
        description: "Alteration proposal introduced for legislative review.",
      },
      {
        marker: "Approved",
        title: "Legislative approvals completed",
        description: "Required approval path completed for this preview item.",
      },
      {
        marker: "Current",
        title: "Enacted alteration",
        description: "Treated separately from proposed amendments.",
        status: "current",
      },
    ],
  },
  {
    id: "fourth-alteration-2017",
    title: "Fourth Alteration Act, 2017",
    status: "current",
    topic: "Elections and judicial administration",
    year: "2017",
    stage: "Enacted",
    summary:
      "Changes relating to elections, judicial administration and local government matters.",
    affectedSections: ["Section 121", "Section 134", "Section 285"],
    timeline: [
      {
        marker: "2017",
        title: "Alteration enacted",
        description: "Displayed as current amendment law in this preview.",
        status: "current",
      },
      {
        marker: "Current",
        title: "Active changes",
        description: "Current-law impact is separated from proposals.",
        status: "current",
      },
    ],
  },
  {
    id: "electoral-governance-proposal",
    title: "Electoral and governance proposal",
    status: "proposed",
    topic: "Elections and governance",
    year: "2026",
    stage: "House review",
    summary:
      "A proposed alteration under legislative consideration. It is not part of the Constitution.",
    affectedSections: ["Section 134", "Section 179"],
    timeline: [
      {
        marker: "Introduced",
        title: "Bill filed",
        description: "Proposal is being considered by the House.",
        status: "proposed",
      },
      {
        marker: "House",
        title: "Current stage",
        description: "Not currently part of the Constitution.",
        status: "proposed",
      },
      {
        marker: "Pending",
        title: "Senate and state approval",
        description: "Later stages are not yet complete.",
      },
      {
        marker: "Pending",
        title: "Enactment",
        description: "No legal effect until the full process is complete.",
      },
    ],
  },
  {
    id: "fundamental-rights-proposal",
    title: "Fundamental rights proposal",
    status: "proposed",
    topic: "Rights protections",
    year: "2025",
    stage: "Senate review",
    summary:
      "Suggested rights changes. No legal effect until enacted through the constitutional alteration process.",
    affectedSections: ["Section 37", "Section 39", "Section 45"],
    timeline: [
      {
        marker: "Introduced",
        title: "Proposal received",
        description: "Marked as proposed for public understanding.",
        status: "proposed",
      },
      {
        marker: "Current",
        title: "Senate review",
        description: "Still not currently in force.",
        status: "proposed",
      },
      {
        marker: "Pending",
        title: "State ratification",
        description: "Ratification is not complete.",
      },
    ],
  },
]

export const answerStages = [
  "Understanding question",
  "Finding relevant provisions",
  "Checking current version",
  "Preparing explanation",
]

export const lowConfidenceMatches = [
  {
    section: "Section 37",
    title: "Privacy",
    summary: "Phone, correspondence, home and private life.",
  },
  {
    section: "Section 41",
    title: "Freedom of movement",
    summary: "Movement across Nigeria and residence rights.",
  },
]

export const savedProvisions = [
  {
    id: "saved-privacy",
    provision: section37,
    note: "Saved from phone-search conversation",
  },
  {
    id: "saved-expression",
    provision: section39,
    note: "Useful for press and speech questions",
  },
]

export const sourceDocuments = [
  {
    title: "1999 Constitution as amended",
    authority: "Official source",
    status: "Verified",
    pages: "172 pages",
    retrieved: "28 Aug 2026",
  },
  {
    title: "First Alteration Act package",
    authority: "National Assembly source",
    status: "Needs page check",
    pages: "18 pages",
    retrieved: "26 Aug 2026",
  },
  {
    title: "Rights alteration proposal",
    authority: "Legislative bill source",
    status: "Proposed only",
    pages: "9 pages",
    retrieved: "24 Aug 2026",
  },
]

export const ingestionJobs = [
  {
    id: "ING-204",
    source: "1999 Constitution as amended",
    status: "Parsed",
    progress: "100%",
    updated: "Today",
  },
  {
    id: "ING-203",
    source: "First Alteration Act package",
    status: "Human review",
    progress: "82%",
    updated: "Yesterday",
  },
  {
    id: "ING-202",
    source: "Rights alteration proposal",
    status: "Awaiting verification",
    progress: "64%",
    updated: "27 Aug",
  },
]

export const reviewQueue: ReviewItem[] = [
  {
    id: "REV-118",
    source: "First Alteration Act package",
    page: "Page 7",
    targetProvision: "Section 285",
    confidence: "92%",
    reviewer: "Unassigned",
    status: "needs-review",
    oldWording: "The court may make rules for regulating its own procedure.",
    newWording:
      "The court may make rules for regulating its practice and procedure, subject to the provisions of this Constitution.",
  },
  {
    id: "REV-117",
    source: "Rights alteration proposal",
    page: "Page 3",
    targetProvision: "Section 37",
    confidence: "71%",
    reviewer: "Legal QA",
    status: "needs-correction",
    oldWording:
      "The privacy of citizens, their homes, correspondence, telephone conversations and telegraphic communications is hereby guaranteed and protected.",
    newWording:
      "Proposed wording detected with uncertain subsection alignment. Human correction required before it can be used as evidence.",
  },
]

export const corpusReleases = [
  {
    version: "Corpus 0.3.0",
    status: "Candidate",
    notes: "Adds alteration-act lineage checks",
    evidence: "1,248 provisions",
  },
  {
    version: "Corpus 0.2.2",
    status: "Live",
    notes: "Current-law baseline with Chapter IV validation",
    evidence: "1,116 provisions",
  },
]

export const evaluationRuns = [
  {
    name: "Rights question set",
    status: "Passing",
    score: "94%",
    focus: "Source grounding and citations",
  },
  {
    name: "Pidgin phrasing set",
    status: "Needs review",
    score: "81%",
    focus: "Language detection and plain explanation",
  },
  {
    name: "Proposed-law confusion set",
    status: "Passing",
    score: "97%",
    focus: "Current versus proposed distinction",
  },
]

export const sidebarSections = [
  {
    label: "Explore",
    items: [
      { icon: FiMessageSquare, title: "Ask a question", path: "/" },
      {
        icon: FiBookOpen,
        title: "Browse laws",
        path: "/laws",
      },
      {
        icon: FiClock,
        title: "Amendments",
        path: "/amendments",
        count: "4",
      },
      {
        icon: FiBookmark,
        title: "Saved provisions",
        path: "/saved",
      },
    ],
  },
]
