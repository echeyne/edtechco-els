export interface Project {
  title: string;
  description: string;
  url: string;
}

export const projects: Project[] = [
  {
    title: "Early Learning Standards Explorer",
    description:
      "A tool for exploring early learning standards across states, helping educators and policymakers compare and navigate developmental benchmarks.",
    url: "https://els-explorer.example.com",
  },
  {
    title: "Parent Planning Tool",
    description:
      "A tool for parents to create personalized learning plans for their children, aligned with state early learning standards.",
    url: "https://planning.example.com",
  },
];
