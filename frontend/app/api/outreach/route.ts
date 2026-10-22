import fs from "node:fs";
import { dataPath } from "@/lib/data";
import { eventLine, localWriteAllowed } from "@/lib/outreach-local";

/** Local-only write path: appends one event to backend/data/outreach.jsonl. Everywhere else it answers 403. */
function allowed(request: Request) {
  return localWriteAllowed(
    process.env,
    request.headers.get("host"),
    request.headers.get("origin"),
  );
}

export async function GET(request: Request) {
  return Response.json({ local: allowed(request) });
}

export async function POST(request: Request) {
  if (!allowed(request)) {
    return Response.json({ error: "local writes are off" }, { status: 403 });
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid json" }, { status: 400 });
  }
  const line = eventLine(body);
  if (!line) return Response.json({ error: "invalid event" }, { status: 400 });
  fs.appendFileSync(dataPath("outreach.jsonl"), `${line}\n`);
  return Response.json({ ok: true });
}
