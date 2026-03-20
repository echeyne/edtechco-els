import { useNavigate, useLocation } from "react-router-dom";
import { Descope } from "@descope/react-sdk";
import { useAuth } from "@/contexts/AuthContext";
import { useEffect } from "react";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  const from =
    (location.state as { from?: Location })?.from?.pathname ?? "/planning";

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md py-12">
      <h2 className="text-2xl font-semibold text-center mb-6">Sign in</h2>
      <Descope
        flowId="sign-up-or-in"
        onSuccess={() => navigate(from, { replace: true })}
        onError={(e) => console.error("Descope login error", e)}
      />
    </div>
  );
}
