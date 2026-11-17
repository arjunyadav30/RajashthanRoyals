import { describe, expect, it } from "vitest";
import { getPlayerDirectoryTotals } from "./availablePlayers";

describe("player directory totals", () => {
  it("counts a name shared across batting and bowling only once", () => {
    const baseline = getPlayerDirectoryTotals();
    const player = { name: "Unique Directory Test Player", player_id: "fixture-1" };

    const totals = getPlayerDirectoryTotals([player], [{ ...player }]);

    expect(totals.all).toBe(baseline.all + 1);
    expect(totals.available).toBe(baseline.available + 1);
    expect(totals.other).toBe(baseline.other + 1);
  });
});
