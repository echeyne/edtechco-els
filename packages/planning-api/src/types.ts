export interface PlanContent {
  sections: PlanSection[];
  summary: string;
}

export interface PlanSection {
  label: string;
  description?: string;
  activities: PlanActivity[];
}

export interface PlanActivity {
  title: string;
  description: string;
  indicatorCode: string;
  indicatorDescription: string;
  domain: string;
  strand?: string;
}

export interface PlanSummary {
  id: string;
  childName: string;
  childAge: string;
  state: string;
  duration: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface PlanDetail extends PlanSummary {
  interests: string | null;
  concerns: string | null;
  content: PlanContent;
}

export interface ChatRequest {
  message: string;
  sessionId?: string;
  planId?: string;
}

export type SSEEvent =
  | { event: "token"; data: { text: string; sessionId: string } }
  | { event: "plan"; data: { planId: string; action: "created" | "updated" } }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { message: string } };
