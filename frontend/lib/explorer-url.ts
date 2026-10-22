import { BUCKETS, type Bucket } from "./queue";

export type Sort = "priority" | "score" | "newest" | "connected" | "name";
export type View = "cards" | "table";
export const SORTS: Sort[] = ["priority", "score", "newest", "connected", "name"];

export type ExplorerState = {
  query: string;
  stage: string | null;
  tag: string | null;
  status: Bucket | null;
  linkedOnly: boolean;
  emailOnly: boolean;
  sort: Sort;
  view: View;
};

export const DEFAULT_STATE: ExplorerState = {
  query: "",
  stage: null,
  tag: null,
  status: null,
  linkedOnly: false,
  emailOnly: false,
  sort: "priority",
  view: "cards",
};

/** State from a query string; unknown or malformed values fall back to the defaults. */
export function parseExplorerState(search: string): ExplorerState {
  const p = new URLSearchParams(search);
  const sort = p.get("sort") as Sort;
  const status = p.get("status") as Bucket;
  return {
    query: p.get("q") ?? DEFAULT_STATE.query,
    stage: p.get("stage") || null,
    tag: p.get("tag") || null,
    status: BUCKETS.some((b) => b.key === status) ? status : null,
    linkedOnly: p.get("linked") === "1",
    emailOnly: p.get("email") === "1",
    sort: SORTS.includes(sort) ? sort : DEFAULT_STATE.sort,
    view: p.get("view") === "table" ? "table" : "cards",
  };
}

/** Query string (without the "?") holding only what differs from the defaults, so a clean view has a clean URL. */
export function serializeExplorerState(s: ExplorerState): string {
  const p = new URLSearchParams();
  if (s.query) p.set("q", s.query);
  if (s.stage) p.set("stage", s.stage);
  if (s.tag) p.set("tag", s.tag);
  if (s.status) p.set("status", s.status);
  if (s.linkedOnly) p.set("linked", "1");
  if (s.emailOnly) p.set("email", "1");
  if (s.sort !== DEFAULT_STATE.sort) p.set("sort", s.sort);
  if (s.view !== DEFAULT_STATE.view) p.set("view", s.view);
  return p.toString();
}
