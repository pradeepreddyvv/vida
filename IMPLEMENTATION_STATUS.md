# Vida implementation status — 2026-10-02

## AWS hosting completed

The user changed hosting preference to all AWS. https://dahb851px2bik.cloudfront.net is deployed and verified (homepage, project route, authenticated API). Backend code was refreshed while preserving runtime Google credentials. Notion client ID remains empty. See AWS_DEPLOYMENT.md for secure setup and exact callback URLs. Earlier Sites blockers below no longer apply to the requested hosting plan.

## Latest demo update

See DEMO_GUIDE.md for the current working demo. AWS backend is deployed successfully in the approved account. The local frontend at http://127.0.0.1:5175 uses it. Projects group real tasks and searchable notes. Live tests passed for persistence, cited RAG answers, proposal approval, plan generation and acceptance. Ten regression tests pass. Phone layout was inspected at 390 × 844. Earlier deployment notes below are historical: AWS target is resolved; Sites registration and OAuth credentials remain unresolved.

Plan acceptance now uses a transaction with existing-record checks and deletes obsolete planner blocks. Full protection against a newly inserted concurrent commitment and durable sign-in remain follow-up work. Only stored tasks are scheduled; new block IDs are server-generated.


## Confirmed product decisions

- First release prioritizes Notion and Google Calendar synchronization.
- Laptop chat is a wide, resizable right panel beside the current page.
- AI task and calendar changes require a visible proposal and explicit approval.
- Sites is the requested frontend host; AWS remains the backend.

## Local implementation

The proposed Sites frontend lives in `sites/vida`; the prior frontend remains in `frontend`. The new interface includes persistent chat mounting, keyboard and pointer resizing, source passages, approval cards, honest connection failures, document-processing polling, and sync progress/error reporting.

Backend changes include owner-scoped passage retrieval, strict session-token lookup, proposal confirmation, numeric DynamoDB normalization, paginated seven-day primary-calendar import with timezone/midnight handling, and resumable nested Notion page imports. Sync operations use a per-provider lease. OAuth state consumption checks provider and expiration atomically. Changed calendar dates with existing plans are returned for separate draft generation; Settings starts those jobs without accepting the drafts.

Notion sync is an import, not bidirectional editing. Calendar imports are bounded to the next seven days. Notion import batches are bounded; select Sync again when partial. Search uses lexical passage ranking, not an embedding index. Disconnecting Notion excludes its imported documents from chat retrieval; this is not deletion of stored imported data.

## Verification

- `sites/vida`: production build passed.
- Python source compilation passed.
- Seven tests passed in `backend/tests/test_sync_and_approvals.py`, using mocked AWS and provider responses: numeric storage, authentication, owner-only/idempotent approval, retrieval isolation, calendar pagination/midnight/deletion, nested/paginated Notion content, and OAuth provider mismatch.
- Existing backend URL failed to connect in the local browser preview. No successful live end-to-end integration test is claimed.
- Optional WebMCP navigation is implemented but not verified in a supported browser context.

## Deployment blockers

AWS sign-in succeeded as account `237226121208`, role `AccountFullAccessRole`. Listing Lambda functions in `us-east-2` returned none. User clarification is pending on whether to deploy anew there or authenticate to the existing Vida account. No cloud resources were changed in this continuation.

Sites registration returned an internal error without a site ID or deployment credential. An owner-site listing did not include Vida. No hosted Vida URL was produced; unrelated existing Sites were not modified.

## Still required before release

1. Resolve the AWS target and Sites registration, then configure the actual frontend origin, callback origin, and OAuth applications securely.
2. Verify real Notion/Calendar connection, sync, source-grounded AI answers, and confirmed calendar writes.
3. Finish a comprehensive planner review: acceptance still uses nontransactional batch writes and needs stale-plan checks, replacement of obsolete planner blocks, and conflict validation against current calendar data.
4. Validate proposal field constraints and stale external-calendar actions more deeply before exposing all calendar mutations publicly.
5. Add Notion removed/revoked-page reconciliation and test interrupted/concurrent import recovery. Imported content can otherwise remain stale while a connection is active.
6. Replace temporary browser sessions with durable account access for a long-lived personal workspace; do not describe the current session flow as production authentication.
7. Verify laptop/mobile layouts against a working backend and perform live end-to-end tests. Local build/tests do not establish deployment readiness.

Existing edits from other work were preserved. This is a partial implementation, not a declaration that the entire project has been reviewed or completed.

## Calendar-first planning update — 2026-10-02

- Google connection, explicit calendar selection, and completed sync gate the workspace. Picker requires the added calendar-list read-only scope, so existing connections must reconnect.
- Calendar imports cover selected calendars for the next seven days, with source-aware event IDs, recurring occurrences, timezone conversion, midnight splitting, and conservative busy-time protection.
- Plan shows commitments, sync time, available minutes, explicit focus-task selection, and editable hours. User chooses priorities; no inferred tasks are scheduled.
- Chat `plan_day` and both Plan generation routes use one planner, with deterministic conflict checks and a per-workspace worker lease. Drafts require acceptance; accepted plans change Vida blocks, not Google events.
- Pages listen for confirmed chat changes. Regeneration refreshes Google first. Acceptance checks the stored calendar snapshot against current imported blocks.
- Notion/provider unreadable JSON now gets a bounded retry for read requests and an actionable error. Exact user-reported failure was not located in current AWS logs; actual user Notion sync remains to be retried.
- Validation: 15 backend tests, frontend production build, SAM build. Live API checks verify calendar prerequisite and OAuth picker scope. Real Google consent/calendar selection and Notion sync require the user's connected account.
- Limits: seven-day import window, manual sync outside draft generation; no continuous push synchronization. External calendar edits since the last import are only visible after the next sync. Calendar write proposals still require separate approval.


## Deployed assistant and search update — 2026-10-02

This update supersedes the earlier deployment blockers above. Vida is hosted at https://dahb851px2bik.cloudfront.net in account 237226121208, us-east-2.

- Deployed sidebar demo prompts and approved actions for local tasks/notes/focus, Google Calendar events, scoped Notion edits, and public web research.
- Tavily configured server-side. Live test passed: actual AI query proposal, approval, Tavily request, four HTTPS sources and cited answer. Basic search limits each request to four results; date/topic filters support recent research.
- Live isolated tests passed for source-grounded saved-note answers, task creation only after approval, and repeat-approval idempotence.
- 24 backend tests and production frontend/SAM builds pass. Expected simulated storage-failure log in tests is deliberate.
- Notion create/append/rename/text-only replacement paths have automated coverage, but live write verification remains blocked: the user-authorized “Vida demo test” page is absent from the synced catalog. Share/sync it or name a shared parent. No arbitrary existing page was edited.
- Page-name resolution instructions allow clear typo matches, identify the actual destination, and ask when ambiguous; this is model behavior backed by owner-scoped exact page IDs and approval, not a guaranteed fuzzy-search algorithm.
- Retrieval is lexical passage search, not vector embeddings. Notion replacement is restricted to small plain-text pages; nested/rich pages need append or provider editing. No claim of unrestricted page editing or production account authentication.

- Follow-up: live empty-catalog testing exposed invented Notion page names in model text (no external write). Empty Notion catalog requests now bypass the model with share/sync instructions; listing pages uses server-rendered catalog titles. 25 tests pass including this regression.

- Added OAuth private workspace Notion page creation (parent workspace=true), preserving approval and owner-bound indexing. 27 tests pass. A regression covers model-echoed status objects: their inner action becomes a fresh validated pending proposal; the model status is never authoritative. Live creation verification is in progress.

- Live Notion verification PASSED: created private page “Vida demo test” (3ee8f0c5-429a-8190-9d10-cc0171514360), user approved the preview, provider result recorded and indexed; approved append also completed with the real page ID. Earlier model-invented IDs were rejected before writes. Exact ID selection was needed after the contaminated earlier history; automatic fuzzy page resolution is not claimed verified. Screenshot: vida-notion-verified.png.

## Background batch execution — 2026-10-02

- Isolated vida-workflows CloudFormation stack created: Standard Step Functions Map (two workers), scoped execution role and API start permission, EventBridge bus/rule and Lambda subscriber. AWS definition validation and cfn-lint passed.
- One approval submits the saved batch to the server; workers check saved ownership/approval, claim each action and preserve individual outcomes. Repeat batch approvals reuse a deterministic execution name. Per-resource leases replace the global lock only for this execution path.
- Pub/sub writes deduplicated activity notices; UI fetches authoritative state and notices every eight seconds. This is not WebSocket push. Steps needing a new dependent resource still require a later reviewed action.
- 38 backend tests pass, frontend and SAM build pass. Live bulk smoke verification pending.
- Actual Notion page read-back verified the repaired exercise and senior SDE reminder. Existing calendar duplicates were not deleted.

- Live background smoke PASSED: actual AI created two stored proposals; one API approval started Step Functions; both steps finished with no per-action browser calls; two EventBridge subscriber notices were observed; repeated approval returned the same workflow without duplicate work. This test used an isolated workspace with a task and note. Live Google and Notion mutations were tested separately, not as a single concurrent provider batch.

## Live Google Calendar + Notion batch test

- Initial single prompt exposed model omission of the Notion action. Added a bounded structured repair and fail-closed destination completeness check for explicit cross-provider write requests; 39 tests pass. This is a focused guard, not universal natural-language intent completeness.
- Retest: one prompt updated existing “Vida two-app test” on October 3, 2026 from 11:30–11:40 to 11:45–11:55 America/Phoenix and appended a matching note to “Vida demo test”. Both saved proposals approved together; background activity showed 2/2 completed.
- Read-back: Google sync and October 3 Plan display show one Vida two-app test at 11:45–11:55. Reloaded actual Notion page shows the matching two-app workflow note. Screenshots: vida-two-app-verified.png and vida-two-app-notion.png. Test artifacts retained.
- Older Exercise events remain at both 10:00–11:00 and 18:00–19:00; this test did not remove those duplicates.

## Five-action live test

A single explicit five-item prompt produced five proposals and one approved background batch completed 5/5: two tasks (20-minute rehearsal and 15-minute README review), one local indexed decision note, one Notion append, and a Google Calendar test event on October 3, 2026 at 12:00–12:10 America/Phoenix. Read-back verified tasks in the Plan focus list, the note in Library, the appended text on the actual Notion page, and the event after Google sync. Test items are labeled and retained. Evidence: vida-five-items-verified.png. This validates the explicit five-item case, not arbitrary unstructured brainstorming.

## Notion task and habit mirror (2026-10-02)

Implemented one-way Vida → Notion synchronization in `shared/notion_mirror.py`.
New OAuth connections enqueue creation of private **Vida Tasks** and **Vida Habits** pages. Existing connections initialize through Settings → Notion → Sync. Successful task/habit API mutations and completed task workflow notifications queue an asynchronous mirror update. Onboarding confirmation also queues existing records.

Stable page mappings are scoped to Vida user and Notion workspace. Managed blocks carry per-record links; sync updates existing blocks and preserves unrelated notes. Task completion and dated habit check-ins are represented as checkboxes. Removing a task in Vida soft-archives its managed block. Ambiguous creation failures stop for review rather than blindly creating duplicates. Disconnection prevents subsequent worker writes; pages are retained. Settings exposes mirror state, error/retry instructions, and links.

Scope: this is not two-way synchronization; Notion checkbox/text edits do not modify Vida. No webhook subscription or new persistent AWS resource is added. Lambda asynchronous delivery retries failures; exhausted retries require Settings Sync. Large initial imports are bounded and may need additional sync attempts. Page creation interrupted before its ID is saved requires manual recovery rather than reconnecting. Unit suite: 47 passing checks including six mirror tests; live verification recorded after deployment.

Live verification: created Vida Tasks (3ee8f0c5429a8153b3b5e74b3f911734) and Vida Habits (3ee8f0c5429a810696ebd00b702d506f), inspected actual Notion contents, and confirmed an automatic habit check-in reached the managed page. Corrected habit API defaults to use the user's timezone and made Today send its displayed date explicitly. Regression suite now passes 48 tests.

Added persistent connection setup banner in AppShell: shows only missing Google Calendar / Notion connections, links to Settings sections, clears after both are connected, refreshes on navigation/focus/integration events. Today includes an expandable five-step productivity guide, initially expanded for an empty task list. Connected-account live page verifies the guide and absence of unnecessary setup prompts.

## Workflow validation and truthful receipts (2026-10-02)
Normalized integral task durations from integers, numeric strings, Decimal and integral floats; rejected booleans, fractions, non-finite and out-of-range values. Plain-text approval/clear commands now bypass generative replies and report only saved pending state or ask what should be cleared. Prose-only model output receives a bounded structured-proposal repair with conversation context. Cross-provider repair now includes prior user context. Fresh requests following a clear-all boundary do not inherit earlier demo instructions. Future calendar events outside the recorded sync window are blocked until availability can be verified. Regression suite: 52 checks passed. Completed external edits are preserved; old blocked cards are not silently executed or rewritten.

## Free-text request pipeline (2026-10-02)
Added `shared/request_pipeline.py`: structured intent classification, a saved per-session request, action planning, deterministic coverage/content/date/duration checks, and existing approval-backed execution. Unnumbered paragraphs are split into separate changes. Short email destination replies deterministically retain all items. Other continuations must preserve earlier item IDs and kinds. Completed/processing/uncertain steps are retained without re-execution. Questions fall through to existing retrieval/chat handling.

Classifier and planner each get at most one repair attempt; malformed output fails closed. Model prose does not approve or execute actions. The planner receives factual catalogs rather than competing output-format instructions. Explicit note contents/checklist entries are checked before creating proposals. Existing historical blocked cards are not automatically rewritten.

Validation: 62 unit checks passed; SAM build passed. Live Bedrock synthetic evaluation verified five unnumbered intentions, an email follow-up retaining all five, planner coverage with exact dates/durations and note contents, and a simple 30-minute laundry request for tomorrow. The October 17 calendar step correctly remained blocked against an October 2–9 import window. No external calendar or Notion writes were made during these checks. These are bounded examples, not proof of perfect classification. Maximum five changes and the current calendar import horizon remain in effect.
Deployment verified: both existing `vida-api` and `vida-ai` functions report Active/Successful and their deployed code hashes match the tested package. Infrastructure, credentials, and frontend were unchanged for this update. A fresh browser end-to-end approval/write test remains unperformed for this classifier release.

## October 24 free-text failure repair
Reproduced the user's exact paragraph against Bedrock: the classifier returned malformed JSON initially, then six valid intentions (including both a walk task and event). The former five-item ceiling rejected these and masked the cause with a generic error. Classification, fallback workflow parsing, proposal creation, and batch approval now consistently allow up to ten changes. Repair instructions distinguish a new request from a continuation instead of always urging continuation. No step is dropped to fit a preferred count.

Validation: 65 unit checks passed, including ten saved proposals accepted as one batch without executing before approval, overflow rejection, and malformed-output recovery. Live exact-prompt classification and planning succeeded with six intentions. The model proposed a future walk slot despite limited calendar coverage; existing deterministic proposal validation rejects events outside the imported window. No live calendar/Notion writes were made in this evaluation. The five-vs-six interpretation remains visible for user review; it is not silently forced. SAM build passed.

## Request visibility and interrupted-worker recovery
Added persisted job preparation stages (checking context, separating actions, preparing changes, validating/saving review cards) exposed through job polling and the activity endpoint. Chat shows the current stage while sending and recovers active-job status after navigation. Prior approved batches are labeled Previous results and collapsed when none are running. A second send is blocked locally when a known request is active; existing backend mutual exclusion remains.

The previous worker timeout was 90 seconds while its lock lasted 900 seconds. Worker timeout is now 180 seconds; job deadlines and decision locks use the actual remaining Lambda lifetime plus a ten-second safety margin. Interrupted jobs report an interruption after that deadline rather than appearing to run indefinitely. External actions are never automatically replayed. Legacy processing records without a deadline use the former runtime plus margin; pending jobs have a ten-minute observation deadline. Existing records are not deleted or silently executed.

Validation: 68 tests, frontend production build, and SAM build passed. Browser verification was blocked by the existing in-app browser connection timeout. No real calendar or Notion changes were made by this repair.

## Contextual priority replies and helpful defaults
Destination-picker replies following a task-priority question now repeat the actual open task choices instead of invoking classification or inferring edits. Simple exact task-name replies (with connective words such as first/then/please) resolve verified task IDs directly into a pending set_focus approval card. No duplicate task is created. Other replies continue through normal interpretation. Classifier now receives recent assistant questions as well as user text. Planner instructions encourage optional-field defaults, concise titles, unique catalog matching, and recommendations when the user asks it to choose, while retaining approval and real-ID/calendar validation.

70 unit tests passed. A live model check initially misclassified a priority reply as create_task; the direct task matcher addresses that case and its regression verifies no duplicate tasks or automatic priority writes. General-knowledge/default prompt changes are guidance, not a guarantee of arbitrary intent accuracy. After priority approval, draft generation still uses Plan; automatic dependent draft execution is not implemented here.

## Complete demo starting prompts
Rewrote all six chat demo prompts with explicit defaults, bounded outputs, missing-data handling, and approval instructions. Chores demo proposes two tasks plus a shopping note. Priorities demo uses saved focus or recommends up to three existing tasks, then guides to Plan after approval. Notion demo names the page and exact append text; calendar demo specifies tomorrow/30 minutes/5–8 PM and asks only when destination or availability is unresolved. Research demo supplies an explicit public query and source requirements. No prompt is auto-sent.

A live classifier smoke test of all six revised prompts passed after fixing question-mode outputs that contained valid write intents. Expected outputs: source lookup/question; chores/three actions; planning/question delegated to planner; Notion/append; scheduling/event; research/search. 71 regression tests passed; production frontend and SAM builds passed. This is classification/build coverage, not six end-to-end external write tests. Duplicate detection in these prompts remains an instruction to the model, not a universal cross-system deduplication guarantee. Browser visual verification remains unavailable due to the in-app browser connection timeout.

## Saturday brain-dump demo
Organize a brain dump now fills a five-section Saturday prompt: two chores, shopping note, Notion append, and a calendar walk, followed by explicit review-first instructions. The button fetches the saved timezone and computes the next strictly upcoming Saturday in JavaScript (browser timezone fallback if none is saved), replacing date/timezone placeholders before filling the editable draft. This avoids a reproduced model error where relative Saturday was resolved to a Friday. Users can edit the filled date before sending.

Three timezone/date checks passed, production build passed, and the live Bedrock classifier returned exactly two create_task intentions, one save_note, one notion_append, and one create_event, with October 3 as the explicit date. No additional walk task. No external writes or full browser execution were performed; actual Notion/calendar proposals remain subject to catalog/coverage checks and approval.

## Connected-workspace Saturday starter
Saturday is now the first demo button, labeled Organize my Saturday. Chat shows a starter invitation only when both calendar and Notion capabilities report connected. Load Saturday starter prepares an editable dated prompt; Not now dismisses the invitation. Dismissal/loading is remembered per session user ID in this browser. Capability status refreshes on panel visibility, window focus, and integration-change events. Existing drafts are protected before and after the date lookup. Nothing is sent or approved automatically. Production build passed; live visual verification remains blocked by the browser connection issue.

## Isolated judge/test entry
Added an onboarding dropdown (Sam/everyday, Maya/student, Alex/builder). Each click creates a new opaque-token workspace, not a shared account: three tasks, three habits, one project, three searchable notes, and seven days of clearly labeled sample commitments. Test sessions are 24 hours, not durable identity/login. No integration credentials are seeded or copied.

Test profiles carry a server-controlled sample flag. Google/Notion OAuth initiation, sync workers, external action proposals, and automatic Notion mirroring reject or skip test workspaces. Start clean & connect my accounts creates a NEW empty session and leaves sample content behind; it does not transfer or purge records. The personal flow still requires both connections before exploring. Real OAuth eligibility remains subject to the provider app's configured test users/workspace scope, not bypassed here.

Demo planning uses the sample commitments without claiming Google is connected. Drafts remain unaccepted. A live test caught an AI schedule conflict, so sample mode now falls back to deterministic free-slot scheduling when an AI draft fails validation, with that fact stated in its explanation. This fallback does not apply to personal workspaces. Chat labels test mode explicitly and disables the real Notion/calendar demo buttons; the Saturday prompt in sample mode proposes local tasks and a note only.

Validation: 76 regression tests passed; frontend/SAM builds passed. Live API checks verified two isolated visitors, correct sample record counts, blocked OAuth for both providers, empty personal session, and labeled sample planning context. Live browser verified the entry dropdown and populated test workspace (vida-judge-entry.png). No real calendar or Notion data was changed by these checks. Final live draft retest recorded below.
Final live sample-plan retest passed: a two-task draft was saved around protected sample commitments using the explicitly disclosed scheduling-rule fallback. It remained a draft; no acceptance or external writes. Test-mode proposal cards now display Personal workspace required instead of Needs clarification, and point to the clean-workspace action. Personal setup from onboarding also starts a fresh session when the current profile is a test profile.

## Isolated local demo completion — October 2, 2026

Supersedes the earlier integration-blocker-only test mode: `/test` now opens the sample profile picker without personal onboarding. Each choice creates its own 24-hour workspace. The five-step Saturday starter prepares two tasks, a Library note, a local sample Notion append, and a local calendar event. Approvals remain required; receipts and the banner explicitly say external data is not synced. Personal OAuth/sync remains blocked for test profiles, and starting personal setup creates a fresh session without copying sample data.

Local append uses a conditional transaction against the previewed text. Local events recheck conflicts and use a calendar revision condition to detect concurrent changes. Saved proposal status makes repeat approvals idempotent. Only sample Notion append and sample calendar creation are supported by these simulated provider destinations; real provider operations still require a personal workspace.

Validation: 80 backend regression tests pass; frontend and SAM builds pass. Live five-action request produced five pending proposals, left tasks unchanged before approval, then completed all five through the deployed Step Functions workflow. Task count increased from three to five, both integration receipts explicitly said demo only/not synced, and no integration records existed. Browser verified `/test`, seeded dashboard, and the starter with the next Saturday date. No personal provider data was used or changed.

## Final judge-path polish

Added the first-position “Try organizing my Saturday” starter and “Try Vida with sample data” entry wording. Completed workflows display a single count, destination links, expandable details, and distinct completed/review colors. Completed history now describes saved results rather than repeating the old pre-approval message. Prepared JUDGE_EVIDENCE.md, judge-evidence screenshots, sanitized AWS connection/execution metadata, updated README, DEMO_GUIDE.md, and SUBMISSION_DRAFT.md.

Final validation: 81 backend tests pass. Live replay of every completed proposal left task/document/calendar records unchanged. Browser refresh preserved five completed results. A live read-only shopping-list question initially misclassified as a note write (never approved); added an explicit read-only lookup branch, regression test, and verified source-backed answer with no proposal. This targeted improvement does not establish perfect interpretation for arbitrary prompts.

Public-repository preparation only: added environment/artifact ignores, corrected current frontend path and live URL, scanned working files and Git history for common credential patterns (no matches). No commit, remote change, or push was performed; user is handling GitHub with Claude.
Final clean browser rerun verified the deployed starter, all five ready proposals, approval, five completed results, persistence after refresh, and a concise shopping-list answer with [S1][S2] citations and no new proposal. Both Lambda deployments report Successful with matching code hashes. No GitHub push was performed.
