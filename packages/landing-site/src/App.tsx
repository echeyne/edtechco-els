import { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import ProjectsSection from "./components/ProjectsSection";
import ArticlesSection from "./components/ArticlesSection";
import AboutSection from "./components/AboutSection";
import Footer from "./components/Footer";
import PrivacyPage from "./components/PrivacyPage";
import TermsPage from "./components/TermsPage";
import ContactPage from "./components/ContactPage";

type Page = "home" | "privacy" | "terms" | "contact";

function hashToPage(hash: string): Page {
  if (hash === "#privacy") return "privacy";
  if (hash === "#terms") return "terms";
  if (hash === "#contact") return "contact";
  return "home";
}

function App() {
  const [page, setPage] = useState<Page>(hashToPage(window.location.hash));

  useEffect(() => {
    const onHashChange = () => setPage(hashToPage(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const goHome = () => {
    window.location.hash = "#hero";
  };

  return (
    <>
      <Navbar />
      <main>
        {page === "privacy" && <PrivacyPage onBack={goHome} />}
        {page === "terms" && <TermsPage onBack={goHome} />}
        {page === "contact" && <ContactPage onBack={goHome} />}
        {page === "home" && (
          <>
            <Hero />
            <ProjectsSection />
            <ArticlesSection />
            <AboutSection />
          </>
        )}
      </main>
      <Footer />
    </>
  );
}

export default App;
