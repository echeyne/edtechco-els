import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import ProjectsSection from "./components/ProjectsSection";
import ArticlesSection from "./components/ArticlesSection";
import AboutSection from "./components/AboutSection";
import Footer from "./components/Footer";

function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <ProjectsSection />
        <ArticlesSection />
        <AboutSection />
      </main>
      <Footer />
    </>
  );
}

export default App;
