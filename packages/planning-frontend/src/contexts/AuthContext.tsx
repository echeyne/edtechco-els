import {
  createContext,
  useContext,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import {
  AuthProvider,
  useDescope,
  useSession,
  useUser,
} from "@descope/react-sdk";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: { id: string; email: string } | null;
  login: () => void;
  logout: () => Promise<void>;
  token: string | null;
}

const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  login: () => {},
  logout: async () => {},
  token: null,
});

export function useAuth() {
  return useContext(AuthContext);
}

const DESCOPE_PROJECT_ID = import.meta.env.VITE_DESCOPE_PROJECT_ID ?? "";

/** Inner component that has access to Descope hooks (must be inside AuthProvider). */
function AuthInner({ children }: { children: ReactNode }) {
  const { isAuthenticated, isSessionLoading, sessionToken } = useSession();
  const { user: descopeUser } = useUser();
  const sdk = useDescope();

  const login = useCallback(() => {
    // Descope flow-based login is handled by the <Descope> component.
    // This is a no-op placeholder; the UI renders the Descope flow when needed.
  }, []);

  const logout = useCallback(async () => {
    await sdk.logout();
  }, [sdk]);

  const user = useMemo(() => {
    if (!isAuthenticated || !descopeUser) return null;
    return {
      id: descopeUser.userId ?? "",
      email: descopeUser.email ?? "",
    };
  }, [isAuthenticated, descopeUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: isAuthenticated && !isSessionLoading,
      isLoading: isSessionLoading,
      user,
      login,
      logout,
      token: sessionToken ?? null,
    }),
    [isAuthenticated, isSessionLoading, user, login, logout, sessionToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthContextProvider({ children }: { children: ReactNode }) {
  if (!DESCOPE_PROJECT_ID) {
    return (
      <AuthContext.Provider
        value={{
          isAuthenticated: false,
          isLoading: false,
          user: null,
          login: () => {},
          logout: async () => {},
          token: null,
        }}
      >
        {children}
      </AuthContext.Provider>
    );
  }

  return (
    <AuthProvider projectId={DESCOPE_PROJECT_ID}>
      <AuthInner>{children}</AuthInner>
    </AuthProvider>
  );
}
