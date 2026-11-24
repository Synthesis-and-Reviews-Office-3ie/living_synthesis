import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import GitHub from "next-auth/providers/github";
import Credentials from "next-auth/providers/credentials";
import type { Provider } from "next-auth/providers";

const providers: Provider[] = [
  // OAuth Providers
  Google({
    clientId: process.env.GOOGLE_CLIENT_ID!,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    authorization: {
      params: {
        prompt: "consent",
        access_type: "offline",
        response_type: "code",
      },
    },
  }),
  MicrosoftEntraID({
    clientId: process.env.MICROSOFT_CLIENT_ID!,
    clientSecret: process.env.MICROSOFT_CLIENT_SECRET!,
    tenantId: "common", // allows personal & work accounts
  }),
  GitHub({
    clientId: process.env.GITHUB_CLIENT_ID!,
    clientSecret: process.env.GITHUB_CLIENT_SECRET!,
  }),
  // Email/Password fallback (syncs with backend)
  Credentials({
    name: "Email",
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "Password", type: "password" },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) return null;

      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email as string,
            password: credentials.password as string,
          }),
        });

        if (!res.ok) return null;

        const data = await res.json();
        return {
          id: data.user_id || credentials.email,
          email: credentials.email as string,
          name: data.name,
          accessToken: data.access_token,
          tier: data.tier || "free",
        };
      } catch {
        return null;
      }
    },
  }),
];

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers,
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // Initial sign in
      if (account && user) {
        // Sync OAuth user with backend
        if (account.provider !== "credentials") {
          try {
            // Add 5 second timeout to prevent hanging
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/oauth-sync`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                provider: account.provider,
                provider_id: account.providerAccountId,
                email: user.email,
                name: user.name,
                image: user.image,
                access_token: account.access_token,
              }),
              signal: controller.signal,
            });
            
            clearTimeout(timeoutId);

            if (res.ok) {
              const data = await res.json();
              token.accessToken = data.access_token;
              token.userId = data.user_id;
              token.tier = data.tier || "free";
              token.userName = data.name;
              // Store token expiration time (backend token expires in 1 week)
              token.accessTokenExpires = Date.now() + 7 * 24 * 60 * 60 * 1000;
            }
          } catch (error) {
            console.error("OAuth sync failed (will retry on next request):", error);
            // Still allow login even if backend sync fails - we'll sync later
          }
        } else {
          // Credentials provider - token already has accessToken
          token.accessToken = (user as any).accessToken;
          token.tier = (user as any).tier || "free";
          token.userName = (user as any).name;
          // Store token expiration time
          token.accessTokenExpires = Date.now() + 7 * 24 * 60 * 60 * 1000;
        }
      }

      // Check if token needs refresh (refresh if less than 1 day left)
      const shouldRefresh = token.accessTokenExpires && 
        (token.accessTokenExpires as number) - Date.now() < 24 * 60 * 60 * 1000;
      
      if (shouldRefresh && token.accessToken) {
        try {
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token.accessToken}`,
            },
          });

          if (res.ok) {
            const data = await res.json();
            token.accessToken = data.access_token;
            token.accessTokenExpires = Date.now() + 7 * 24 * 60 * 60 * 1000;
            console.log("[Auth] Token refreshed successfully");
          }
        } catch (error) {
          console.error("[Auth] Token refresh failed:", error);
        }
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.userId = token.userId as string;
      session.tier = token.tier as string;
      session.userName = token.userName as string;
      return session;
    },
  },
  session: {
    strategy: "jwt",
  },
  trustHost: true,
});

// Extend next-auth types
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    userId?: string;
    tier?: string;
    userName?: string;
  }
}
