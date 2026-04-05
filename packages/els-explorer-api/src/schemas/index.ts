import { z } from "zod";

// --- Create Schemas ---

export const CreateDomainSchema = z.object({
  documentId: z.number().int().positive(),
  code: z.string().max(20),
  name: z.string(),
  description: z.string().nullable().optional(),
});

export const CreateStrandSchema = z.object({
  domainId: z.number().int().positive(),
  code: z.string().max(30),
  name: z.string(),
  description: z.string().nullable().optional(),
});

export const CreateSubStrandSchema = z.object({
  strandId: z.number().int().positive(),
  code: z.string().max(40),
  name: z.string(),
  description: z.string().nullable().optional(),
});

export const CreateIndicatorSchema = z.object({
  domainId: z.number().int().positive(),
  strandId: z.number().int().positive().nullable().optional(),
  subStrandId: z.number().int().positive().nullable().optional(),
  code: z.string().max(50),
  title: z.string().nullable().optional(),
  description: z.string(),
  ageBand: z.string().max(20).nullable().optional(),
  sourcePage: z.number().int().positive().nullable().optional(),
  sourceText: z.string().nullable().optional(),
});

// --- Update Schemas ---

export const UpdateDomainSchema = z.object({
  code: z.string().max(20).optional(),
  name: z.string().optional(),
  description: z.string().nullable().optional(),
  documentId: z.number().int().positive().optional(),
});

export const UpdateStrandSchema = z.object({
  code: z.string().max(30).optional(),
  name: z.string().optional(),
  description: z.string().nullable().optional(),
  domainId: z.number().int().positive().optional(),
});

export const UpdateSubStrandSchema = z.object({
  code: z.string().max(40).optional(),
  name: z.string().optional(),
  description: z.string().nullable().optional(),
  strandId: z.number().int().positive().optional(),
});

export const UpdateIndicatorSchema = z.object({
  code: z.string().max(50).optional(),
  title: z.string().nullable().optional(),
  description: z.string().optional(),
  ageBand: z.string().max(20).nullable().optional(),
  sourcePage: z.number().int().positive().nullable().optional(),
  sourceText: z.string().nullable().optional(),
  subStrandId: z.number().int().positive().nullable().optional(),
  strandId: z.number().int().positive().nullable().optional(),
});

// --- Verify Schema ---

export const VerifySchema = z.object({
  humanVerified: z.boolean(),
});

// --- Reorder Schema ---

export const ReorderDomainsSchema = z.object({
  domainIds: z.array(z.number().int().positive()).min(1),
});

// --- Filter Query Schema ---

export const FilterQuerySchema = z.object({
  country: z.string().length(2).optional(),
  state: z.string().max(10).optional(),
});

// --- Inferred Types ---

export type CreateDomainInput = z.infer<typeof CreateDomainSchema>;
export type CreateStrandInput = z.infer<typeof CreateStrandSchema>;
export type CreateSubStrandInput = z.infer<typeof CreateSubStrandSchema>;
export type CreateIndicatorInput = z.infer<typeof CreateIndicatorSchema>;
export type UpdateDomainInput = z.infer<typeof UpdateDomainSchema>;
export type UpdateStrandInput = z.infer<typeof UpdateStrandSchema>;
export type UpdateSubStrandInput = z.infer<typeof UpdateSubStrandSchema>;
export type UpdateIndicatorInput = z.infer<typeof UpdateIndicatorSchema>;
export type VerifyInput = z.infer<typeof VerifySchema>;
export type ReorderDomainsInput = z.infer<typeof ReorderDomainsSchema>;
export type FilterQueryInput = z.infer<typeof FilterQuerySchema>;
