import { describe, it, expect } from "vitest";
import { preparePdfData } from "../PlanPdfDownload";
import type { PlanDetail } from "@/types";

/**
 * Unit tests for PlanPdfDownload — preparePdfData function
 *
 * Validates: Requirements 9.2
 */

const samplePlan: PlanDetail = {
  id: "plan-001",
  childName: "Emma",
  childAge: "4",
  state: "CA",
  duration: "2-weeks",
  status: "active",
  createdAt: "2025-01-15T10:00:00.000Z",
  updatedAt: "2025-01-15T12:00:00.000Z",
  interests: "dinosaurs and painting",
  concerns: "speech development",
  content: {
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
  },
};

describe("preparePdfData", () => {
  it("extracts child profile fields from the plan", () => {
    const result = preparePdfData(samplePlan);

    expect(result.childName).toBe("Emma");
    expect(result.childAge).toBe("4");
    expect(result.state).toBe("CA");
    expect(result.duration).toBe("2-weeks");
  });

  it("extracts the plan summary", () => {
    const result = preparePdfData(samplePlan);

    expect(result.summary).toBe(
      "A personalized 2-week learning plan for Emma.",
    );
  });

  it("flattens all activities from all sections", () => {
    const result = preparePdfData(samplePlan);

    expect(result.activities).toHaveLength(3);
  });

  it("preserves activity titles and descriptions", () => {
    const result = preparePdfData(samplePlan);

    expect(result.activities[0].title).toBe("Counting Snack Time");
    expect(result.activities[0].description).toBe(
      "Count crackers together before eating.",
    );
    expect(result.activities[1].title).toBe("Story Retelling");
    expect(result.activities[2].title).toBe("Nature Walk Shapes");
  });

  it("includes indicator codes and descriptions for every activity", () => {
    const result = preparePdfData(samplePlan);

    expect(result.activities[0].indicatorCode).toBe("MA.PK.1.2");
    expect(result.activities[0].indicatorDescription).toBe(
      "Count objects up to 10.",
    );
    expect(result.activities[1].indicatorCode).toBe("ELA.PK.2.1");
    expect(result.activities[1].indicatorDescription).toBe(
      "Retell familiar stories in sequence.",
    );
    expect(result.activities[2].indicatorCode).toBe("MA.PK.3.1");
    expect(result.activities[2].indicatorDescription).toBe(
      "Identify basic shapes in the environment.",
    );
  });

  it("includes domain and strand for each activity", () => {
    const result = preparePdfData(samplePlan);

    expect(result.activities[0].domain).toBe("Mathematics");
    expect(result.activities[0].strand).toBe("Number Sense");
    expect(result.activities[1].domain).toBe("English Language Arts");
    expect(result.activities[1].strand).toBeUndefined();
    expect(result.activities[2].domain).toBe("Mathematics");
    expect(result.activities[2].strand).toBe("Geometry");
  });

  it("tags each activity with its parent section label", () => {
    const result = preparePdfData(samplePlan);

    expect(result.activities[0].sectionLabel).toBe("Week 1");
    expect(result.activities[1].sectionLabel).toBe("Week 1");
    expect(result.activities[2].sectionLabel).toBe("Week 2");
  });

  it("handles a plan with a single section and single activity", () => {
    const minimal: PlanDetail = {
      ...samplePlan,
      content: {
        summary: "Quick plan.",
        sections: [
          {
            label: "Immediate",
            activities: [
              {
                title: "Sing ABCs",
                description: "Sing the alphabet song together.",
                indicatorCode: "ELA.INF.1.1",
                indicatorDescription: "Recognize letters of the alphabet.",
                domain: "English Language Arts",
                strand: "Phonics",
              },
            ],
          },
        ],
      },
    };

    const result = preparePdfData(minimal);

    expect(result.childName).toBe("Emma");
    expect(result.summary).toBe("Quick plan.");
    expect(result.activities).toHaveLength(1);
    expect(result.activities[0].sectionLabel).toBe("Immediate");
    expect(result.activities[0].indicatorCode).toBe("ELA.INF.1.1");
  });
});
