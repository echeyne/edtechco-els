import type {
  Document,
  Domain,
  Strand,
  SubStrand,
  Indicator,
  HierarchyResponse,
  CreateDomainRequest,
  CreateStrandRequest,
  CreateSubStrandRequest,
  CreateIndicatorRequest,
  UpdateDomainRequest,
  UpdateStrandRequest,
  UpdateSubStrandRequest,
  UpdateIndicatorRequest,
  ReorderDomainsRequest,
  VerifyRequest,
  FilterQuery,
  ApiError,
} from "@els/shared";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// ---- Fetch wrapper ----

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null;
    const message = body?.error?.message ?? res.statusText;
    const err = new Error(message) as Error & {
      status: number;
      body: ApiError | null;
      sourceUrl?: string;
    };
    err.status = res.status;
    err.body = body;
    err.sourceUrl = (body?.error as Record<string, unknown> | undefined)
      ?.sourceUrl as string | undefined;
    throw err;
  }

  return res.json() as Promise<T>;
}

// ---- Read endpoints (public) ----

export function getDocuments(filters?: FilterQuery): Promise<Document[]> {
  const params = new URLSearchParams();
  if (filters?.country) params.set("country", filters.country);
  if (filters?.state) params.set("state", filters.state);
  const qs = params.toString();
  return request<Document[]>(`/api/documents${qs ? `?${qs}` : ""}`);
}

export function getHierarchy(documentId: number): Promise<HierarchyResponse> {
  return request<HierarchyResponse>(`/api/documents/${documentId}/hierarchy`);
}

export function getPdfUrl(
  documentId: number,
): Promise<{ url: string; expiresAt: string }> {
  return request<{ url: string; expiresAt: string }>(
    `/api/documents/${documentId}/pdf-url`,
  );
}

export function getFilters(): Promise<{
  countries: string[];
  states: string[];
}> {
  return request<{ countries: string[]; states: string[] }>("/api/filters");
}

// ---- Create endpoints (authenticated) ----

export function createDomain(
  data: CreateDomainRequest,
  token: string,
): Promise<Domain> {
  return request<Domain>(
    "/api/domains",
    { method: "POST", body: JSON.stringify(data) },
    token,
  );
}

export function createStrand(
  data: CreateStrandRequest,
  token: string,
): Promise<Strand> {
  return request<Strand>(
    "/api/strands",
    { method: "POST", body: JSON.stringify(data) },
    token,
  );
}

export function createSubStrand(
  data: CreateSubStrandRequest,
  token: string,
): Promise<SubStrand> {
  return request<SubStrand>(
    "/api/sub-strands",
    { method: "POST", body: JSON.stringify(data) },
    token,
  );
}

export function createIndicator(
  data: CreateIndicatorRequest,
  token: string,
): Promise<Indicator> {
  return request<Indicator>(
    "/api/indicators",
    { method: "POST", body: JSON.stringify(data) },
    token,
  );
}

// ---- Write endpoints (authenticated) ----

export function updateDomain(
  id: number,
  data: UpdateDomainRequest,
  token: string,
): Promise<Domain> {
  return request<Domain>(
    `/api/domains/${id}`,
    { method: "PUT", body: JSON.stringify(data) },
    token,
  );
}

export function deleteDomain(
  id: number,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    `/api/domains/${id}`,
    { method: "DELETE" },
    token,
  );
}

export function verifyDomain(id: number, data: VerifyRequest, token: string) {
  return request<{
    success: boolean;
    verifiedAt?: string;
    verifiedBy?: string;
  }>(
    `/api/domains/${id}/verify`,
    { method: "PATCH", body: JSON.stringify(data) },
    token,
  );
}

export function reorderDomains(
  data: ReorderDomainsRequest,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    "/api/domains/reorder",
    { method: "PUT", body: JSON.stringify(data) },
    token,
  );
}

export function updateStrand(
  id: number,
  data: UpdateStrandRequest,
  token: string,
): Promise<Strand> {
  return request<Strand>(
    `/api/strands/${id}`,
    { method: "PUT", body: JSON.stringify(data) },
    token,
  );
}

export function deleteStrand(
  id: number,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    `/api/strands/${id}`,
    { method: "DELETE" },
    token,
  );
}

export function verifyStrand(id: number, data: VerifyRequest, token: string) {
  return request<{
    success: boolean;
    verifiedAt?: string;
    verifiedBy?: string;
  }>(
    `/api/strands/${id}/verify`,
    { method: "PATCH", body: JSON.stringify(data) },
    token,
  );
}

export function updateSubStrand(
  id: number,
  data: UpdateSubStrandRequest,
  token: string,
): Promise<SubStrand> {
  return request<SubStrand>(
    `/api/sub-strands/${id}`,
    { method: "PUT", body: JSON.stringify(data) },
    token,
  );
}

export function deleteSubStrand(
  id: number,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    `/api/sub-strands/${id}`,
    { method: "DELETE" },
    token,
  );
}

export function verifySubStrand(
  id: number,
  data: VerifyRequest,
  token: string,
) {
  return request<{
    success: boolean;
    verifiedAt?: string;
    verifiedBy?: string;
  }>(
    `/api/sub-strands/${id}/verify`,
    { method: "PATCH", body: JSON.stringify(data) },
    token,
  );
}

export function updateIndicator(
  id: number,
  data: UpdateIndicatorRequest,
  token: string,
): Promise<Indicator> {
  return request<Indicator>(
    `/api/indicators/${id}`,
    { method: "PUT", body: JSON.stringify(data) },
    token,
  );
}

export function deleteIndicator(
  id: number,
  token: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(
    `/api/indicators/${id}`,
    { method: "DELETE" },
    token,
  );
}

export function verifyIndicator(
  id: number,
  data: VerifyRequest,
  token: string,
) {
  return request<{
    success: boolean;
    verifiedAt?: string;
    verifiedBy?: string;
  }>(
    `/api/indicators/${id}/verify`,
    { method: "PATCH", body: JSON.stringify(data) },
    token,
  );
}

// ---- Detail endpoints (public) ----

export interface DomainDetail extends Domain {}

export interface StrandDetail extends Strand {
  domain: Domain | null;
}

export interface SubStrandDetail extends SubStrand {
  strand: Strand | null;
  domain: Domain | null;
}

export interface IndicatorDetail extends Indicator {
  subStrand: SubStrand | null;
  strand: Strand | null;
  domain: Domain | null;
}

export function getDomain(id: number): Promise<DomainDetail> {
  return request<DomainDetail>(`/api/domains/${id}`);
}

export function getStrand(id: number): Promise<StrandDetail> {
  return request<StrandDetail>(`/api/strands/${id}`);
}

export function getSubStrand(id: number): Promise<SubStrandDetail> {
  return request<SubStrandDetail>(`/api/sub-strands/${id}`);
}

export function getIndicatorDetail(id: number): Promise<IndicatorDetail> {
  return request<IndicatorDetail>(`/api/indicators/${id}`);
}
