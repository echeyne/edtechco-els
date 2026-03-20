import { Routes, Route, NavLink } from "react-router-dom";
import { AuthContextProvider } from "@/contexts/AuthContext";
import AuthGuard from "@/components/AuthGuard";
import LandingPage from "@/pages/LandingPage";
import AboutPage from "@/pages/AboutPage";
import PlanningPage from "@/pages/PlanningPage";
import PlanDetailPage from "@/pages/PlanDetailPage";

function App() {
  return (
    <AuthContextProvider>
      <div className="min-h-screen bg-background">
        <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-30 px-6 py-3">
          <div className="container flex items-center justify-between">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              <span className="text-primary">Parent Planning</span>{" "}
              <span className="font-normal text-muted-foreground">Tool</span>
            </h1>
            <nav className="flex items-center gap-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`
                }
              >
                Home
              </NavLink>
              <NavLink
                to="/about"
                className={({ isActive }) =>
                  `text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`
                }
              >
                About
              </NavLink>
              <NavLink
                to="/planning"
                className={({ isActive }) =>
                  `text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`
                }
              >
                Planning
              </NavLink>
            </nav>
          </div>
        </header>
        <main className="container py-6">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route
              path="/planning"
              element={
                <AuthGuard>
                  <PlanningPage />
                </AuthGuard>
              }
            />
            <Route
              path="/planning/:id"
              element={
                <AuthGuard>
                  <PlanDetailPage />
                </AuthGuard>
              }
            />
          </Routes>
        </main>
      </div>
    </AuthContextProvider>
  );
}

export default App;
