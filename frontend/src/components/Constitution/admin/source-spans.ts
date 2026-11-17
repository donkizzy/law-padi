import type { ReviewItemPublic, SourcePagePublic } from "@/client"

type SourceSpanPreview = {
  bbox?: number[]
  page?: number
  width: number
  height: number
}

export function sourceSpanPreviews(
  spans: ReviewItemPublic["source_spans"],
  pages: SourcePagePublic[],
): SourceSpanPreview[] {
  if (!Array.isArray(spans)) return []
  return spans.map((span) => {
    const page =
      typeof span.page_number === "number"
        ? span.page_number
        : typeof span.page === "number"
          ? span.page
          : undefined
    const sourcePage = pages.find((item) => item.page_number === page)
    const box = span.bbox
    const objectBox =
      box && typeof box === "object"
        ? (box as Record<string, unknown>)
        : undefined
    const coordinates = Array.isArray(box)
      ? box
      : objectBox
        ? [objectBox.x0, objectBox.y0, objectBox.x1, objectBox.y1]
        : undefined
    const bbox =
      coordinates?.length === 4 &&
      coordinates.every(
        (value) => typeof value === "number" && Number.isFinite(value),
      )
        ? (coordinates as number[])
        : undefined
    const space = sourcePage?.quality_signals?.coordinate_space
    const dpi =
      space &&
      typeof space === "object" &&
      "render_dpi" in space &&
      typeof space.render_dpi === "number"
        ? space.render_dpi
        : 72
    const scale = dpi / 72
    const dimensionsKnown = sourcePage?.width && sourcePage?.height
    const raster =
      space &&
      typeof space === "object" &&
      "unit" in space &&
      space.unit === "raster_pixels"
    return {
      bbox,
      page,
      width:
        dimensionsKnown || !raster ? (sourcePage?.width ?? 612) * scale : 0,
      height:
        dimensionsKnown || !raster ? (sourcePage?.height ?? 792) * scale : 0,
    }
  })
}

export function sourceBoxStyle(span: SourceSpanPreview) {
  const [x1, y1, x2, y2] =
    span.bbox && span.bbox.length >= 4 ? span.bbox : [0, 0, 0, 0]
  return {
    height: `${clampPercent(((y2 - y1) / span.height) * 100)}%`,
    left: `${clampPercent((x1 / span.width) * 100)}%`,
    top: `${clampPercent((y1 / span.height) * 100)}%`,
    width: `${clampPercent(((x2 - x1) / span.width) * 100)}%`,
  }
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100) / 100))
}
