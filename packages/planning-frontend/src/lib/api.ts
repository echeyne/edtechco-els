import type { PlanSummary, PlanDetail } from "@/types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// ---- Error type ----

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- Internal fetch wrapper for JSON endpoints ----

async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || `HTTP ${res.status}`, res.status);
  }

  return res.json() as Promise<T>;
}

// ---- WebSocket session ----

export interface SessionRequest {
  sessionId?: string;
  planId?: string;
}

export interface SessionResponse {
  url: string;
  sessionId: string;
  userId: string;
  expiresAt: number;
}

export async function getSessionUrl(
  body: SessionRequest,
  token: string,
): Promise<SessionResponse> {
  return request<SessionResponse>("/api/chat/session", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---- Plan CRUD endpoints ----

/** GET /api/plans — list plans for the authenticated user */
export function getPlans(token: string): Promise<PlanSummary[]> {
  return request<PlanSummary[]>("/api/plans", token);
}

/** GET /api/plans/:id — get full plan detail */
export function getPlan(id: string, token: string): Promise<PlanDetail> {
  return request<PlanDetail>(`/api/plans/${encodeURIComponent(id)}`, token);
}

/** DELETE /api/plans/:id — delete a plan */
export function deletePlan(
  id: string,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    `/api/plans/${encodeURIComponent(id)}`,
    token,
    { method: "DELETE" },
  );
}
