import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { statuteBlocks } from "@/lib/legal-provisions"

/** Stored statute wording as prose, with printed tables shown as tables. */
export function StatuteText({
  text,
  className,
}: {
  text: string
  className?: string
}) {
  return (
    <div lang="en" className={className}>
      {statuteBlocks(text).map((block, index) =>
        block.kind === "text" ? (
          <p className="whitespace-pre-wrap not-first:mt-4" key={index}>
            {block.text}
          </p>
        ) : (
          // Inline-size containment keeps a wide table scrolling in its own box
          // instead of stretching every layout that hosts statute text.
          <div className="not-first:mt-4 [contain:inline-size]" key={index}>
            <Table className="min-w-xl font-sans">
              <TableHeader>
                <TableRow>
                  {block.header.map((cell, column) => (
                    <TableHead
                      className="h-auto py-2 align-bottom whitespace-normal"
                      key={column}
                    >
                      {cell}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {block.rows.map((row, rowIndex) => (
                  <TableRow key={rowIndex}>
                    {row.map((cell, column) => (
                      <TableCell
                        className="align-top whitespace-normal"
                        key={column}
                      >
                        {cell}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ),
      )}
    </div>
  )
}
