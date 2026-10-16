import { Text } from "@react-email/components"
import { LinkButton } from "../ui/Button"
import { Heading } from "../ui/Heading"
import { Layout } from "../ui/Layout"
import { Link } from "../ui/Link"

type VerifyEmailProps = {
  project_name: string
  link: string
  valid_hours: string
}

export default function VerifyEmail({
  project_name = "{{ project_name }}",
  link = "{{ link }}",
  valid_hours = "{{ valid_hours }}",
}: VerifyEmailProps) {
  return (
    <Layout
      title={`${project_name} - Confirm your email address`}
      preview={`Confirm your email address for ${project_name}`}
      project_name={project_name}
    >
      <Heading>Confirm your email address</Heading>
      <Text style={bodyTextStyle}>
        Thanks for creating a {project_name} account. Confirm this is your
        email address so your saved sections and conversations can follow you
        to any device.
      </Text>
      <LinkButton href={link}>Confirm email address</LinkButton>
      <Text style={supportingTextStyle}>
        Or copy and paste this link into your browser:
        <br />
        <Link href={link}>{link}</Link>
      </Text>
      <Text style={supportingTextStyle}>
        This link will expire in {valid_hours} hours.
      </Text>
      <Text style={supportingTextStyle}>
        If you didn't create an account, you can safely ignore this email.
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
