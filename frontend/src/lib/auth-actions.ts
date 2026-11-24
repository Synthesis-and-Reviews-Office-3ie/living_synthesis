"use server";

import { signIn, signOut } from "@/lib/auth";
import { redirect } from "next/navigation";

export async function signInWithGoogle() {
  await signIn("google", { redirect: true, redirectTo: "/dashboard" });
}

export async function signInWithMicrosoft() {
  await signIn("microsoft-entra-id", { redirect: true, redirectTo: "/dashboard" });
}

export async function signInWithGitHub() {
  await signIn("github", { redirect: true, redirectTo: "/dashboard" });
}

export async function signInWithCredentials(email: string, password: string) {
  try {
    await signIn("credentials", { email, password, redirect: false });
    redirect("/dashboard");
  } catch (error: any) {
    throw error;
  }
}

export async function signOutAction() {
  await signOut({ redirect: true, redirectTo: "/" });
}
