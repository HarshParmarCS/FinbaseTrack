"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Loader2, Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FormField, describedBy } from "@/components/shared/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { InputWithIcon } from "@/components/shared/input-with-icon";
import { PasswordInput } from "@/components/shared/password-input";
import { AuthCard } from "@/features/auth/auth-card";
import { applyApiError } from "@/lib/api/form-errors";
import { useRegister } from "@/features/auth/hooks";
import { registerSchema, type RegisterValues } from "@/features/auth/schemas";

const FIELDS = ["name", "email", "password"] as const;

export function RegisterForm() {
  const params = useSearchParams();
  const registerUser = useRegister();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: "", email: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      // The backend signs the new user in (it sets the session cookies), so GuestGate moves on.
      await registerUser.mutateAsync(values);
    } catch (error) {
      setFormError(applyApiError(error, FIELDS, setError, { emailConflictField: "email" }));
    }
  });

  const queryNext = params.get("next");
  const loginHref = queryNext ? `/login?next=${encodeURIComponent(queryNext)}` : "/login";

  return (
    <AuthCard
      title="Create your account"
      description="Start organizing projects and tasks with your team."
      footer={
        <>
          Already registered?{" "}
          <Link href={loginHref} className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4" aria-label="Create account">
        {formError ? (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        ) : null}

        <FormField id="name" label="Name" error={errors.name?.message}>
          <InputWithIcon
            icon={UserRound}
            id="name"
            placeholder="Your full name"
            autoComplete="name"
            aria-invalid={Boolean(errors.name)}
            aria-describedby={describedBy("name", { error: errors.name?.message })}
            {...register("name")}
          />
        </FormField>
        <FormField id="email" label="Email" error={errors.email?.message}>
          <InputWithIcon
            icon={Mail}
            id="email"
            type="email"
            placeholder="name@company.com"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={describedBy("email", { error: errors.email?.message })}
            {...register("email")}
          />
        </FormField>
        <FormField
          id="password"
          label="Password"
          hint="At least 8 characters."
          error={errors.password?.message}
        >
          <PasswordInput
            id="password"
            autoComplete="new-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={describedBy("password", {
              error: errors.password?.message,
              hint: "At least 8 characters.",
            })}
            {...register("password")}
          />
        </FormField>

        <Button type="submit" size="cta" className="w-full" disabled={registerUser.isPending}>
          {registerUser.isPending ? "Creating account…" : "Create account"}
          {registerUser.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <ArrowRight aria-hidden />
          )}
        </Button>
      </form>
    </AuthCard>
  );
}
