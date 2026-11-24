"use client";

import React, { createContext, useContext, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";

interface User {
  id?: string;
  email?: string | null;
  name?: string | null;
  image?: string | null;
  tier?: "free" | "pro" | "team";
  preferred_llm_model?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => void;
  refreshUser: () => void;
  accessToken: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status, update } = useSession();
  
  const user: User | null = session?.user ? {
    id: session.userId as string,
    email: session.user.email,
    name: session.userName || session.user.name,
    image: session.user.image,
    tier: (session.tier as "free" | "pro" | "team") || "free",
  } : null;

  const accessToken = session?.accessToken || null;

  // Store token in localStorage for axios interceptor
  useEffect(() => {
    if (accessToken) {
      console.log("[Auth] Token stored in localStorage");
      localStorage.setItem("token", accessToken);
    } else {
      console.log("[Auth] No access token in session, clearing localStorage");
      localStorage.removeItem("token");
    }
  }, [accessToken]);

  const logout = () => {
    localStorage.removeItem("token");
    signOut({ callbackUrl: "/" });
  };

  const refreshUser = () => {
    update();
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      loading: status === "loading", 
      logout,
      refreshUser,
      accessToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
