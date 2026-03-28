export interface Article {
  title: string;
  description: string;
  url: string;
}

export const articles: Article[] = [
  {
    title: "Building an Early Learning Standards Explorer with AI",
    description:
      "How we used data engineering and AI to make early learning standards across states searchable and comparable for educators.",
    url: "https://medium.com/@edtechco/building-an-early-learning-standards-explorer-with-ai",
  },
  {
    title: "From Data Pipelines to Parent Tools",
    description:
      "The journey of turning raw educational standards data into a practical planning tool for parents and caregivers.",
    url: "https://medium.com/@edtechco/from-data-pipelines-to-parent-tools",
  },
  {
    title: "Lessons Learned: Open-Source EdTech Development",
    description:
      "Reflections on building open-source tools for education, including challenges with data quality, accessibility, and community feedback.",
    url: "https://medium.com/@edtechco/lessons-learned-open-source-edtech-development",
  },
];
