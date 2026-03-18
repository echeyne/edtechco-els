import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut } from "lucide-react";

export function LoginButton() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{user.email}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            await logout();
            navigate("/");
          }}
        >
          <LogOut className="mr-1.5 h-4 w-4" />
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <Button variant="outline" size="sm" onClick={() => navigate("/login")}>
      <LogIn className="mr-1.5 h-4 w-4" />
      Sign in
    </Button>
  );
}
