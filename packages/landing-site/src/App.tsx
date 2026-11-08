import { useEffect, type ComponentType } from "react";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import HomeProof from "./components/HomeProof";
import HomeExample from "./components/HomeExample";
import ArticlesSection from "./components/ArticlesSection";
import AboutSection from "./components/AboutSection";
import Footer from "./components/Footer";
import PrivacyPage from "./components/PrivacyPage";
import TermsPage from "./components/TermsPage";
import ContactPage from "./components/ContactPage";
import ResearchPage from "./pages/ResearchPage";
import DataPage from "./pages/DataPage";
import ForStatesPage from "./pages/ForStatesPage";
import ForResearchersPage from "./pages/ForResearchersPage";
import ForCurriculumPage from "./pages/ForCurriculumPage";
import AboutPage from "./pages/AboutPage";
import BriefPage from "./pages/BriefPage";
import NotFoundPage from "./pages/NotFoundPage";
import { useDocumentTitle } from "./components/ui";
import {
  matchRoute,
  scrollToHash,
  useLocation,
  type RoutePath,
} from "./router";

function HomePage() {
  useDocumentTitle(null);
  return (
    <>
      <Hero />
      <HomeProof />
      <HomeExample />
      <ArticlesSection />
      <AboutSection />
    </>
  );
}

const PAGES: Record<RoutePath, ComponentType> = {
  "/": HomePage,
  "/research": ResearchPage,
  "/data": DataPage,
  "/for-states": ForStatesPage,
  "/for-researchers": ForResearchersPage,
  "/for-curriculum": ForCurriculumPage,
  "/about": AboutPage,
  "/brief": BriefPage,
  "/contact": ContactPage,
  "/privacy": PrivacyPage,
  "/terms": TermsPage,
};

function App() {
  const { pathname, hash } = useLocation();
  const route = matchRoute(pathname);
  const Page = route ? PAGES[route] : NotFoundPage;

  // New page: jump to the anchor if there is one, otherwise to the top.
  useEffect(() => {
    if (!scrollToHash(hash)) window.scrollTo(0, 0);
  }, [pathname, hash]);

  return (
    <>
      <div className="print:hidden">
        <Navbar />
      </div>
      <main>
        <Page />
      </main>
      <div className="print:hidden">
        <Footer />
      </div>
    </>
  );
}

export default App;
