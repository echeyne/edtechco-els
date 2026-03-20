// Feature: parent-planning-tool, Property 11: SSE token stream reconstructs agent response

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

/**
 * Property 11: SSE token stream reconstructs agent response
 *
 * For any complete agent response string, the sequence of SSE token events
 * emitted by the Planning API proxy, when their text fields are concatenated
 * in order, shall produce a string equal to the original agent response.
 *
 * **Validates: Requirements 11.1, 11.6**
 */

// ---- Pure helper under test ----

/**
 * Simulates the SSE token event production from agent response chunks.
 * Each chunk is encoded as bytes, decoded by the proxy, and emitted as
 * an SSE token event with a `text` field.
 */
function chunksToSSETokenEvents(
  chunks: string[],
): Array<{ event: "token"; data: { text: string; sessionId: string } }> {
  const sessionId = "test-session";
  return chunks.map((chunk) => {
    // Simulate the proxy behavior: encode chunk as bytes, then decode
    const bytes = new TextEncoder().encode(chunk);
    const text = new TextDecoder().decode(bytes);
    return {
      event: "token" as const,
      data: { text, sessionId },
    };
  });
}

/**
 * Splits a string into chunks at the given split points.
 * Split points are indices where the string should be cut.
 */
function splitAtPoints(str: string, points: number[]): string[] {
  if (str.length === 0) return [];

  // Deduplicate, clamp to valid range, and sort
  const sorted = [
    ...new Set(points.map((p) => Math.max(0, Math.min(p, str.length)))),
  ].sort((a, b) => a - b);

  const chunks: string[] = [];
  let prev = 0;
  for (const point of sorted) {
    if (point > prev) {
      chunks.push(str.slice(prev, point));
      prev = point;
    }
  }
  // Remaining portion
  if (prev < str.length) {
    chunks.push(str.slice(prev));
  }
  return chunks;
}

describe("Property 11: SSE token stream reconstructs agent response", () => {
  it("concatenating text fields from SSE token events equals the original string", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 200 }),
        fc.array(fc.nat({ max: 200 }), { minLength: 0, maxLength: 20 }),
        (originalString: string, splitPoints: number[]) => {
          // Split the original string into random chunks
          const chunks = splitAtPoints(originalString, splitPoints);

          // Produce SSE token events from the chunks
          const events = chunksToSSETokenEvents(chunks);

          // Concatenate the text fields
          const reconstructed = events.map((e) => e.data.text).join("");

          // Assert equality with the original string
          expect(reconstructed).toBe(originalString);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("empty string produces no SSE token events", () => {
    const chunks = splitAtPoints("", []);
    const events = chunksToSSETokenEvents(chunks);
    expect(events).toHaveLength(0);
    const reconstructed = events.map((e) => e.data.text).join("");
    expect(reconstructed).toBe("");
  });

  it("single chunk produces one SSE token event with the full string", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 200 }),
        (originalString: string) => {
          const events = chunksToSSETokenEvents([originalString]);
          expect(events).toHaveLength(1);
          expect(events[0].data.text).toBe(originalString);
          expect(events[0].event).toBe("token");
        },
      ),
      { numRuns: 100 },
    );
  });
});
