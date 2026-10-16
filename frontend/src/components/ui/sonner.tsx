"use client"

import {
  FiAlertOctagon as OctagonXIcon,
  FiAlertTriangle as TriangleAlertIcon,
  FiCheckCircle as CircleCheckIcon,
  FiInfo as InfoIcon,
  FiLoader as Loader2Icon,
} from "react-icons/fi"
import { useTheme } from "@/components/theme-provider"
import { useIsMobile } from "@/hooks/useMobile"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme } = useTheme()
  // On phones a bottom stack covers the sticky question box and inline
  // actions, so show one toast at a time over the header instead.
  const isMobile = useIsMobile()

  return (
    <Sonner
      theme={theme}
      position={isMobile ? "top-center" : "bottom-right"}
      visibleToasts={isMobile ? 1 : 3}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
