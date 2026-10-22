import { describe, expect, it } from "vitest";
import type { Profile } from "./data";
import { foldOutreach } from "./outreach";
import { leadsToCsv, publishedEmails } from "./leads-csv";

const state = foldOutreach([], 0);
const lead = (over: Partial<Profile>): Profile =>
  ({
    slug: "acme",
    company_name: "Acme",
    score: 80,
    funding_stage: "seed",
    website: "https://acme.io",
    people: [{ name: "Ada L", role: "CEO", org: "Acme", evidence: "" }],
    email_draft: { to: "hi@acme.io", to_source_url: "https://acme.io/contact", subject: "s", body: "b", mailto: "" },
    ...over,
  }) as Profile;

describe("leadsToCsv", () => {
  it("writes a header and one row per lead with the published address and its source", () => {
    const csv = leadsToCsv([{ p: lead({}), s: state }], "https://cali.example").split("\n");
    expect(csv[0]).toBe("company,score,stage,status,next_due,to,to_source_url,contacts,website,profile");
    expect(csv[1]).toBe("Acme,80,seed,none,,hi@acme.io,https://acme.io/contact,Ada L,https://acme.io,https://cali.example/startups/acme");
  });

  it("quotes commas, quotes and newlines and defuses spreadsheet formulas", () => {
    const csv = leadsToCsv([{ p: lead({ company_name: '=HYPERLINK("x"), Inc\nLtd' }), s: state }]);
    expect(csv).toContain(`"'=HYPERLINK(""x""), Inc\nLtd"`);
  });

  it("leaves the address empty when none is published and lists only published ones", () => {
    const noMail = lead({ slug: "b", email_draft: undefined });
    expect(leadsToCsv([{ p: noMail, s: state }]).split("\n")[1]).toContain(",none,,,,Ada L,");
    expect(publishedEmails([{ p: lead({}) }, { p: noMail }])).toEqual(["hi@acme.io"]);
  });
});
