import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { LogIn, LogOut } from "lucide-react";

export function LoginButton() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{user.email}</span>
        <button
          className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-muted transition-colors"
          onClick={async () => {
            await logout();
            navigate("/");
          }}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    );
  }

  return (
    <button
      className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-muted transition-colors"
      onClick={() => navigate("/login")}
    >
      <LogIn className="h-4 w-4" />
      Sign in
    </button>
  );
}
