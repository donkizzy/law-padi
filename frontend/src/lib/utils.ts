import { type ClassValue, clsx } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

// Type scale from index.css; without this, twMerge reads text-title-2 as a
// color and drops it next to text-foreground.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        "display",
        "title-1",
        "title-2",
        "title-3",
        "statute",
        "statute-sm",
        "body-lg",
        "body",
        "label",
        "overline",
        "code",
      ],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
