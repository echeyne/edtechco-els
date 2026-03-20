import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";

// Mock the db client before importing the route module
vi.mock("../../db/client.js", () => ({
  queryMany: vi.fn(),
  queryOne: vi.fn(),
}));

// Mock S3 (not used in hierarchy, but imported by documents.ts)
vi.mock("@aws-sdk/s3-request-presigner", () => ({
  getSignedUrl: vi.fn(),
}));
vi.mock("@aws-sdk/client-s3", () => ({
  S3Client: vi.fn(),
  GetObjectCommand: vi.fn(),
}));

import documents from "../documents.js";
import { queryMany, queryOne } from "../../db/client.js";

const mockedQueryOne = vi.mocked(queryOne);
const mockedQueryMany = vi.mocked(queryMany);

function createApp() {
  const app = new Hono();
  app.route("/api/documents", documents);
  return app;
}

/**
 * Property 1: Hierarchy Response Structure Completeness
 *
 * For any document in the database, when the hierarchy endpoint is called,
 * the response SHALL contain the document with all its domains, and each
 * domain SHALL contain all its strands, and each strand SHALL contain all
 * its sub_strands, and each sub_strand SHALL contain all its indicators,
 * with human_verified status present on all editable records.
 *
 * Validates: Requirements 1.2, 1.3
 */

// ---- Arbitraries for generating hierarchy data ----

const arbTimestamp = fc
  .integer({ min: 1577836800000, max: 1767225600000 }) // 2020-01-01 to 2025-12-31 in ms
  .map((ms) => new Date(ms).toISOString());

/** Generate a document DB row */
const arbDocumentRow = fc.record({
  id: fc.nat({ max: 10000 }),
  country: fc.stringMatching(/^[A-Z]{2}$/),
  state: fc.string({ minLength: 1, maxLength: 10 }),
  title: fc.string({ minLength: 1, maxLength: 100 }),
  version_year: fc.integer({ min: 2000, max: 2030 }),
  source_url: fc.oneof(
    fc.constant(null),
    fc.string({ minLength: 5, maxLength: 50 }),
  ),
  age_band: fc.string({ minLength: 0, maxLength: 10 }),
  publishing_agency: fc.string({ minLength: 0, maxLength: 50 }),
  created_at: arbTimestamp,
});

/** Generate a domain DB row for a given document_id */
function arbDomainRow(documentId: number, domainId: number) {
  return fc.record({
    id: fc.constant(domainId),
    document_id: fc.constant(documentId),
    code: fc.string({ minLength: 1, maxLength: 20 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    description: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 50 }),
    ),
    human_verified: fc.boolean(),
    verified_at: fc.oneof(fc.constant(null), arbTimestamp),
    verified_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
    edited_at: fc.oneof(fc.constant(null), arbTimestamp),
    edited_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
  });
}

/** Generate a strand DB row */
function arbStrandRow(domainId: number, strandId: number) {
  return fc.record({
    id: fc.constant(strandId),
    domain_id: fc.constant(domainId),
    code: fc.string({ minLength: 1, maxLength: 30 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    description: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 50 }),
    ),
    human_verified: fc.boolean(),
    verified_at: fc.oneof(fc.constant(null), arbTimestamp),
    verified_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
    edited_at: fc.oneof(fc.constant(null), arbTimestamp),
    edited_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
  });
}

/** Generate a sub_strand DB row */
function arbSubStrandRow(strandId: number, subStrandId: number) {
  return fc.record({
    id: fc.constant(subStrandId),
    strand_id: fc.constant(strandId),
    code: fc.string({ minLength: 1, maxLength: 40 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    description: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 50 }),
    ),
    human_verified: fc.boolean(),
    verified_at: fc.oneof(fc.constant(null), arbTimestamp),
    verified_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
    edited_at: fc.oneof(fc.constant(null), arbTimestamp),
    edited_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
  });
}

/** Generate an indicator DB row */
function arbIndicatorRow(
  domainId: number,
  strandId: number,
  subStrandId: number,
  indicatorId: number,
) {
  return fc.record({
    id: fc.constant(indicatorId),
    standard_id: fc.string({ minLength: 1, maxLength: 20 }),
    domain_id: fc.constant(domainId),
    strand_id: fc.constant(strandId),
    sub_strand_id: fc.constant(subStrandId),
    code: fc.string({ minLength: 1, maxLength: 50 }),
    title: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 50 }),
    ),
    description: fc.string({ minLength: 1, maxLength: 100 }),
    age_band: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 20 }),
    ),
    source_page: fc.oneof(fc.constant(null), fc.integer({ min: 1, max: 500 })),
    source_text: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 50 }),
    ),
    human_verified: fc.boolean(),
    verified_at: fc.oneof(fc.constant(null), arbTimestamp),
    verified_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
    edited_at: fc.oneof(fc.constant(null), arbTimestamp),
    edited_by: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 1, maxLength: 30 }),
    ),
    last_verified: fc.oneof(fc.constant(null), arbTimestamp),
    created_at: arbTimestamp,
  });
}

/**
 * Generate a complete hierarchy: a document row, plus arrays of domain/strand/
 * sub_strand/indicator rows with consistent foreign keys and unique IDs.
 */
const arbHierarchy = arbDocumentRow.chain((docRow) => {
  const docId = docRow.id;
  // Generate 0-3 domains
  return fc.integer({ min: 0, max: 3 }).chain((numDomains) => {
    const domainIds = Array.from(
      { length: numDomains },
      (_, i) => docId * 1000 + i + 1,
    );
    const domainArbs = domainIds.map((dId) => arbDomainRow(docId, dId));
    const domainsArb =
      domainArbs.length > 0
        ? fc.tuple(
            ...(domainArbs as [(typeof domainArbs)[0], ...typeof domainArbs]),
          )
        : fc.constant([] as Record<string, unknown>[]);

    return domainsArb.chain((domainRows) => {
      const domainArr = Array.isArray(domainRows[0])
        ? domainRows
        : (domainRows as unknown as Record<string, unknown>[]);
      const domainList =
        numDomains === 0 ? [] : (domainArr as Record<string, unknown>[]);

      // For each domain, generate 0-2 strands
      return fc
        .array(fc.integer({ min: 0, max: 2 }), {
          minLength: numDomains,
          maxLength: numDomains,
        })
        .chain((strandCounts) => {
          let strandIdCounter = docId * 100000;
          const strandsByDomain: { domainId: number; strandId: number }[] = [];

          for (let d = 0; d < numDomains; d++) {
            for (let s = 0; s < strandCounts[d]; s++) {
              strandIdCounter++;
              strandsByDomain.push({
                domainId: domainIds[d],
                strandId: strandIdCounter,
              });
            }
          }

          const strandArbs = strandsByDomain.map((s) =>
            arbStrandRow(s.domainId, s.strandId),
          );
          const strandsArb =
            strandArbs.length > 0
              ? fc.tuple(
                  ...(strandArbs as [
                    (typeof strandArbs)[0],
                    ...typeof strandArbs,
                  ]),
                )
              : fc.constant([] as Record<string, unknown>[]);

          return strandsArb.chain((strandRows) => {
            const strandList =
              strandsByDomain.length === 0
                ? []
                : (strandRows as unknown as Record<string, unknown>[]);

            // For each strand, generate 0-2 sub_strands
            const totalStrands = strandsByDomain.length;
            return fc
              .array(fc.integer({ min: 0, max: 2 }), {
                minLength: totalStrands,
                maxLength: totalStrands,
              })
              .chain((subStrandCounts) => {
                let ssIdCounter = docId * 10000000;
                const subStrandsByStrand: {
                  domainId: number;
                  strandId: number;
                  subStrandId: number;
                }[] = [];

                for (let s = 0; s < totalStrands; s++) {
                  for (let ss = 0; ss < subStrandCounts[s]; ss++) {
                    ssIdCounter++;
                    subStrandsByStrand.push({
                      domainId: strandsByDomain[s].domainId,
                      strandId: strandsByDomain[s].strandId,
                      subStrandId: ssIdCounter,
                    });
                  }
                }

                const ssArbs = subStrandsByStrand.map((ss) =>
                  arbSubStrandRow(ss.strandId, ss.subStrandId),
                );
                const ssArb =
                  ssArbs.length > 0
                    ? fc.tuple(
                        ...(ssArbs as [(typeof ssArbs)[0], ...typeof ssArbs]),
                      )
                    : fc.constant([] as Record<string, unknown>[]);

                return ssArb.chain((ssRows) => {
                  const ssList =
                    subStrandsByStrand.length === 0
                      ? []
                      : (ssRows as unknown as Record<string, unknown>[]);

                  // For each sub_strand, generate 0-2 indicators
                  const totalSubStrands = subStrandsByStrand.length;
                  return fc
                    .array(fc.integer({ min: 0, max: 2 }), {
                      minLength: totalSubStrands,
                      maxLength: totalSubStrands,
                    })
                    .chain((indicatorCounts) => {
                      let indIdCounter = docId * 1000000000;
                      const indicatorMeta: {
                        domainId: number;
                        strandId: number;
                        subStrandId: number;
                        indicatorId: number;
                      }[] = [];

                      for (let ss = 0; ss < totalSubStrands; ss++) {
                        for (let i = 0; i < indicatorCounts[ss]; i++) {
                          indIdCounter++;
                          indicatorMeta.push({
                            domainId: subStrandsByStrand[ss].domainId,
                            strandId: subStrandsByStrand[ss].strandId,
                            subStrandId: subStrandsByStrand[ss].subStrandId,
                            indicatorId: indIdCounter,
                          });
                        }
                      }

                      const indArbs = indicatorMeta.map((im) =>
                        arbIndicatorRow(
                          im.domainId,
                          im.strandId,
                          im.subStrandId,
                          im.indicatorId,
                        ),
                      );
                      const indArb =
                        indArbs.length > 0
                          ? fc.tuple(
                              ...(indArbs as [
                                (typeof indArbs)[0],
                                ...typeof indArbs,
                              ]),
                            )
                          : fc.constant([] as Record<string, unknown>[]);

                      return indArb.map((indRows) => {
                        const indList =
                          indicatorMeta.length === 0
                            ? []
                            : (indRows as unknown as Record<string, unknown>[]);

                        return {
                          docRow,
                          domainRows: domainList,
                          strandRows: strandList,
                          subStrandRows: ssList,
                          indicatorRows: indList,
                          // Metadata for assertions
                          strandsByDomain,
                          subStrandsByStrand,
                          indicatorMeta,
                        };
                      });
                    });
                });
              });
          });
        });
    });
  });
});

describe("Property 1: Hierarchy Response Structure Completeness", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("response contains complete nested hierarchy with human_verified on all records", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(arbHierarchy, async (hierarchy) => {
        const {
          docRow,
          domainRows,
          strandRows,
          subStrandRows,
          indicatorRows,
          strandsByDomain,
          subStrandsByStrand,
          indicatorMeta,
        } = hierarchy;

        // Mock queryOne to return the document
        mockedQueryOne.mockResolvedValue(docRow as never);

        // Mock queryMany calls in order: domains, strands, sub_strands, indicators
        mockedQueryMany
          .mockResolvedValueOnce(domainRows as never)
          .mockResolvedValueOnce(strandRows as never)
          .mockResolvedValueOnce(subStrandRows as never)
          .mockResolvedValueOnce(indicatorRows as never);

        const res = await app.request(`/api/documents/${docRow.id}/hierarchy`);
        expect(res.status).toBe(200);

        const body = await res.json();

        // 1. Document id matches
        expect(body.document.id).toBe(docRow.id);

        // 2. Number of domains matches
        expect(body.domains.length).toBe(domainRows.length);

        // 3. Each domain has human_verified as boolean
        for (const domain of body.domains) {
          expect(typeof domain.humanVerified).toBe("boolean");

          // 4. Each domain's strands count matches generated strands for that domain
          const expectedStrands = strandsByDomain.filter(
            (s) => s.domainId === domain.id,
          );
          expect(domain.strands.length).toBe(expectedStrands.length);

          for (const strand of domain.strands) {
            // 5. Each strand has human_verified as boolean
            expect(typeof strand.humanVerified).toBe("boolean");

            // 6. Each strand's subStrands count matches
            const expectedSubStrands = subStrandsByStrand.filter(
              (ss) => ss.strandId === strand.id,
            );
            expect(strand.subStrands.length).toBe(expectedSubStrands.length);

            for (const subStrand of strand.subStrands) {
              // 7. Each subStrand has human_verified as boolean
              expect(typeof subStrand.humanVerified).toBe("boolean");

              // 8. Each subStrand's indicators count matches
              const expectedIndicators = indicatorMeta.filter(
                (im) => im.subStrandId === subStrand.id,
              );
              expect(subStrand.indicators.length).toBe(
                expectedIndicators.length,
              );

              for (const indicator of subStrand.indicators) {
                // 9. Each indicator has human_verified as boolean
                expect(typeof indicator.humanVerified).toBe("boolean");
              }
            }
          }
        }
      }),
      { numRuns: 100 },
    );
  });
});
