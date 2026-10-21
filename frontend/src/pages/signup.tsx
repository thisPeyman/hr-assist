import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Wordmark } from "@/components/shell"
import { useAuth } from "@/auth"
import { persianError, signup } from "@/lib/api"

export function SignupPage() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [orgName, setOrgName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signup({ email, password, org_name: orgName })
      await refresh()
      navigate("/")
    } catch (e) {
      setError(persianError(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-8 bg-background p-4">
      <Wordmark />
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">ساخت حساب جدید</CardTitle>
          <CardDescription>
            با ثبت‌نام، سازمان شما ساخته می‌شود و شما نخستین مدیر آن خواهید بود.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit}>
            <FieldGroup>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <Field>
                <FieldLabel htmlFor="org-name">نام شرکت</FieldLabel>
                <Input
                  id="org-name"
                  autoComplete="organization"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="email">رایانامه</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  dir="ltr"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">گذرواژه</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <p className="text-sm text-muted-foreground">
                  دست‌کم ۸ نویسه انتخاب کنید.
                </p>
              </Field>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "در حال ساخت…" : "ایجاد سازمان و ورود"}
              </Button>
            </FieldGroup>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            از قبل حساب دارید؟{" "}
            <Link to="/login" className="font-medium text-primary hover:underline">
              وارد شوید
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
