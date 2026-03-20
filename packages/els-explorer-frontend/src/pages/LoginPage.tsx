import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Descope } from "@descope/react-sdk";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const handleSuccess = useCallback(() => {
    navigate("/");
  }, [navigate]);

  // If already logged in, redirect home
  if (isAuthenticated) {
    navigate("/");
    return null;
  }

  return (
    <div className="mx-auto max-w-md py-12">
      <h2 className="mb-6 text-center text-xl font-semibold">Sign in</h2>
      <Descope
        flowId="sign-up-or-in"
        onSuccess={handleSuccess}
        onError={(e) => console.error("Login error:", e)}
      />
    </div>
  );
}
