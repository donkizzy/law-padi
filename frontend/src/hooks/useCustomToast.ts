import { toast } from "sonner"
import i18n from "@/lib/i18n"

const useCustomToast = () => {
  const showSuccessToast = (description: string) => {
    toast.success(i18n.t("toast.success"), {
      description,
    })
  }

  const showErrorToast = (description: string) => {
    toast.error(i18n.t("toast.error"), {
      description,
    })
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
