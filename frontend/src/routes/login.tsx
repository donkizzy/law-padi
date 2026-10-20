import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { redirectSearchSchema, safeRedirect } from "@/lib/redirect"

const formSchema = z.object({
  username: z.email({ message: "validation.emailInvalid" }),
  password: z
    .string()
    .min(1, { message: "validation.passwordRequired" })
    .min(8, { message: "validation.passwordMin" }),
}) satisfies z.ZodType<AccessToken>

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/login")({
  component: Login,
  validateSearch: redirectSearchSchema.extend({
    notice: z.enum(["check-email"]).optional().catch(undefined),
  }),
  beforeLoad: async ({ search }) => {
    if (isLoggedIn()) {
      const target = safeRedirect(search.redirect)
      throw target ? redirect({ href: target }) : redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Log in - constitution.ng",
      },
    ],
  }),
})

function Login() {
  const { t } = useTranslation("auth")
  const { redirect: redirectTo, notice } = Route.useSearch()
  const { loginMutation } = useAuth({ redirect: redirectTo })
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (loginMutation.isPending) return
    loginMutation.mutate(data)
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          <div className="flex flex-col items-center gap-2 text-center">
            <h1 className="text-2xl font-bold">{t("login.title")}</h1>
          </div>

          {notice === "check-email" && (
            <p
              className="sq-md border border-primary/30 bg-primary/5 p-3 text-sm"
              role="status"
            >
              {t("login.checkEmail")}
            </p>
          )}

          <div className="grid gap-4">
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("fields.email")}</FormLabel>
                  <FormControl>
                    <Input
                      data-testid="email-input"
                      placeholder="user@example.com"
                      type="email"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="text-xs" />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center">
                    <FormLabel>{t("fields.password")}</FormLabel>
                    <RouterLink
                      to="/recover-password"
                      className="ml-auto text-sm underline-offset-4 hover:underline"
                    >
                      {t("login.forgot")}
                    </RouterLink>
                  </div>
                  <FormControl>
                    <PasswordInput
                      data-testid="password-input"
                      placeholder={t("fields.password")}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="text-xs" />
                </FormItem>
              )}
            />

            <LoadingButton type="submit" loading={loginMutation.isPending}>
              {t("login.submit")}
            </LoadingButton>
          </div>

          <div className="text-center text-sm">
            {t("login.noAccount")}{" "}
            <RouterLink
              to="/signup"
              search={{ redirect: redirectTo }}
              className="underline underline-offset-4"
            >
              {t("login.signUp")}
            </RouterLink>
          </div>
        </form>
      </Form>
    </AuthLayout>
  )
}
