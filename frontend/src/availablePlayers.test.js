import { describe, expect, it } from "vitest";
import { getIpl2026RosterTeam, getPlayerDirectoryTotals } from "./availablePlayers";

describe("player directory totals", () => {
  it("finds 2026 roster teams by normalized player name", () => {
    expect(getIpl2026RosterTeam("akeal hosein")).toBe("Chennai Super Kings");
    expect(getIpl2026RosterTeam("Unknown Player")).toBeNull();
  });

  it("counts a name shared across batting and bowling only once", () => {
    const baseline = getPlayerDirectoryTotals();
    const player = { name: "Unique Directory Test Player", player_id: "fixture-1" };

    const totals = getPlayerDirectoryTotals([player], [{ ...player }]);

    expect(totals.all).toBe(baseline.all + 1);
    expect(totals.available).toBe(baseline.available + 1);
    expect(totals.other).toBe(baseline.other + 1);
  });
});
