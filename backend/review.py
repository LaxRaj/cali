"""Local review screen: read each email, edit it, ask for changes, then press Send. Nothing is sent otherwise.

    uv run python review.py                              # then open the URL it prints
    uv run python review.py --test-to you@example.com    # rehearsal: every Send goes to YOUR address instead

Runs only on 127.0.0.1, checks the Host header, and every action needs the random token embedded in the page, so no
other website can trigger a send through your localhost. It is not part of the static Next.js dashboard.
"""

import argparse
import json
import secrets
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import draft_llm
import outreach

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outreach review</title><style>
:root{--bg:#faf8f4;--fg:#1d1b17;--mut:#6d675c;--line:#d9d3c7;--card:#fff;--acc:#c2410c;--ok:#166534;--bad:#b91c1c}
@media(prefers-color-scheme:dark){:root{--bg:#161411;--fg:#ece7dd;--mut:#9d9588;--line:#3a352d;--card:#1f1c18;--acc:#fb923c;--ok:#4ade80;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 Georgia,serif}
main{max-width:760px;margin:0 auto;padding:20px 16px 80px}h1{font-size:26px;margin:8px 0 2px}
.top{display:flex;gap:10px;flex-wrap:wrap;align-items:center;color:var(--mut);font:13px ui-monospace,monospace;margin-bottom:14px}
.banner{border:1px solid var(--acc);padding:8px 12px;margin:10px 0;font:13px ui-monospace,monospace}
.card{background:var(--card);border:1px solid var(--line);padding:16px;margin:14px 0}
.hd{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font:13px ui-monospace,monospace}
.badge{border:1px solid var(--line);padding:1px 8px}.meta{color:var(--mut);font-size:13px;margin:6px 0 10px}
input,textarea{width:100%;background:transparent;color:var(--fg);border:1px solid var(--line);padding:8px;font:inherit}
textarea{min-height:300px;resize:vertical;margin-top:8px}.row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.row input{flex:1;min-width:200px}button{font:13px ui-monospace,monospace;padding:7px 12px;border:1px solid var(--fg);background:transparent;color:var(--fg);cursor:pointer}
button.primary{background:var(--fg);color:var(--bg)}button:disabled{opacity:.45;cursor:default}
.warn{color:var(--bad);font:13px ui-monospace,monospace;margin-top:8px}.ok{color:var(--ok)}a{color:var(--acc)}
.small{font:12px ui-monospace,monospace;color:var(--mut)}
</style></head><body><main><h1>Outreach review</h1><div class="top" id="top"></div><div id="msg"></div><div id="list"></div></main>
<script>
const TOKEN="__TOKEN__";
const $=(id)=>document.getElementById(id);
function el(tag,props,...kids){const e=document.createElement(tag);Object.assign(e,props||{});for(const k of kids)e.append(k);return e}
async function api(path,body){const r=await fetch(path,{method:body?"POST":"GET",headers:{"X-Token":TOKEN,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  const j=await r.json();if(!r.ok)throw new Error(j.error||"request failed");return j}
function say(text,bad){const m=$("msg");m.replaceChildren(el("div",{className:"banner",style:bad?"border-color:var(--bad)":""},text))}
function card(it,st){
  const subject=el("input",{value:it.subject,"aria-label":"Subject"});
  const body=el("textarea",{value:it.body,"aria-label":"Email body"});
  const warn=el("div",{className:"warn"});const words=el("span",{className:"small"});
  const check=()=>{words.textContent=body.value.split(/\\s+/).filter(Boolean).length+" words";const open=body.value.match(/\\[[^\\]]+\\]/g);
    warn.textContent=open?"Fill in before sending: "+open.join(" "):(it.lint.length?"Needs a fix: "+it.lint.join("; "):"")};
  body.oninput=check;check();
  const fb=el("input",{placeholder:"Ask for changes, e.g. shorter, mention our SF meetup, softer opening"});
  const undo=el("button",{textContent:"Undo",disabled:!it.can_undo});
  const run=(btn,fn)=>async()=>{btn.disabled=true;try{await fn()}catch(e){say(e.message,true)}finally{btn.disabled=false}};
  const cur=()=>({key:it.key,subject:subject.value,body:body.value});
  const rewrite=el("button",{textContent:"Rewrite"});
  rewrite.onclick=run(rewrite,async()=>{if(!fb.value.trim())throw new Error("Type what to change first");await api("/api/revise",{...cur(),feedback:fb.value});say("Rewritten. Read it again; Undo restores your previous text.");load()});
  undo.onclick=run(undo,async()=>{await api("/api/undo",{key:it.key});load()});
  const save=el("button",{textContent:"Save edits"});
  save.onclick=run(save,async()=>{await api("/api/save",cur());say("Saved.");load()});
  const reject=el("button",{textContent:"Reject"});
  const block=el("input",{type:"checkbox",style:"width:auto"});
  reject.onclick=run(reject,async()=>{await api("/api/reject",{key:it.key,block_domain:block.checked});load()});
  const send=el("button",{className:"primary",textContent:st.test_to?"Send test copy to "+st.test_to:"Send"});
  let armed=0;
  send.onclick=run(send,async()=>{
    if(!armed){armed=setTimeout(()=>{armed=0;send.textContent=st.test_to?"Send test copy to "+st.test_to:"Send"},5000);send.textContent="Click again to send to "+(st.test_to||it.to);return}
    clearTimeout(armed);armed=0;const r=await api("/api/send",cur());say(r.result);load()});
  const src=it.to_source_url?el("a",{href:it.to_source_url,target:"_blank",rel:"noreferrer",textContent:"address published here"}):"";
  return el("section",{className:"card"},
    el("div",{className:"hd"},el("strong",{textContent:it.company+" ("+it.kind.replace("_"," ")+")"}),el("span",{className:"badge",textContent:"score "+it.score+" · "+it.intent.replace("_"," ")+" · "+(it.status==="approved"?"approved":"needs your review")})),
    el("div",{className:"meta"},"To: "+it.to+" (",src,")"+(it.reasons.length?" · Why: "+it.reasons.join("; "):"")+(it.signals.length?" · Signal: "+it.signals.join("; "):"")+(it.review_note?" · Held back: "+it.review_note:"")),
    subject,body,el("div",{className:"row"},words),warn,
    el("div",{className:"row"},fb,rewrite,undo),
    el("div",{className:"row"},save,send,reject,el("label",{className:"small"},block," also block this company's domain")))}
async function load(){
  const [st,list]=await Promise.all([api("/api/status"),api("/api/items")]);
  $("top").replaceChildren(el("span",{textContent:"sent today "+st.sent_today+"/"+st.cap}),el("span",{textContent:st.paused?"AGENT PAUSED: "+st.reason:"agent ok"}),
    el("span",{textContent:st.llm?"rewrites: on":"rewrites: off (no GROQ_API_KEY)"}));
  const q=el("button",{textContent:"Find new emails to review"});q.onclick=async()=>{q.disabled=true;try{const r=await api("/api/queue",{});say("Queued "+r.added+" new email(s).");load()}catch(e){say(e.message,true)}};
  $("top").append(q);
  const tb=document.querySelector(".banner.test");if(tb)tb.remove();
  if(st.test_to)$("top").after(el("div",{className:"banner test",textContent:"REHEARSAL: every Send goes to "+st.test_to+" with [TEST] in the subject. Nothing is recorded and no startup is contacted."}));
  $("list").replaceChildren(...(list.items.length?list.items.map(i=>card(i,st)):[el("p",{textContent:"Nothing waiting for review. Use 'Find new emails to review'."})]));
  const sent=list.sent;if(sent.length)$("list").append(el("p",{className:"small",textContent:"Recently sent: "+sent.map(s=>s.company+" ("+s.status+")").join(", ")}));
}
load().catch(e=>say(e.message,true));
</script></body></html>"""


class ReviewApp:
    """The screen's logic, separate from HTTP so it can be tested directly."""

    def __init__(self, data_dir: Path = outreach.DB_DIR, test_to: str = "", svc=None, reviser=None, draft_fn=None):
        self.data_dir, self.test_to, self._svc = Path(data_dir), test_to, svc
        self.reviser = reviser or draft_llm.revise
        self.draft_fn = draft_fn
        self.token = secrets.token_urlsafe(24)

    def svc(self):
        if self._svc is None:
            import gmail_sync

            self._svc = gmail_sync.service()
        return self._svc

    @staticmethod
    def _split(key: str) -> tuple[str, str]:
        company, _, kind = key.rpartition("::")
        return company, kind

    def _item(self, key: str) -> dict:
        outbox = outreach.load_outbox(self.data_dir)
        canonical = outreach.item_key(*self._split(key))
        if canonical not in outbox:
            raise ValueError("unknown email")
        return outbox[canonical]

    def items(self) -> dict:
        outbox = outreach.load_outbox(self.data_dir)
        pending = sorted((i for i in outbox.values() if i["status"] in ("queued", "approved")), key=lambda i: i.get("priority", 0), reverse=True)
        view = lambda i: {  # noqa: E731
            "key": outreach.item_key(i["company"], i["kind"]), "company": i["company"], "kind": i["kind"], "to": i["to"],
            "to_source_url": i.get("to_source_url", ""), "subject": i["subject"], "body": i["body"], "intent": i.get("intent", ""),
            "status": i["status"], "score": i.get("score", 0), "reasons": i.get("reasons", []), "signals": i.get("signals", []),
            "lint": outreach.lint(i), "can_undo": bool(i.get("history")), "review_note": i.get("review_note", ""),
        }
        sent = sorted((i for i in outbox.values() if i["status"] in ("sent", "replied", "bounced")), key=lambda i: i["updated"], reverse=True)[:8]
        return {"items": [view(i) for i in pending], "sent": [{"company": i["company"], "status": i["status"]} for i in sent]}

    def status(self) -> dict:
        now = datetime.now().astimezone()
        outbox, state = outreach.load_outbox(self.data_dir), outreach.load_state(self.data_dir)
        return {"paused": state["paused"], "reason": state["reason"], "sent_today": outreach.sent_today(outbox, now), "cap": outreach.ramp_cap(outbox, now),
                "test_to": self.test_to, "llm": draft_llm.available()}

    def save(self, key: str, subject: str, body: str) -> dict:
        company, kind = self._split(key)
        outreach.update_item(company, kind, self.data_dir, subject=subject, body=body)
        return {"ok": True}

    def revise(self, key: str, subject: str, body: str, feedback: str) -> dict:
        company, kind = self._split(key)
        self.save(key, subject, body)  # revise exactly the text on screen, keeping what you typed undoable
        new = self.reviser(self._item(key), feedback)
        outreach.update_item(company, kind, self.data_dir, subject=new["subject"], body=new["body"], note=f"asked: {feedback[:80]}")
        return {"ok": True}

    def undo(self, key: str) -> dict:
        outreach.undo_edit(*self._split(key), self.data_dir)
        return {"ok": True}

    def reject(self, key: str, block_domain: bool = False) -> dict:
        outreach.reject(*self._split(key), self.data_dir, block_domain=block_domain)
        return {"ok": True}

    def send(self, key: str, subject: str, body: str) -> dict:
        company, kind = self._split(key)
        self.save(key, subject, body)  # what you see in the boxes is exactly what is sent
        try:
            return {"result": outreach.send_now(company, kind, self.data_dir, svc=self.svc(), to_override=self.test_to)}
        except RuntimeError as e:
            raise ValueError(str(e)) from e

    def queue(self) -> dict:
        profiles = outreach._read(self.data_dir / "profiles.json", [])
        draft_fn = self.draft_fn or outreach.make_draft_fn(self.data_dir)
        from draft import load_sender

        added = outreach.queue_from_profiles(profiles, self.data_dir, sender=load_sender(self.data_dir), draft_fn=draft_fn)
        return {"added": len(added)}


def make_handler(app: ReviewApp):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            pass

        def _allowed_host(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _reply(self, code: int, payload, ctype: str = "application/json") -> None:
            data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _authed(self) -> bool:
            return self._allowed_host() and secrets.compare_digest(self.headers.get("X-Token", ""), app.token)

        def do_GET(self):
            if not self._allowed_host():
                return self._reply(403, {"error": "bad host"})
            if self.path == "/":
                return self._reply(200, PAGE.replace("__TOKEN__", app.token), "text/html")
            if not self._authed():
                return self._reply(403, {"error": "bad token"})
            routes = {"/api/items": app.items, "/api/status": app.status}
            if self.path in routes:
                return self._reply(200, routes[self.path]())
            self._reply(404, {"error": "not found"})

        def do_POST(self):
            if not self._authed():
                return self._reply(403, {"error": "bad token"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                actions = {
                    "/api/save": lambda: app.save(body["key"], body["subject"], body["body"]),
                    "/api/revise": lambda: app.revise(body["key"], body["subject"], body["body"], body["feedback"]),
                    "/api/undo": lambda: app.undo(body["key"]),
                    "/api/reject": lambda: app.reject(body["key"], bool(body.get("block_domain"))),
                    "/api/send": lambda: app.send(body["key"], body["subject"], body["body"]),
                    "/api/queue": app.queue,
                }
                if self.path not in actions:
                    return self._reply(404, {"error": "not found"})
                self._reply(200, actions[self.path]())
            except (ValueError, KeyError) as e:
                self._reply(400, {"error": str(e) or "bad request"})
            except Exception as e:  # never leak a traceback page; the terminal shows what happened
                print(f"error: {type(e).__name__}: {e}")
                self._reply(500, {"error": f"{type(e).__name__}: {e}"})

    return Handler


def serve(app: ReviewApp, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=outreach.DB_DIR)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--test-to", default="", help="rehearsal: send every email to this address only")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    app = ReviewApp(a.data_dir, a.test_to)
    server = serve(app, a.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Review screen: {url}" + (f"  (REHEARSAL: sends go to {a.test_to})" if a.test_to else ""))
    if not a.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
