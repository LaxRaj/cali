import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Trackback } from "@/lib/data";
import { Trackbacks } from "./trackbacks";

const row = (o: Partial<Trackback>): Trackback => ({
  entity_type: "edge",
  entity_key: "fund|invested_in|acme",
  field: "invested_in",
  label: "Fund invested in Acme",
  value: "Fund invested_in Acme",
  source_url: "https://www.n.example/a",
  evidence: "Fund backed Acme",
  run_id: "20261001T000000Z",
  first_seen: "2026-10-01T00:00:00",
  last_seen: "2026-10-01T00:00:00",
  seen_count: 1,
  confidence: 1,
  ...o,
});

describe("Trackbacks", () => {
  it("renders nothing without rows", () => {
    const { container } = render(<Trackbacks rows={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a fact with its trust, evidence, source host and run link", () => {
    render(<Trackbacks rows={[row({})]} />);
    const connections = screen.getByRole("region", { name: "Connections" });
    expect(within(connections).getByText("Fund invested in Acme")).toBeInTheDocument();
    expect(within(connections).getByText("verified")).toBeInTheDocument();
    expect(within(connections).getByText("“Fund backed Acme”")).toBeInTheDocument();
    expect(within(connections).getByRole("link", { name: "n.example" })).toHaveAttribute("href", "https://www.n.example/a");
    expect(within(connections).getByRole("link", { name: "run 20261001T000000Z" })).toHaveAttribute("href", "/runs/20261001T000000Z");
  });

  it("lists every source of a fact and counts repeat sightings, without linking backfill runs", () => {
    render(
      <Trackbacks
        rows={[
          row({ seen_count: 3, last_seen: "2026-10-09T00:00:00" }),
          row({ source_url: "https://other.example/b", run_id: "backfill-2026-10-09", confidence: 0.4 }),
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: "other.example" })).toBeInTheDocument();
    expect(screen.getByText(/seen 3×/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /backfill/ })).not.toBeInTheDocument();
  });
});
