# Vida — Hackathon Plan — Final Scope

**Deadline:** October 2, 2026, 11:59 PM PDT
**Category:** Daily Life Enhancement | **Lane:** Community
**Tags:** `#daily-life-enhancement` `#community`
**AWS Account:** 042170206023 | **Region:** us-east-1 | **Profile:** `--profile hackathon`
**Credits:** $100 initial + up to $100 earnable | **Free plan expires:** March 30, 2027

---

## Pitch

**"Vida connects what matters to you with the time you actually have. It creates a realistic plan, explains the trade-offs, and adjusts when your day changes."**

Upload one document. Pick your role. Vida extracts your context, builds a plan around your real availability, and adjusts it when life gets in the way. Two AI roles collaborate: a Planner proposes and a Reviewer challenges. Deterministic code blocks invalid schedules; the user accepts a feasible proposal before it becomes the plan.

**Killer demo moment:** Plan your day → drop in an unexpected meeting → watch Vida replan in seconds, explaining what moved and why.

---

## Architecture

```text
Browser → CloudFront → S3 frontend (private, OAC)
                   └→ /api/* → HTTP API → vida-api
                                           ├→ DynamoDB vida-main (3 GSIs)
                                           ├→ S3 presigned upload
                                           └→ async Invoke → vida-ai
                                                              ├→ Bedrock Nova Lite
                                                              └→ Managed KB Retrieve
Browser ← GET /api/jobs/{id} ← persisted job status/result
```

Two Lambdas only: `vida-api` handles sessions, CRUD, aggregation, plan acceptance and job submission; `vida-ai` is an internal worker. All public routes pass through vida-api. One DynamoDB table stores the twelve business entity types plus sessions, jobs, extractions, receipts, day state, plan references, activity events and usage counters. Detailed contracts and base SAM blueprint: [DESIGN.md](DESIGN.md).

**AI stack:**
- Primary: regional Bedrock Nova Lite (`amazon.nova-lite-v1:0`) through Converse.
- Retrieval: Bedrock **Managed Knowledge Base** with service-managed embeddings/storage/reranking; separate Retrieve then Converse.
- If KB is pending/unavailable: labelled, bounded context from the user's own documents.
- If model calls fail: bounded retry and visible failure; the last accepted schedule remains usable. Additional vendors are deferred until tested.

**Access check:** a real small Converse invocation in the intended account/role, followed by a managed KB and two-user retrieval test. A model catalog listing does not prove invocation access. No account upgrade or deployment is authorized by this design document itself.

**AWS services:** DynamoDB, Lambda, API Gateway, S3, CloudFront, Bedrock (including KB), IAM and CloudWatch Logs. Avoid counting a Bedrock feature twice for the submission.

---

## Feature Scope (MVP — what ships)

### P0: Must Ship

**0. Single-Shot Onboarding**

User picks a role (Student / Working Pro / Both / Other), drops one file (.md/.txt/.pdf). AI extracts their context and presents it in three groups before committing anything:

| Group | Example | User action |
|-------|---------|-------------|
| **Facts** | "You listed Python, graduated from X" | Pre-selected for review, editable |
| **Suggestions** | "This looks like a job-search goal" | Accept or dismiss |
| **Commitments** | "Submit assignment by October 3" | Only created if user confirms |

This prevents the "AI invented 25 tasks I never asked for" problem. The user sees exactly what Vida extracted, confirms what matters, and arrives at a dashboard that reflects their actual priorities.

**Upload flow:** S3 presigned URL (not base64 in JSON — avoids Lambda's 6MB payload limit). The client submits the server-issued doc_id after upload; a persisted job validates the owned object and processes it. No separate S3-triggered duplicate processing path.

**1. Today Page (Primary Destination)**

The first thing users see. Answers: "What should I do right now?"

- Next action card with estimated duration and "Why this?"
- Today's plan: time-blocked agenda with tasks placed in available slots
- Capacity bar: X min scheduled / Y min available
- Changes to review (if replan happened)
- Optional energy check-in (skip-able)
- Quick capture input at top

**2. Plan Page**

Where users manage their commitments. Answers: "What's coming, and what fits?"

- Agenda view (default): today/week timeline with tasks and calendar blocks
- List view: all tasks filterable by status, priority, goal, due date
- Goals section: progress bars, milestones, linked tasks
- Habits section: daily checklist with streaks
- Manual busy blocks: "I'm busy 2-4pm" → planner respects this

**3. Chat + Agent Pipeline**

Natural language interface accessible from every page. Handles:

- Simple actions: "add a task", "complete X", "I'm busy 3-5pm" → direct execution
- Planning requests: "plan my day", "what should I focus on?" → full agent pipeline
- Capture: "I applied to Acme today, need to practice SQL" → preserves the capture and proposes a task; dedicated job-application tracking is deferred
- Queries: "how am I doing on my goals?" → reads data + RAG, summarizes

**4. "My Day Changed" Replan (THE DEMO MOMENT)**

User says "I have an unexpected meeting 2-4pm" or "this task took longer than expected." Vida:
1. Recalculates available time
2. Preserves completed + locked work
3. Prefers keeping existing placements and moves only eligible future items
4. Shows a change summary: "Kept your deadline. Deferred practice; tomorrow remains a proposal. Buffer reduced."
5. User accepts or edits the revision

**5. End-of-Day Report**

Generated on demand (automatic schedules are deferred):
1. **Accomplishments:** completed planned + unplanned work
2. **Unfinished:** what didn't get done and why
3. **Comparison:** today vs yesterday using recorded evidence; baseline-plan completion and actual-time coverage shown separately
4. **Suggestion:** one improvement for tomorrow
5. **Tomorrow preview:** proposed adjustment to next day's plan

### P1: Ship If Time

**6. Progress Page** — completion stats, journal entries, basic trend view; the P0 daily report is accessible from Today
**7. Library Page** — uploaded documents list, upload more, source status; P0 onboarding still exposes the uploaded source status
**8. Journal** — quick daily entry, AI-generated activity summary

### Deferred (Post-Hackathon)

- Durable/recoverable user accounts and cross-device history
- Scheduled daily reports and reminders
- Dedicated job-application trackers and automatic notes-page organization
- Additional AI provider adapters
- Notion integration and sync
- Google Calendar integration
- Weekly/monthly/yearly reports
- Skill evidence tracking
- Communication drafts
- Multiple calendar providers
- Voice input
- Step Functions for async workflows

---

## Multi-Agent Pipeline

```
User Message
    │
    ▼
┌──────────────────┐
│  ROUTER (code)   │  Intent classification:
│                  │  → pattern match first (fast)
│                  │  → AI classify if ambiguous
└────────┬─────────┘
         │
    ┌────┴─────────────┐
    │                  │
    ▼                  ▼
  SIMPLE            PLANNING FLOW
  ACTION            ┌────────────────────────────────────┐
    │               │ 1. SNAPSHOT (code)                  │
    │               │    Load tasks, calendar, goals,     │
    │               │    availability, habits, doc text   │
    │               │                                     │
    │               │ 2. PLANNER (AI call — Nova Lite)    │
    │               │    Proposes: schedule, priorities,   │
    │               │    assumptions, deferred items      │
    │               │                                     │
    │               │ 3. REVIEWER (AI call — Nova Lite)   │
    │               │    Challenges: overload, missed     │
    │               │    deadlines, unrealistic estimates  │
    │               │    Max 1 repair cycle allowed        │
    │               │                                     │
    │               │ 4. FINAL VALIDATOR (code)            │
    │               │    Time conflicts? Dependencies?     │
    │               │    Capacity exceeded?                │
    │               │                                     │
    │               │ 5. PRESENT (persist job result)       │
    │               │    Valid draft + explanation + Accept │
    │               └────────────────────────────────────┘
    │                              │
    ▼                              ▼
┌───────────────────────────────────────┐
│  EXECUTOR (code only — sole writer)   │
│  Validates → Writes DynamoDB → Receipt│
└───────────────────────────────────────┘
```

**Key rules:**
- Agents propose. Only executor code commits user commitments; worker code may persist jobs, proposals and report drafts.
- Maximum one repair: Planner → Reviewer → optional Planner-fix → deterministic validation. Hard failures block Accept; there is no majority vote or unbounded debate.
- Validator is pure code: time math, conflict detection, dependency checks.
- Agents exchange bounded structured JSON. The snapshot builder supplies the read-only context; native model tool loops are deferred.

**Read-only tools (Planner + Reviewer):**
`get_profile`, `list_tasks`, `list_goals`, `get_calendar`, `get_habits`, `search_knowledge`, `get_stats`

**Write tools (Executor only):**
`create_task`, `update_task`, `create_goal`, `update_goal`, `create_habit`, `log_habit`, `add_journal`, `set_calendar_block`

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | React 18 + Vite + Tailwind CSS | Fast, tiny bundle, great DX |
| UI Components | shadcn/ui | Pre-built, dark/light themes, accessible |
| Backend | Python 3.12 + Lambda | Best boto3 support, fast for Bedrock |
| API | API Gateway HTTP API | Cheaper than REST API, JWT support |
| Database | DynamoDB (on-demand) | Serverless, eligible usage draws on remaining credits |
| AI (LLM) | Bedrock Nova Lite | Native AWS, tool calling, credits |
| AI failure handling | Bounded retry + visible job status | No untested cross-provider fallback |
| RAG | Bedrock Knowledge Base | Managed ingestion + retrieval |
| Hosting | S3 + CloudFront | Reliable, global CDN |
| IaC | AWS SAM | Simpler than CDK for this scope |
| Coding Agent | Claude Code + AWS Agent Toolkit | Required for hackathon |

---

## DynamoDB Schema (Summary)

**Table: `vida-main`** — Single-table design, PK: `USER#<id>`, SK varies by entity

| Entity | SK Pattern | Key Fields |
|--------|-----------|------------|
| Profile | `PROFILE` | name, role, phase, timezone, availability, planning_mode |
| Goal | `GOAL#<id>` | title, target_date, status, progress_pct, category, priority |
| Task | `TASK#<id>` | title, due_date, priority, status, goal_id, remaining_minutes |
| TimeBlock | `BLOCK#<id>` | date, start_time, end_time, block_type (busy/task/break), locked |
| Habit | `HABIT#<id>` | name, frequency, category |
| HabitLog | `HABITLOG#<date>#<habit_id>` | completed, date |
| Journal | `JOURNAL#<date>#<entry_id>` | entry_text, ai_summary, mood |
| ChatMsg | `CHAT#<session>#<ts>` | role, content, agent, tool_calls |
| Document | `DOC#<id>` | file_name, s3_key, extracted_text_s3_key, kb_status |
| DailyPlan | `PLAN#<date>#<revision>` | blocks, deferred, assumptions, status |
| DailyReport | `REPORT#<date>` | ai_narrative, accomplishments, comparison_yesterday, improvement_suggestion |
| Skill | `SKILL#<id>` | name, category, proficiency, source |

**GSI1:** `GSI1PK=USER#<id>`, `GSI1SK=GOALSTATUS#...|TASKSTATUS#...` — filter goals/tasks by status + date
**GSI2:** `GSI2PK=USER#<id>`, `GSI2SK=DATE#<date>#<entity_type>` — date-range queries across entities
**GSI3:** `GSI3PK=USER#<id>`, `GSI3SK=GOAL#<goal_id>#TASK#<task_id>` or `HABIT#<id>#LOG#<date>` — goal→tasks and habit→logs

Task SK uses a stable `TASK#<id>` (ULID) so reassigning a task to a different goal doesn't change its primary key. Goal→task relationship is tracked via GSI3.

Full schema with examples in [DESIGN.md](DESIGN.md).

---

## UI Structure

Four destination design + global Capture + Ask Vida. Today and Plan are P0; hide Progress/Library navigation until their P1 pages work. The P0 daily report remains accessible on Today. No duplicate task stores or separate chat-created task lists.

| Destination | User question | Contents |
|-------------|--------------|----------|
| **Today** | "What should I do now?" | Next action, daily plan, capacity, check-in |
| **Plan** | "What's coming?" | Agenda/list, goals, habits, calendar blocks |
| **Progress** | "How am I doing?" | Completion stats, journal, daily report |
| **Library** | "What does Vida know?" | Uploaded docs, source status |

**Global elements:** Capture button (quick task/thought), Ask Vida chat panel (side panel on desktop, full-screen on mobile), profile/settings.

---

## 48-Hour Timeline

### Day 1 — Wed Sep 30 (proposed sequence; adjust to actual remaining time)

| Block | Time | Tasks | Hours |
|-------|------|-------|-------|
| 1 | Now | Git init, SAM template, DynamoDB table, S3 buckets, IAM roles, verify Bedrock access | 2h |
| 2 | +2h | Shared Python layer: db.py, ai.py, prompts.py. CRUD Lambda (goals, tasks, habits, journal, calendar). API Gateway wiring. curl tests. | 4h |
| 3 | +6h | Onboarding across vida-api and vida-ai (presign, async extraction, review, atomic confirm). Bedrock KB setup. | 2h |
| 4 | +8h | Frontend scaffold: Vite + React + Tailwind + shadcn. Router. Layout (sidebar + header). Today page shell. | 2h |

### Day 2 — Thu Oct 1 (full day, ~16 hours)

| Block | Time | Tasks | Hours |
|-------|------|-------|-------|
| 5 | 9 AM | vida-ai worker with job leases and agent pipeline: Router → Planner → Reviewer → Validator → Executor. Tool implementations. | 4h |
| 6 | 1 PM | Frontend pages: Onboard, Today (full), Plan (agenda + list + goals + habits), Chat panel. Connect to API. | 4h |
| 7 | 5 PM | Replan flow: "my day changed" → recalculate → present diff → accept. End-of-day report generation. Dashboard aggregation. | 3h |
| 8 | 8 PM | Deploy: build frontend → S3 → CloudFront. Test full flow on public URL. Fix bugs. | 3h |
| 9 | 11 PM | Progress page, Library page, polish. Loading/error states. | 2h |

### Day 3 — Fri Oct 2 (deadline day)

| Block | Time | Tasks | Hours |
|-------|------|-------|-------|
| 10 | 9 AM | Bug fixes. End-to-end testing with sample profiles. Recheck session isolation implemented before private uploads. | 3h |
| 11 | 12 PM | Screenshots of Claude Code + AWS MCP connection. README. Builder Center post. | 2h |
| 12 | 2 PM | Demo recording (optional). Final deploy. Submission. | 2h |
| 13 | 4 PM+ | Monitor. Fix anything that breaks. Final check before 11:59 PM PDT. | buffer |

---

## Cost Controls and Remaining Checks

The email establishes **$100 starting credits**, with **up to $100 additionally earnable**; it does not establish the current balance. Free-plan expiry is **March 30, 2027 or credit exhaustion, whichever occurs first**. Verify actual service eligibility and remaining balance before provisioning. No-charge Free plan protection ends if the account is upgraded; credits running out can also make the application unavailable. [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

Use a **$15 prototype spending target**, with alerts at $5/$10/$15, plus application job/upload/session caps. A budget alert is a notification, not a hard spending stop. Do not promise a fixed <$10 total without measured inference input/output, retries, KB storage duration/query count, logs, and infrastructure usage. Managed KB pricing and regional model prices must be checked at setup. [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).

| Risk | Concrete mitigation |
|------|---------------------|
| Model/KB unavailable to this account | Invoke-test early; keep CRUD usable and label owned-text retrieval fallback |
| AI exceeds HTTP API's 30s limit | Persist job, invoke vida-ai asynchronously, poll job status |
| Replayed jobs or double Accept | Conditional leases + stable request keys + durable receipts |
| Draft stale or partially committed | Full current-state validation and one DynamoDB acceptance transaction |
| Replan loses completed work | Stable block IDs; frozen/history blocks excluded from replacement |
| Cross-user documents or demo collision | Server-issued bearer sessions; owned S3 mapping; mandatory RAG filter and two-user test |
| SPA rewrite hides API errors | Static-only CloudFront Function; cache disabled on /api/* |
| Weak progress comparison | Immutable activity events and baseline plans; missing time stays unknown |
| Deadline pressure | Finish P0 loop first; defer integrations/extra models/P1 pages |
| Judging availability | Check remaining credits, endpoint health and error logs through the judging window |

---

## Competitive Edge (Scoring Rubric)

**Technical Innovation (25%):** Multi-agent pipeline with bounded review, managed RAG, structured agent proposals, single-table DynamoDB, presigned uploads, replan flow.

**Implementation Quality (25%):** A focused AWS architecture, serverless, least-privilege IAM, structured JSON contracts between agents, deterministic validation, proper error states.

**Community/Market Impact (25%):** Real problem (juggling goals + career prep + coursework), works for any student or professional, community lane with ASU peers.

**Creativity & Storytelling (25%):** "Built during my Google interview prep, right after my Amazon internship. Vida is the assistant I wished I had." Real personal data flows through the system. Judges can try it with their own resume.

---

## Submission Template

Draft copy only: replace future-tense implementation claims with verified results, actual screenshots and real URLs before submitting. Confirm deadline/category/rubric against the event rules; those details were supplied in prior notes and are not re-verified here.

```
# Vida — Your AI Life Planning Assistant

## What it does
Upload your resume or a brain dump. Pick your role. Vida extracts your
context and builds a realistic daily plan around your actual availability.

When your day changes — an unexpected meeting, a task that ran long — Vida
replans in seconds, explaining what moved and why.

Two AI roles and deterministic application code handle planning:
- **Planner** proposes priorities and a schedule
- **Reviewer** challenges overload and missed deadlines
- **Validator (code)** blocks schedules that violate hard constraints
- **Executor (code)** commits only accepted, current proposals

## The problem
Students and professionals juggle dozens of commitments across career,
learning, health, and life. No tool connects all of these with AI that
knows your actual context and available time.

## How I built it
Built entirely with Claude Code connected to AWS via the Agent Toolkit
MCP Server. The coding agent handled infrastructure provisioning, Lambda
development, Bedrock configuration, and deployment — documented with
screenshots throughout.

## AWS services
- **Amazon CloudWatch Logs** — Operational diagnostics
- **Amazon Bedrock** (Nova Lite) — Bounded Planner/Reviewer calls
- **Bedrock Knowledge Bases** — Managed RAG over personal documents
- **Amazon DynamoDB** — Serverless data store (single-table design)
- **AWS Lambda** — Backend functions (Python 3.12)
- **Amazon API Gateway** — HTTP API
- **Amazon S3** — Frontend hosting + document storage
- **Amazon CloudFront** — Global CDN + public HTTPS URL
- **AWS IAM** — Least-privilege security

## My story
I'm an MSCS student at ASU (4.11 GPA) who just completed an SDE
internship at Amazon AWS. I built Vida because I was drowning in
spreadsheets and Notion pages trying to prepare for Google interviews
while managing coursework and side projects.

Vida is the assistant I wished I had — one that knows my context, respects
my time, and adjusts when plans inevitably change.

🔗 Live app: [CloudFront URL]
📦 Source: [GitHub URL]

#daily-life-enhancement #community
```
