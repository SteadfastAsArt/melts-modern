/**
 * Unit tests for scrubber-related pure logic functions.
 *
 * These functions are extracted inline since app.js is a vanilla script
 * (no module exports). The tests verify the logic independently.
 */
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Extracted pure functions (mirroring app.js logic)
// ---------------------------------------------------------------------------

/**
 * Detect new phases between two step results.
 * @param {string} prevPhases - "+" delimited phase string from previous step
 * @param {string} currPhases - "+" delimited phase string from current step
 * @returns {string[]} Array of new phase instance names
 */
function detectNewPhases(prevPhases, currPhases) {
  const prev = prevPhases ? prevPhases.split("+").filter(Boolean) : [];
  const curr = currPhases ? currPhases.split("+").filter(Boolean) : [];
  const prevSet = new Set(prev);
  return curr.filter((p) => !prevSet.has(p));
}

/**
 * Strip trailing digits and capitalize a phase name for display.
 * @param {string} phase - e.g. "olivine1", "clinopyroxene2"
 * @returns {string} Display name e.g. "Olivine", "Clinopyroxene"
 */
function formatPhaseName(phase) {
  const baseName = phase.replace(/\d+$/, "");
  return baseName.charAt(0).toUpperCase() + baseName.slice(1);
}

/**
 * Compute liquid percentage from current and initial liquid mass.
 * @param {number} currentMass
 * @param {number} initialMass
 * @returns {string} Percentage string like "78.5" or "?" if invalid
 */
function computeLiquidPct(currentMass, initialMass) {
  if (!currentMass || !initialMass || initialMass === 0) return "?";
  return ((currentMass / initialMass) * 100).toFixed(1);
}

// ---------------------------------------------------------------------------
// Tests: detectNewPhases
// ---------------------------------------------------------------------------
describe("detectNewPhases", () => {
  it("returns empty array when phases are identical", () => {
    expect(detectNewPhases("olivine1+spinel1", "olivine1+spinel1")).toEqual([]);
  });

  it("detects a single new phase", () => {
    expect(
      detectNewPhases("olivine1+spinel1", "olivine1+spinel1+clinopyroxene1")
    ).toEqual(["clinopyroxene1"]);
  });

  it("detects multiple new phases", () => {
    expect(
      detectNewPhases("olivine1", "olivine1+spinel1+clinopyroxene1")
    ).toEqual(["spinel1", "clinopyroxene1"]);
  });

  it("handles empty previous phases", () => {
    expect(detectNewPhases("", "olivine1")).toEqual(["olivine1"]);
  });

  it("handles empty current phases", () => {
    expect(detectNewPhases("olivine1", "")).toEqual([]);
  });

  it("handles both empty", () => {
    expect(detectNewPhases("", "")).toEqual([]);
  });

  it("handles undefined/null gracefully", () => {
    expect(detectNewPhases(undefined, "olivine1")).toEqual(["olivine1"]);
    expect(detectNewPhases(null, "olivine1")).toEqual(["olivine1"]);
    expect(detectNewPhases("olivine1", undefined)).toEqual([]);
    expect(detectNewPhases(null, null)).toEqual([]);
  });

  it("ignores phase removal (not a new phase event)", () => {
    expect(
      detectNewPhases("olivine1+spinel1+clinopyroxene1", "olivine1+spinel1")
    ).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Tests: formatPhaseName
// ---------------------------------------------------------------------------
describe("formatPhaseName", () => {
  it("strips trailing digits and capitalizes", () => {
    expect(formatPhaseName("olivine1")).toBe("Olivine");
    expect(formatPhaseName("clinopyroxene2")).toBe("Clinopyroxene");
    expect(formatPhaseName("plagioclase1")).toBe("Plagioclase");
    expect(formatPhaseName("spinel1")).toBe("Spinel");
  });

  it("handles multi-digit suffixes", () => {
    expect(formatPhaseName("rhm-oxide12")).toBe("Rhm-oxide");
  });

  it("handles names without trailing digits", () => {
    expect(formatPhaseName("liquid")).toBe("Liquid");
  });

  it("handles single character names", () => {
    expect(formatPhaseName("a1")).toBe("A");
  });
});

// ---------------------------------------------------------------------------
// Tests: computeLiquidPct
// ---------------------------------------------------------------------------
describe("computeLiquidPct", () => {
  it("computes percentage correctly", () => {
    expect(computeLiquidPct(75, 100)).toBe("75.0");
  });

  it("returns ? for zero initial mass", () => {
    expect(computeLiquidPct(50, 0)).toBe("?");
  });

  it("returns ? for undefined values", () => {
    expect(computeLiquidPct(undefined, 100)).toBe("?");
    expect(computeLiquidPct(50, undefined)).toBe("?");
  });

  it("handles 100% liquid", () => {
    expect(computeLiquidPct(100, 100)).toBe("100.0");
  });

  it("handles near-zero liquid", () => {
    expect(computeLiquidPct(0.1, 100)).toBe("0.1");
  });
});
