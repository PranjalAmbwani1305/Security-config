import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, refreshSession, setAuthLostHandler, tokens } from "../lib/api";

export type Role = "org_admin" | "grc_manager" | "grc_auditor" | "reviewer" | "read_only";

export type User = {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  is_platform_admin: boolean;
};
export type Organization = { id: string; name: string; slug: string; is_active: boolean };
export type Membership = { organization: Organization; role: Role };

type SessionResponse = {
  access_token: string;
  refresh_token: string;
  user: User;
  organization: Organization | null;
  role: Role | null;
  permissions: string[];
};
type MeResponse = Omit<SessionResponse, "access_token" | "refresh_token"> & {
  memberships: Membership[];
};

type RegisterInput = {
  email: string;
  password: string;
  full_name: string;
  organization_name?: string;
  invitation_token?: string;
};

type AuthState = {
  status: "loading" | "authenticated" | "anonymous";
  me: MeResponse | null;
};

type AuthContextValue = {
  status: AuthState["status"];
  user: User | null;
  organization: Organization | null;
  role: Role | null;
  memberships: Membership[];
  /** Mirrors the backend permission matrix; the backend remains the enforcer. */
  can: (permission: string) => boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  loginWithGoogle: (
    credential: string,
    extra?: { organization_name?: string; invitation_token?: string },
  ) => Promise<void>;
  switchOrganization: (organizationId: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", me: null });

  const loadMe = useCallback(async () => {
    const me = await api<MeResponse>("/auth/me");
    setState({ status: "authenticated", me });
  }, []);

  const adopt = useCallback(
    async (session: SessionResponse) => {
      tokens.set(session.access_token, session.refresh_token);
      await loadMe();
    },
    [loadMe],
  );

  // Restore the session on page load from the stored refresh token.
  useEffect(() => {
    setAuthLostHandler(() => setState({ status: "anonymous", me: null }));
    (async () => {
      if (tokens.hasRefresh() && (await refreshSession())) {
        try {
          await loadMe();
          return;
        } catch {
          tokens.clear();
        }
      }
      setState({ status: "anonymous", me: null });
    })();
    return () => setAuthLostHandler(null);
  }, [loadMe]);

  const value = useMemo<AuthContextValue>(() => {
    const me = state.me;
    const permissions = new Set(me?.permissions ?? []);
    return {
      status: state.status,
      user: me?.user ?? null,
      organization: me?.organization ?? null,
      role: me?.role ?? null,
      memberships: me?.memberships ?? [],
      can: (p) => permissions.has(p),
      login: async (email, password) =>
        adopt(await api<SessionResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) })),
      register: async (input) =>
        adopt(await api<SessionResponse>("/auth/register", { method: "POST", body: JSON.stringify(input) })),
      loginWithGoogle: async (credential, extra) =>
        adopt(
          await api<SessionResponse>("/auth/sso/google", {
            method: "POST",
            body: JSON.stringify({ credential, ...extra }),
          }),
        ),
      switchOrganization: async (organizationId) =>
        adopt(
          await api<SessionResponse>("/auth/switch-organization", {
            method: "POST",
            body: JSON.stringify({ organization_id: organizationId }),
          }),
        ),
      logout: async () => {
        try {
          await api("/auth/logout", { method: "POST" });
        } catch {
          /* session may already be gone server-side */
        }
        tokens.clear();
        setState({ status: "anonymous", me: null });
      },
    };
  }, [state, adopt]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
