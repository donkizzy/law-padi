/**
 * Reflow single source line wraps while keeping blank-line paragraphs and
 * breaks before numbered parts and provisos. Copied text uses the original.
 */
export function readableText(text: string) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .split(/\n{2,}/)
    .map((paragraph) =>
      paragraph
        .replace(
          /\n(?!\s*(?:\((?:\d+[a-z]?|[a-z]{1,2}|[ivxlc]+)\)|Provided\b))\s*/g,
          " ",
        )
        .replace(
          /([;:\u2014-])\s+(\((?:\d+[a-z]?|[a-z]|[ivxlc]+)\)\s)/g,
          "$1\n$2",
        ),
    )
    .join("\n\n")
    .replace(/^\n/, "")
}

export type StatuteBlock =
  | { kind: "text"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] }

function tableCells(line: string) {
  return line.includes("|") ? line.split("|").map((cell) => cell.trim()) : []
}

/**
 * Split stored text into prose and tables. A printed table is stored one row
 * per line with cells separated by "|"; a run of such lines is a table whose
 * first line is the header. Display only, like readableText.
 */
export function statuteBlocks(text: string): StatuteBlock[] {
  const blocks: StatuteBlock[] = []
  let prose: string[] = []
  let table: string[][] = []
  const flushProse = () => {
    const joined = readableText(prose.join("\n"))
    if (joined.trim()) blocks.push({ kind: "text", text: joined })
    prose = []
  }
  const flushTable = () => {
    if (table.length < 2) {
      prose.push(...table.map((row) => row.join(" | ")))
    } else {
      flushProse()
      const width = Math.max(...table.map((row) => row.length))
      const [header, ...rows] = table.map((row) => [
        ...row,
        ...Array<string>(width - row.length).fill(""),
      ])
      blocks.push({ kind: "table", header, rows })
    }
    table = []
  }
  for (const line of text.split("\n")) {
    const cells = tableCells(line)
    if (cells.length >= 2) {
      table.push(cells)
    } else {
      flushTable()
      prose.push(line)
    }
  }
  flushTable()
  flushProse()
  return blocks
}
