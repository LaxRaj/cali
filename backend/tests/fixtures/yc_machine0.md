[Home](https://www.ycombinator.com/home)›[Launches](https://www.ycombinator.com/launches)›machine0
# machine0: Cloud computers for AI agents
One command spins up a persistent VM. Your agent drives it via CLI or MCP, building its own fleet from 1 vCPU up to 60 vCPU / 240 GB and 8×H100s.
**Barnaby Malet**
3 months ago
Embed
<https://machine0.io>
#developer_tools#cloud_computing
TLDR: machine0 is a CLI for agent compute: “machine0 new mybox” gives your agent a full cloud VM, billed by the minute, from $0.013/hr up to 60 vCPU / 240 GB and 8×H100s. Agents drive it themselves via CLI or MCP.
<https://www.youtube.com/watch?v=gyllkZ0M04E>
## The Pain
Agent workloads are moving from ephemeral to always-on. A coding agent working on a hard feature runs 6-8 hours. Auto-research agents run for days. OpenClaw & Hermes run 24/7. As you run more in parallel:
  * **Resources** : a few agents on a big codebase saturate your RAM and CPU. Auto-research needs GPUs you don't have.
  * **Security** : “—yolo” on your personal machine is one prompt injection away from exfiltrated credentials.
  * **Availability** : close your laptop and the agent dies mid-task.
  * **Isolation** : there's no clean line between everything on your laptop and the minimum this agent actually needs.

## The Solution
machine0 gives every agent its own computer. It's a CLI that both humans and agents can use without reading docs:
  * “machine0 new mybox” creates an SSH-ready VM with a static IP and HTTPS endpoint. Always on (99.99% uptime) until you switch it off.
  * **Billed by the minute.** 1 vCPU / 1 GB at $0.013/hr up to 60 vCPU / 240 GB, plus GPUs from RTX 4000 Ada to 8×H100s.
  * **Profiles.** Bundles of MCP connections, credentials, prompts, and env vars, injected at VM creation. Each agent gets exactly the capabilities (or personality) you choose, and nothing else.
  * **Agents self-serve.** Hand the CLI or MCP server to Claude, Codex, or OpenCode and it manages its own fleet: spin up a box for a build, snapshot it, tear it down.
  * **Suspend & resume.** Pause an idle machine, stop paying for compute, resume exactly where it left off.
  * **Snapshot & clone.** Configure one machine perfectly, then stamp out ten identical agents from it.
  * **NixOS is first-class.** Declarative, reproducible machines.

## How people use it
  * **Compute for your agent** : give it the CLI and it spins up its own VMs for builds, tests, and long jobs instead of grinding your laptop.
  * **Hosting the agent itself** : run Claude, Codex or Hermes 24/7. Snapshot once, then clone as many as you want.
  * **Swarms of agents** : an orchestrator agent spawns worker machines, farms out subtasks, and tears them down when the work is done.
  * **Auto-Research on GPUs** : drop an agent on an H100 with a goal and let it run for days.

## About me
I'm a solo, second-time YC founder. I was CTO of Upflow (YC W20), where I scaled EPD post series A and personally owned DevOps, infra, and security for years because they were too high-stakes to delegate. Upflow handles sensitive accounting data for companies like Postman, ProductBoard, and Lattice, and is doing many millions in ARR.
Before that I built consumer payments at Hike Messenger (100M+ users) in India. Working with sensitive data and infra for years is what got me deep into the problems machine0 solves, security especially.
## Asks 🙏
  * Try it: <https://machine0.io>
  * Let's talk about your agent fleets, software factory or auto-research: hello@machine0.io