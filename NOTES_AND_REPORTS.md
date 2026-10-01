# Vida: notes, synchronization, and long-term reports

> **Scope note (finalized MVP):** [PLAN.md](PLAN.md) and [DESIGN.md](DESIGN.md) define the current implementation. This document retains review rationale and future-product ideas. Notion synchronization, scheduled reports and long-term trend views are deferred; DynamoDB is the hackathon source of truth.

Updated September 30, 2026, following the user's requirements for end-of-day reports, comparisons over months and years, free-form journal/chat capture, and notes-based tracking. “Google notes” is interpreted as Google Keep. Provider selection below is a recommendation; no connection, deployment, account upgrade, or external write has been performed.

**Recommendation: use Notion for the editable tracking workspace. Use its official hosted MCP for agent interaction and its API plus webhooks for application synchronization. Build reports from a timestamped activity history.**

## 1. AWS account update

The supplied AWS email establishes a starting grant of **USD $100**, an opportunity to earn **up to another USD $100**, and a Free plan expiry of **March 30, 2027 or credit exhaustion, whichever happens first**. This is not a live check of the remaining balance.

AWS documents no charges while the account remains on the Free plan, with restrictions on available services. At expiry, the account closes automatically unless upgraded; continued access is therefore relevant to a product intended to retain years of history. The old plan's “all services cost $0” assumption should be replaced with eligible usage covered by remaining credits and free allowances. [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

AWS lists Bedrock features as accessible using credits on both Free and Paid plans. This supports considering Bedrock again; it does not prove that every model, region, or retrieval configuration is enabled in this account. [AWS AI offers](https://aws.amazon.com/free/ai/).

Do not make AgentCore a prerequisite for the MVP: AWS's general Free Tier page labels it Paid-plan exclusive, while a separate limited-rollout signup-experience document lists it under that experience's Free Tier. Verify the actual account before relying on either description. The bounded agent workflow can remain in the planned application workers. [General Free Tier offers](https://aws.amazon.com/free/), [new signup experience service list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).

Before implementation, verify the account plan, remaining credits, region, and exact model access. Set usage limits for the public demo and monitor credits consumed, not just cash charges. Do not upgrade automatically. Add portable exports and a hosting-renewal decision before the Free plan expires; the email does not fund years of operation or third-party subscriptions.

## 2. Notion versus Google Keep

| Requirement | Notion | Google Keep |
|---|---|---|
| Reusable project/job pages | Strong fit for structured records with attached notes | Better suited to lightweight notes; less suitable for the proposed connected record model |
| Official hosted MCP | Yes, maintained by Notion | No official Google-hosted Keep MCP was established by this research; community servers exist |
| Updating existing content | Official MCP can create and update pages | Official Keep notes resource exposes create/get/list/delete, without a note-content update/patch method |
| Background integration | Public OAuth API connection and webhooks | Official API is oriented toward enterprise administration and delegated access |
| Months/years of reports | Suitable as a readable report archive, with separate structured history for calculations | Possible to store text summaries, but weaker for related records and evolving trackers |

Notion hosts its MCP server and exposes tools for workspace content and databases. Its OAuth connection is the preferred interactive agent route. [Notion MCP overview](https://developers.notion.com/guides/mcp/overview).

Google's official Keep API documentation describes an enterprise administration use case. Its notes method list has no content update operation, which directly conflicts with repeatedly appending to and updating an existing tracker page. [Keep API overview](https://developers.google.com/workspace/keep/api/guides), [Keep notes methods](https://developers.google.com/workspace/keep/api/reference/rest/v1/notes).

Community Keep MCP servers can offer broader editing. The inspected `feuerdev/keep-mcp` uses an unofficial private API through `gkeepapi` and a Google master token. That is a poor default dependency for a consumer application that should be easy for anyone to connect. This assessment concerns that implementation; it does not assert that every community connector works the same way. [keep-mcp implementation](https://github.com/feuerdev/keep-mcp).

Notion is not unrestricted on every plan. Some MCP search filters and query modes are restricted or metered, so inspect actual tool access and keep reporting independent of paid AI-search features. [Supported tools and plan access](https://developers.notion.com/guides/mcp/mcp-supported-tools).

Notion's documented REST block policy distinguishes single-member Free workspaces from multi-member Free workspaces, and the scope also depends on connection type. MCP has a separate enforcement policy. Verify the intended workspace and connection before promising unlimited automated notes. [Workspace block limits](https://developers.notion.com/reference/workspace-block-limits).

If “Google notes” means Google Docs, that is a different comparison. The Keep-specific API findings above do not apply to Docs.

## 3. MCP and background sync have different responsibilities

Use the maintained hosted endpoint `https://mcp.notion.com/mcp` when an agent needs to work interactively with Notion. It requires an initial interactive OAuth authorization. The older local `notion-mcp-server` package is no longer actively maintained. [Connecting to Notion MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp).

An application can maintain an authorized MCP connection and refresh tokens, but it must manage expiry, rotation, reconnects, permissions, and tool restrictions. Initial interactive authorization does not mean the user must be present for every later action. [Building a Notion MCP client](https://developers.notion.com/guides/mcp/build-mcp-client).

For Vida's scheduled reports and background synchronization, recommend a direct Notion API adapter. Use a public OAuth connection for a product with many users, or a scoped internal connection for a first personal prototype. A multiuser product must not share the developer's workspace credential. [Notion public connections](https://developers.notion.com/guides/get-started/public-connections).

Both entry points should feed the same domain validation and action rules. Expose narrow actions such as `find_application`, `record_application_update`, `complete_task`, and `publish_daily_report`; do not give every specialist an unrestricted page editor.

## 4. Notes-based tracking without duplicate databases

For the user's requested notes-based mode, make **Notion authoritative for editable tasks, job applications, projects, journal entries, and notes**. Vida displays those same records and writes back to them. AWS stores execution state, history, synchronization metadata, and derived retrieval/search data. A connected calendar remains authoritative for its external events.

This refines the earlier AWS-only storage proposal. Do not keep independently editable copies of task status in both Notion and DynamoDB. The AWS copy is a projection/cache with an explicit freshness marker. Unsynced local changes remain visibly pending until acknowledged.

| Data | Owner | AWS role |
|---|---|---|
| Task status, due dates, application stage | Notion records | Cached reads, validated command queue, change history |
| Journal and original note text | Selected Notion pages | Permission-aware retrieval projection, only when enabled |
| External event time and attendees | Calendar provider | Busy-time cache and provider ID mappings |
| Draft plan and execution state | Vida | Versioned proposals, validation, action receipts |
| Historical activity and metric snapshots | Vida | Structured reporting evidence, correction history, export |
| Generated report numbers and narrative | Vida-generated artifact | Versioned source snapshot; published Notion page with a separate user-reflection section |

Use a stable `vida_id` and retain each Notion `page_id` and data-source ID. A record edited through Vida is the same record opened in Notion. A job-specific task view filters the shared Tasks collection; it is not a copied checklist with a second status.

For people who do not use Notion, a later native-storage adapter can implement the same domain contract. Each workspace selects one authoritative backend; do not require multiple integrations during onboarding.

## 5. Workspace structure and page-creation rules

Create one Vida home page with linked views over these collections:

| Collection | What one record represents |
|---|---|
| Tasks | One action or routine occurrence; relates to a project/application when relevant |
| Projects | One bounded initiative, with an outcome and related tasks |
| Applications | One company + role + requisition/application, with stage and dated updates |
| Notes | One topic or useful reference, linked to relevant records |
| Journal | One dated entry; multiple entries per day can share a daily view |
| Reports | One report per user, period type, and period start; revisions update its generated section |

Show Jobs, Learning, or another area only when used. These are views and page templates, not new isolated data stores. The user should not have to understand the collection structure to capture a thought.

Rules for creating or reusing a page:

1. Check explicit linked IDs and existing source mappings first.
2. For applications, prefer requisition ID or canonical job URL plus company; the same company can have several unrelated applications.
3. Search existing topics and use semantic similarity to propose possible matches.
4. Update an existing record only when identity is sufficiently established. Ambiguous matches go to a small review inbox.
5. Create a new record only for a new entity or genuinely new topic. Do not create a topic page for every casual remark.
6. A new task becomes a row/page in Tasks and is linked to the existing project or application. Future discussion updates that task or adds a dated activity item.

## 6. Free-form chat and journal organization

Treat this as an intake workflow followed by retrieval when needed:

```text
Message or journal entry
  → preserve original text and timestamp
  → extract zero or more facts, actions, reflections, and questions
  → resolve existing entities and sources
  → validate intent, dates, permissions, and duplicates
  → apply authorized changes or retain suggestions
  → show a concise “Saved to…” receipt
  → refresh retrieval projections and report inputs
```

One message can relate to several destinations while retaining one original source. Use references or excerpts rather than copying the entire journal into every topic. Ordinary conversation can remain ordinary conversation; offer a temporary-chat mode and a “Don't save this” control.

Example, illustrative rather than user data:

> “I applied to Acme's backend role today. I need to practice SQL this week. I felt tired after work.”

| Extracted item | Destination | Treatment |
|---|---|---|
| Application submitted | Existing matching application, or one new application | Record a self-reported application event; do not claim a portal verified it |
| SQL practice | Tasks, linked to the relevant learning/project context | Capture the explicit intention under the user's chosen auto-organization policy; do not invent a hard deadline |
| Tired after work | Journal/check-in | Preserve as a dated self-report; use for planning only if the person enabled it |

Later: “Acme invited me to interview” should update the same application when the role is clear. If there are two Acme applications, clarify which one. “Maybe I should apply” remains a thought or suggestion, not an Applied status.

Default receipt: “Updated Acme application · Added SQL practice to Tasks · Saved today's reflection.” Each destination is clickable; provide Edit, Move, and Undo where reversible. Do not ask a separate confirmation for every routine note when the user has enabled automatic organization. Sending messages and invitations remains a separate permission.

## 7. Synchronization contract

Notion webhooks notify the application about changes; the application fetches the latest authorized content. Events are not a complete content snapshot. Validate webhook signatures, acknowledge receipt promptly, and process changes through a queue. [Notion webhooks](https://developers.notion.com/reference/webhooks).

Events can be delayed, aggregated, and delivered out of order. Use event IDs for deduplication, fetch current state, and reconcile periodically. Do not promise instantaneous synchronization or an exhaustive history of every intermediate Notion edit. [Webhook delivery behavior](https://developers.notion.com/reference/webhooks-events-delivery).

Suggested synchronization record: `connection_id`, `workspace_id`, `vida_id`, `notion_page_id`, `last_observed_edit_time`, `last_synced_hash`, `pending_operation_id`, `sync_status`, and `last_checked_at`.

Required behaviors:

- Serialize Vida writes per record and use operation IDs so retries do not create a second page or append an update twice.
- Before changing a mapped field, compare the last synchronized value with the current Notion value. Independent field edits may merge; conflicting edits require resolution.
- A pre-write check alone is not an atomic lock against someone editing in Notion. Verify writes and surface detected conflicts; avoid replacing whole user-authored pages.
- Write generated reports into a clearly owned section. Preserve user annotations separately when regenerating.
- Recognize your own completed writes to prevent webhook echo loops. Do not suppress genuine later edits merely because the same connection was involved.
- Handle deletion, archive, moved pages, and revoked access. Remove unavailable content from retrieval and dependent memory. Distinguish inaccessible from confirmed deleted.
- Show `Synced`, `Pending`, `Needs review`, or `Reconnect` with a last-checked time. A successful local save must not masquerade as a successful external write.
- Reconcile uncertain writes before retrying. Notion documents cases where a write saves but returns an error; blindly repeating it can duplicate content. Respect returned rate-limit delays. [API limits and write retries](https://developers.notion.com/reference/request-limits).

Calendar synchronization is a separate provider connection. A date property in Notion does not establish that an external calendar event exists.

## 8. End-of-day report

Make the daily review part of the core product. Generate it on demand and, when enabled, at the user's chosen local end-of-day time. Keep it in the app and optionally publish it to the selected Notion Reports collection. Email or chat delivery is a separate opt-in action.

The report should answer:

1. **What happened?** Completed planned tasks, completed unplanned work, meaningful outcomes, and logged practice.
2. **What changed?** Added commitments, moved tasks, unfinished work, blockers, and the user's stated reasons.
3. **How does it compare?** Today versus yesterday and a comparable recent baseline, with data coverage visible.
4. **What could improve?** One or two supported observations, expressed as testable suggestions.
5. **What should tomorrow account for?** A small proposal the user can accept, edit, or ignore.

Use evidence labels: confirmed application operation, user-reported activity, and AI interpretation. A completed task is not proof of a broader outcome; logging interview practice does not prove improved interview performance.

Avoid turning missing logs into failed days. Show “No activity recorded” where appropriate. If the person writes “I completed this yesterday,” retain both the activity date and the later recording date, then revise the affected report.

Use a report key such as `owner + day + local_date` and a revision number. Scheduled retries update the same report. Store the input cutoff and source versions so late information can trigger a visible correction rather than silently rewriting history.

## 9. Monthly and yearly improvement

| Horizon | Useful comparison |
|---|---|
| Daily | Actual outcomes, unfinished commitments, workload realism, one adjustment |
| Weekly | Similar weekdays, recurring blockers, effort estimates, goal balance |
| Monthly | Prior month and recent rolling baseline; completed milestones and repeated experiments |
| Quarterly | Project outcomes, skill evidence, changing priorities, sustainable routines |
| Yearly | Milestones and evidence over time, changed circumstances, lessons retained, next priorities |

Keep an append-oriented activity history with explicit correction/retraction events, subject to the user's deletion and retention choices. Capture at least `event_id`, `owner`, `entity_id`, `type`, `occurred_at`, `recorded_at`, `timezone`, `source`, `evidence_kind`, and correction linkage. For external changes whose exact occurrence time is unknown, store the observation time and uncertainty instead of inventing precision.

Retain the accepted start-of-day plan snapshot and later revisions. Otherwise moving an unfinished task out of today can artificially improve the completion rate. Show unplanned completed work separately from the original-plan completion measure. Reopened tasks and corrected activity must not be counted twice.

Calculate counts, durations, ratios, and comparisons in code. Let the model explain the computed metrics and linked evidence. Aggregate numerators and denominators before computing rates; do not average daily percentages blindly. Use actual time only when logged; a scheduled hour is not a measured hour of work.

Long-term metrics should reflect the person's goals: delivered project milestones, application-stage transitions, completed assessments, protected personal time, or reduced carryover. Raw task counts favor small tasks and are insufficient as a personal-growth score. For job-search conversion comparisons, use consistent application cohorts and allow time for responses.

Preserve changes in goal definitions, availability, and circumstances. Compare equivalent periods, display coverage, and distinguish correlation from causation. “Evening tasks were often deferred on logged workdays” can motivate a one-week morning experiment; it does not establish that the person is inherently unproductive at night.

Create an improvement loop: observation → chosen experiment → time window → result → keep/change/stop. Examples include shorter focus blocks or fewer daily commitments. Store these experiments so the assistant can learn what the individual found helpful without repeating generic advice.

Keep source events and structured period aggregates alongside narratives. Month and year reports must be able to recompute from evidence, not just summarize increasingly compressed AI summaries. Let users export their records, reports, and supporting metrics.

## 10. Practical release sequence

1. **Personal prototype:** one scoped Notion workspace, stable IDs, Tasks + Applications + Journal + Reports, manual Refresh, and clear sync status. Record activity and daily-plan snapshots immediately.
2. **Complete daily loop:** chat capture → reuse an existing page → complete a task → generate a sourced daily report → suggest a change for tomorrow. The user can correct every extracted item.
3. **Automatic synchronization:** webhooks, queued processing, retry reconciliation, conflict handling, deletion handling, and periodic refresh. Until this works, describe sync as manual rather than continuous.
4. **General onboarding:** each user authorizes their own workspace; data and retrieval stay isolated. Provide a sample/native demo for visitors without Notion.
5. **Long-term reports:** add weekly/monthly views first, then quarterly/yearly views as real history accumulates. Synthetic historical examples must be labeled as demonstrations.

Do not make every report period a separate agent. Use one reusable reporting workflow: collect evidence → calculate metrics → draft narrative → verify claims → publish through the authorized executor. Intake, planning, and reporting can share the same facts and entity references without sharing unrestricted write access.

Acceptance checks: repeated capture does not duplicate an application; similarly named roles stay separate; ambiguous dates are not invented; Notion edits appear after refresh; concurrent edits are surfaced; a report retry updates one page; late activity revises the proper period; revoked pages disappear from retrieval; missing days stay unknown; and monthly metrics match recomputation from source events.
