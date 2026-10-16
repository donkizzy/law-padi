import { Text } from "@react-email/components"
import { LinkButton } from "../ui/Button"
import { Heading } from "../ui/Heading"
import { Layout } from "../ui/Layout"
import { Link } from "../ui/Link"

type AccountExistsProps = {
  project_name: string
  login_link: string
  reset_link: string
}

export default function AccountExists({
  project_name = "{{ project_name }}",
  login_link = "{{ login_link }}",
  reset_link = "{{ reset_link }}",
}: AccountExistsProps) {
  return (
    <Layout
      title={`${project_name} - You already have an account`}
      preview={`You already have a ${project_name} account`}
      project_name={project_name}
    >
      <Heading>You already have an account</Heading>
      <Text style={bodyTextStyle}>
        Someone tried to create a {project_name} account with this email
        address. You already have one, so you can log in instead.
      </Text>
      <LinkButton href={login_link}>Log in</LinkButton>
      <Text style={supportingTextStyle}>
        Forgot your password? <Link href={reset_link}>Reset it here</Link>.
      </Text>
      <Text style={supportingTextStyle}>
        If this wasn't you, you can safely ignore this email. Your account
        hasn't changed.
      </Text>
    </Layout>
  )
}

const bodyTextStyle = {
  color: "#334155",
  fontSize: "15px",
  lineHeight: "26px",
  margin: "0 0 18px",
}

const supportingTextStyle = {
  color: "#64748b",
  fontSize: "14px",
  lineHeight: "23px",
  margin: "0 0 16px",
}
