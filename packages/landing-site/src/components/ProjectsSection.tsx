import { projects as defaultProjects, type Project } from "../data/projects";
import ProjectCard from "./ProjectCard";

interface ProjectsSectionProps {
  projects?: Project[];
}

export default function ProjectsSection({
  projects = defaultProjects,
}: ProjectsSectionProps) {
  return (
    <section id="projects" className="px-4 pb-16">
      <h2 className="mb-10 text-center text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Our Projects
      </h2>
      <div className="mx-auto grid max-w-4xl grid-cols-1 gap-6 md:grid-cols-2">
        {projects.map((project) => (
          <ProjectCard key={project.title} project={project} />
        ))}
      </div>
    </section>
  );
}
