import { expect, test } from "@playwright/test"
import { statuteBlocks } from "../src/lib/statute-text"

test("preserves explicit definition paragraphs while reflowing source lines", () => {
  const text = [
    "In this Act —",
    "",
    '"Board" means the Joint Revenue Board',
    "of Nigeria;",
    "  ",
    '"person" includes an individual,',
    "a company or a body of individuals.",
  ].join("\r\n")

  expect(statuteBlocks(text)).toEqual([
    {
      kind: "text",
      text: 'In this Act —\n\n"Board" means the Joint Revenue Board of Nigeria;\n\n"person" includes an individual, a company or a body of individuals.',
    },
  ])
})

test("preserves numbered paragraphs and provisos when reflowing source lines", () => {
  const text =
    "The Board may —\n(a) hold or dispose\nof its property; and\n(b) keep records.\nProvided that the Act applies."

  expect(statuteBlocks(text)).toEqual([
    {
      kind: "text",
      text: "The Board may —\n(a) hold or dispose of its property; and\n(b) keep records.\nProvided that the Act applies.",
    },
  ])
})
