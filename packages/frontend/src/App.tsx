import { Routes, Route, NavLink } from "react-router-dom";
import { AuthContextProvider } from "@/contexts/AuthContext";
import HomePage from "@/pages/HomePage";
import DocumentsPage from "@/pages/DocumentsPage";
import PDFViewerPage from "@/pages/PDFViewerPage";
import InfoPage from "@/pages/InfoPage";

function App() {
  return (
    <AuthContextProvider>
      <div className="min-h-screen bg-background">
        <header className="border-b px-6 py-4">
          <div className="container flex items-center justify-between">
            <h1 className="text-2xl font-semibold">
              Early Learning Standards Explorer
            </h1>
            <nav className="flex items-center gap-4">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors hover:text-primary ${
                    isActive ? "text-primary" : "text-muted-foreground"
                  }`
                }
              >
                Home
              </NavLink>
              <NavLink
                to="/documents"
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors hover:text-primary ${
                    isActive ? "text-primary" : "text-muted-foreground"
                  }`
                }
              >
                Documents
              </NavLink>
              <NavLink
                to="/info"
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors hover:text-primary ${
                    isActive ? "text-primary" : "text-muted-foreground"
                  }`
                }
              >
                Info
              </NavLink>
            </nav>
          </div>
        </header>
        <main className="container py-6">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id/view" element={<PDFViewerPage />} />
            <Route path="/info" element={<InfoPage />} />
          </Routes>
        </main>
      </div>
    </AuthContextProvider>
  );
}

export default App;
