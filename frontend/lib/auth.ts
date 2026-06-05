/** NextAuth.js configuration for Prism. */

import type { NextAuthOptions } from "next-auth";
import EmailProvider from "next-auth/providers/email";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

async function fetchUserByEmail(
  email: string,
): Promise<{
  id: number;
  api_key_hash: string;
  is_pro: boolean;
  interests: string;
} | null> {
  try {
    const res = await fetch(
      `${FASTAPI_URL}/users?email=${encodeURIComponent(email)}`,
    );
    if (!res.ok) return null;
    const users = await res.json();
    // The API returns a list; pick the first match
    if (Array.isArray(users) && users.length > 0) return users[0];
    if (!Array.isArray(users) && users.id) return users;
    return null;
  } catch {
    return null;
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    EmailProvider({
      server: {
        host: process.env.EMAIL_SERVER_HOST || "smtp.resend.com",
        port: Number(process.env.EMAIL_SERVER_PORT) || 465,
        auth: {
          user: process.env.EMAIL_SERVER_USER || "resend",
          pass: process.env.RESEND_API_KEY || "",
        },
      },
      from: process.env.EMAIL_FROM || "noreply@yourdomain.com",
    }),
  ],

  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  callbacks: {
    async signIn({ user }) {
      if (!user.email) return false;
      const prismUser = await fetchUserByEmail(user.email);
      return prismUser !== null;
    },

    async jwt({ token, trigger }) {
      if (trigger === "signIn" && token.email) {
        const prismUser = await fetchUserByEmail(token.email);
        if (prismUser) {
          token.userId = prismUser.id;
          token.apiKeyHash = prismUser.api_key_hash;
          token.isPro = prismUser.is_pro;
          token.interests = prismUser.interests;
        }
      }
      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        (session.user as Record<string, unknown>).id = token.userId;
        (session.user as Record<string, unknown>).isPro = token.isPro;
        (session.user as Record<string, unknown>).interests = token.interests;
        // api_key stays in token only — NEVER exposed to browser
      }
      return session;
    },
  },

  pages: {
    signIn: "/login",
    newUser: "/signup",
    verifyRequest: "/check-email",
    error: "/auth-error",
  },
};

export { fetchUserByEmail, FASTAPI_URL };
