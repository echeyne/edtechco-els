import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import PlanDisplay from "../PlanDisplay";
import type { PlanContent } from "@/types";

const samplePlan: PlanContent = {
  summary: "A personalized 2-week learning plan for Emma.",
  sections: [
    {
      label: "Week 1",
      description: "Focus on number sense and literacy.",
      activities: [
        {
          title: "Counting Snack Time",
          description: "Count crackers together before eating.",
          indicatorCode: "MA.PK.1.2",
          indicatorDescription: "Count objects up to 10.",
          domain: "Mathematics",
          strand: "Number Sense",
        },
        {
          title: "Story Retelling",
          description: "Read a story and ask the child to retell it.",
          indicatorCode: "ELA.PK.2.1",
          indicatorDescription: "Retell familiar stories in sequence.",
          domain: "English Language Arts",
        },
      ],
    },
    {
      label: "Week 2",
      activities: [
        {
          title: "Nature Walk Shapes",
          description: "Find shapes in nature during a walk.",
          indicatorCode: "MA.PK.3.1",
          indicatorDescription: "Identify basic shapes in the environment.",
          domain: "Mathematics",
          strand: "Geometry",
        },
      ],
    },
  ],
};

describe("PlanDisplay", () => {
  it("renders the plan summary", () => {
    render(<PlanDisplay content={samplePlan} />);
    expect(
      screen.getByText("A personalized 2-week learning plan for Emma."),
    ).toBeInTheDocument();
  });

  it("renders all activity sections with labels", () => {
    render(<PlanDisplay content={samplePlan} />);
    const sections = screen.getAllByTestId("activity-section");
    expect(sections).toHaveLength(2);
    expect(screen.getByText("Week 1")).toBeInTheDocument();
    expect(screen.getByText("Week 2")).toBeInTheDocument();
  });

  it("renders section description when provided", () => {
    render(<PlanDisplay content={samplePlan} />);
    expect(
      screen.getByText("Focus on number sense and literacy."),
    ).toBeInTheDocument();
  });

  it("renders all activity cards", () => {
    render(<PlanDisplay content={samplePlan} />);
    const cards = screen.getAllByTestId("activity-card");
    expect(cards).toHaveLength(3);
  });

  it("renders activity titles and descriptions", () => {
    render(<PlanDisplay content={samplePlan} />);
    expect(screen.getByText("Counting Snack Time")).toBeInTheDocument();
    expect(
      screen.getByText("Count crackers together before eating."),
    ).toBeInTheDocument();
    expect(screen.getByText("Story Retelling")).toBeInTheDocument();
    expect(screen.getByText("Nature Walk Shapes")).toBeInTheDocument();
  });

  it("renders standard references with indicator codes", () => {
    render(<PlanDisplay content={samplePlan} />);
    expect(screen.getByText("MA.PK.1.2")).toBeInTheDocument();
    expect(screen.getByText("ELA.PK.2.1")).toBeInTheDocument();
    expect(screen.getByText("MA.PK.3.1")).toBeInTheDocument();
  });

  it("renders indicator descriptions", () => {
    render(<PlanDisplay content={samplePlan} />);
    expect(screen.getByText("Count objects up to 10.")).toBeInTheDocument();
    expect(
      screen.getByText("Retell familiar stories in sequence."),
    ).toBeInTheDocument();
  });

  it("renders domain and strand info", () => {
    render(<PlanDisplay content={samplePlan} />);
    // Domain text appears in multiple references
    expect(screen.getAllByText("Mathematics")).toHaveLength(2);
    expect(screen.getByText("English Language Arts")).toBeInTheDocument();
    // Strand appears when provided
    expect(screen.getByText("Number Sense")).toBeInTheDocument();
    expect(screen.getByText("Geometry")).toBeInTheDocument();
  });
});
