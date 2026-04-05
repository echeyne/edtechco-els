// Base types matching database schema

export interface Document {
  id: number;
  country: string;
  state: string;
  title: string;
  versionYear: number;
  sourceUrl: string | null;
  s3Key: string | null;
  ageBand: string;
  publishingAgency: string;
  createdAt: Date;
}

export interface Domain {
  id: number;
  documentId: number;
  code: string;
  name: string;
  description: string | null;
  order: number | null;
  humanVerified: boolean;
  verifiedAt: Date | null;
  verifiedBy: string | null;
  editedAt: Date | null;
  editedBy: string | null;
  deleted: boolean;
  deletedAt: Date | null;
  deletedBy: string | null;
}

export interface Strand {
  id: number;
  domainId: number;
  code: string;
  name: string;
  description: string | null;
  humanVerified: boolean;
  verifiedAt: Date | null;
  verifiedBy: string | null;
  editedAt: Date | null;
  editedBy: string | null;
  deleted: boolean;
  deletedAt: Date | null;
  deletedBy: string | null;
}

export interface SubStrand {
  id: number;
  strandId: number;
  code: string;
  name: string;
  description: string | null;
  humanVerified: boolean;
  verifiedAt: Date | null;
  verifiedBy: string | null;
  editedAt: Date | null;
  editedBy: string | null;
  deleted: boolean;
  deletedAt: Date | null;
  deletedBy: string | null;
}

export interface Indicator {
  id: number;
  standardId: string;
  domainId: number;
  strandId: number | null;
  subStrandId: number | null;
  code: string;
  title: string | null;
  description: string;
  ageBand: string;
  sourcePage: number;
  sourceText: string;
  humanVerified: boolean;
  verifiedAt: Date | null;
  verifiedBy: string | null;
  editedAt: Date | null;
  editedBy: string | null;
  lastVerified: Date | null;
  createdAt: Date;
  deleted: boolean;
  deletedAt: Date | null;
  deletedBy: string | null;
}

// API Response types — nested hierarchy

export interface DomainWithChildren extends Domain {
  strands: StrandWithChildren[];
  indicators: Indicator[];
}

export interface StrandWithChildren extends Strand {
  subStrands: SubStrandWithChildren[];
  indicators: Indicator[];
}

export interface SubStrandWithChildren extends SubStrand {
  indicators: Indicator[];
}

export interface HierarchyResponse {
  document: Document;
  domains: DomainWithChildren[];
}

// API Create request types

export interface CreateDomainRequest {
  documentId: number;
  code: string;
  name: string;
  description?: string | null;
}

export interface CreateStrandRequest {
  domainId: number;
  code: string;
  name: string;
  description?: string | null;
}

export interface CreateSubStrandRequest {
  strandId: number;
  code: string;
  name: string;
  description?: string | null;
}

export interface CreateIndicatorRequest {
  domainId: number;
  strandId?: number | null;
  subStrandId?: number | null;
  code: string;
  title?: string | null;
  description: string;
  ageBand?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
}

// API Update request types

export interface UpdateDomainRequest {
  code?: string;
  name?: string;
  description?: string | null;
  documentId?: number;
}

export interface ReorderDomainsRequest {
  /** Array of domain IDs in the desired display order */
  domainIds: number[];
}

export interface UpdateStrandRequest {
  code?: string;
  name?: string;
  description?: string | null;
  domainId?: number;
}

export interface UpdateSubStrandRequest {
  code?: string;
  name?: string;
  description?: string | null;
  strandId?: number;
}

export interface UpdateIndicatorRequest {
  code?: string;
  title?: string | null;
  description?: string;
  ageBand?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
  subStrandId?: number | null;
  strandId?: number | null;
}

export interface VerifyRequest {
  humanVerified: boolean;
}

export interface FilterQuery {
  country?: string;
  state?: string;
}

// API Error response

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
