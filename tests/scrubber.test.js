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

/**
 * Find the index of the real data scatter trace for scrubber highlighting.
 * Boundary/line traces (hoverinfo "skip", no markers) must be ignored — on
 * TAS/AFM the first trace is a short boundary line, so the bounds check must
 * use THIS trace's length, not container.data[0].
 * @param {Array} traces - Plotly trace objects
 * @returns {number} index of the data scatter trace, or -1
 */
function findDataTraceIndex(traces) {
  for (let t = 0; t < traces.length; t++) {
    if (traces[t].hoverinfo !== "skip" && traces[t].mode && traces[t].mode.includes("markers")) {
      return t;
    }
  }
  return -1;
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

// ---------------------------------------------------------------------------
// Tests: findDataTraceIndex (scrubber highlight trace selection)
// ---------------------------------------------------------------------------
describe("findDataTraceIndex", () => {
  // Mimics a TAS figure: first traces are short boundary lines, then data scatter.
  const tasTraces = [
    { mode: "lines", hoverinfo: "skip", x: [41, 41] },          // boundary (2 pts)
    { mode: "lines", hoverinfo: "skip", x: [45, 49] },          // boundary (2 pts)
    { mode: "markers", x: new Array(20).fill(0), y: new Array(20).fill(0) }, // data (20 pts)
  ];

  it("skips boundary line traces and finds the data scatter", () => {
    expect(findDataTraceIndex(tasTraces)).toBe(2);
  });

  it("selected data trace is long enough to highlight mid-path steps", () => {
    // Regression: the old code gated on data[0].x.length (=2), skipping highlight
    // for every step beyond index 1 on TAS/AFM.
    const idx = findDataTraceIndex(tasTraces);
    expect(tasTraces[idx].x.length).toBe(20);
    expect(tasTraces[idx].x[15]).not.toBeUndefined();
  });

  it("finds the first trace when it is already a marker scatter", () => {
    const traces = [{ mode: "markers", x: [1, 2, 3] }];
    expect(findDataTraceIndex(traces)).toBe(0);
  });

  it("returns -1 when there is no marker trace", () => {
    expect(findDataTraceIndex([{ mode: "lines", hoverinfo: "skip", x: [1, 2] }])).toBe(-1);
  });
});
