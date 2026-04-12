export interface Article {
  title: string;
  description: string;
  url: string;
}

export const articles: Article[] = [
  {
    title: "Early Childhood Education Has a Data Problem",
    description:
      "How fragmented early learning standards are quietly undermining the P-3 pipeline — and what software engineering can do about it",
    url: "https://medium.com/@emilycheyne/early-childhood-education-has-a-data-problem-2e1a758764be",
  },
  {
    title: "Teaching AI to Read Like a Curriculum Specialist",
    description:
      "Inside the prompt engineering and architecture behind an automated early learning standards parser",
    url: "https://medium.com/@emilycheyne/teaching-ai-to-read-like-a-curriculum-specialist-2709bc6fa880",
  },
  {
    title:
      "From Standards to Story Time: Building an AI Planning Assistant Grounded in Real Early Learning Data",
    description:
      "How a conversational agent turns state-specific learning standards into personalized activity plans for families",
    url: "https://medium.com/@emilycheyne/from-standards-to-story-time-building-an-ai-planning-assistant-grounded-in-real-early-learning-68af26d83591",
  },
  {
    title:
      "Why a Human Verification Layer is Necessary in Addition to the AI Pipeline",
    description:
      "AI can extract early learning standards at scale. But production data quality requires human oversight and engineering to make that oversight fast enough for realistic usage.",
    url: "https://medium.com/@emilycheyne/why-a-human-verification-layer-is-necessary-in-addition-to-the-ai-pipeline-ef1509d0a668",
  },
  {
    title: "The Case for a National Early Learning Data Layer",
    description:
      "Exploring the implications of every early learning standard in America being machine-readable, queryable, and interoperable, and why this scenario is closer than you might think.",
    url: "https://emilycheyne.medium.com/the-case-for-a-national-early-learning-data-layer-8bcd48e139f0",
  },
];
