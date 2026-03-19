import { Routes, Route, NavLink } from "react-router-dom";
import { AuthContextProvider } from "@/contexts/AuthContext";
import { LoginButton } from "@/components/LoginButton";
import HomePage from "@/pages/HomePage";
import DocumentsPage from "@/pages/DocumentsPage";
import PDFViewerPage from "@/pages/PDFViewerPage";
import InfoPage from "@/pages/InfoPage";
import LoginPage from "@/pages/LoginPage";
import DetailPage from "@/pages/DetailPage";

function App() {
  return (
    <AuthContextProvider>
      <div className="min-h-screen bg-background">
        <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-30 px-6 py-3">
          <div className="container flex items-center justify-between">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              <span className="text-primary">Early Learning Standards</span>{" "}
              <span className="font-normal text-muted-foreground">
                Explorer
              </span>
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
                to="/documents"
                className={({ isActive }) =>
                  `text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`
                }
              >
                Documents
              </NavLink>
              <NavLink
                to="/info"
                className={({ isActive }) =>
                  `text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`
                }
              >
                Info
              </NavLink>
              <div className="ml-2 pl-2 border-l">
                <LoginButton />
              </div>
            </nav>
          </div>
        </header>
        <main className="container py-6">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id/view" element={<PDFViewerPage />} />
            <Route
              path="/domains/:id"
              element={<DetailPage recordType="domain" />}
            />
            <Route
              path="/strands/:id"
              element={<DetailPage recordType="strand" />}
            />
            <Route
              path="/sub-strands/:id"
              element={<DetailPage recordType="sub_strand" />}
            />
            <Route
              path="/indicators/:id"
              element={<DetailPage recordType="indicator" />}
            />
            <Route path="/info" element={<InfoPage />} />
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </main>
      </div>
    </AuthContextProvider>
  );
}

export default App;
