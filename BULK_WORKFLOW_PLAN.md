# Vida bulk workflows

Status: staged implementation. Step Functions Standard and an EventBridge completion bus are now deployed in the vida-workflows stack. Approved independent steps run server-side with concurrency two; persistent notifications feed an in-app activity panel refreshed every eight seconds. A maximum of five saved proposals can be approved together. The detailed dependency scheduler, queues, transactional outbox and WebSocket transport below remain a later design, not deployed capabilities.

## Product behavior

A user provides a brain dump. Vida extracts every requested outcome, shows destinations and missing details, and saves a versioned workflow. Clarifying one step never discards the others. Approval authorizes exact changes, not unrestricted future action. Independent approved steps continue after the browser closes. Dependent steps wait for verified predecessor results. The UI displays completed, blocked, failed, and uncertain outcomes separately.

Example: move the existing October 3 Exercise event from 18:00–19:00 to 10:00–11:00; append the senior SDE reminder to the chosen Notion page. Resolve the existing event and page IDs. Do not create a new event when an update was requested. If two Exercise events exist, show them and ask which to keep or change; do not silently delete either. Do not invent the senior SDE's specific tips.

## Target architecture and current simplification

The first deployed version invokes the existing Lambda worker directly from a Step Functions Map. It publishes explicit per-step completion events through the EventBridge service integration. This avoids queue/callback infrastructure before there is evidence of provider backlog. Action records remain authoritative if event delivery fails. Separate resource leases prevent simultaneous writes to the same resource; a conflicting step currently needs review instead of automatically waiting.

## Architecture decision

- Keep the existing Python Lambda/API Gateway API and Bedrock model. One coordinator model call produces typed steps; resolvers and validators use deterministic code and provider reads. Separate model agents are optional roles, not a requirement for every API call.
- DynamoDB stores workflow versions, steps, approvals, resource leases, results and notification events. Store the original request and unresolved intentions independently of the bounded chat history.
- Step Functions Standard owns execution ordering, bounded parallel branches, waiting and recovery. This fits long-running human approval and callback needs better than Express. Initial approvals are stored before starting execution; later approvals use server-held callback tokens with timeouts.
- SQS queues buffer Google, Notion and local-tool work; Lambda workers handle each provider. Step Functions dispatches ready steps with callback correlation. Each layer has one responsibility: Step Functions owns dependency progression; SQS owns delivery and short transient transport retries; workers own provider calls and result validation.
- DynamoDB transactional outbox records state changes and notification events together. A Streams consumer publishes them to EventBridge. Separate subscribers update the activity feed, monitoring and user notification delivery. EventBridge is notification fan-out, not the execution state database.
- API Gateway WebSocket pushes in-app updates to authenticated workspace connections. REST workflow snapshots and an event cursor recover missed updates on reconnect. Keep polling as fallback. No email, Slack or external notification subscriptions without a separate user choice.

## Persistent contract

Workflow: owner_id, workflow_id, original_request, version, status, created_at, updated_at, summary, execution_arn.
Step: step_id, workflow_id, intent, provider, operation, arguments, resolved resource IDs, depends_on, status, input_version, approval_hash, idempotency_key, attempt, lease_expiry, provider_result_id, result_url, verification evidence, error_code.
Approval: owner_id, workflow/version, selected step IDs, canonical argument hash, target snapshot/etag, expiry, approval time. Store callback secrets server-side; never expose them to model prompts or browser events.
Event: event_id, owner_id, workflow_id, step_id, step_version, event_type, timestamp, safe summary. Send identifiers and minimal display text, not OAuth tokens or private document bodies.

Step states: needs_input -> awaiting_approval -> approved -> queued -> running -> succeeded. Alternate outcomes: failed, needs_review (remote outcome uncertain), cancelled, blocked_dependency. Workflow status is derived from its steps; partial success must never be reported as complete.

## Coordinator and scheduling

1. Extract ALL intentions into a bounded typed plan; preserve ambiguous intentions as needs_input.
2. Resolve names against current catalogs and provider reads. Exact match first; clear typo matches appear by their actual name in the preview. Multiple plausible matches require selection.
3. Validate ownership, supported operations, calendar conflicts, expected resource versions and limits. Reject cycles and nonexistent dependency IDs.
4. Save the plan before asking a question. Answers revise only relevant fields; any changed action invalidates its earlier approval.
5. Preview all steps. Allow approve selected, approve all ready, edit, or cancel. Display blocked steps even when others are ready.
6. Start the server workflow from an atomic approved-version transition. Begin with a configurable limit of two concurrent steps per workspace and five steps per workflow; these are product defaults, not AWS limits. Split larger brain dumps into reviewed batches without losing remaining intentions.
7. Each scheduler round runs ready, approved steps whose dependencies succeeded. Resource-level leases serialize writes to the same Notion page or Google event; independent resources can run together. Replace the current workspace-wide worker lock for execution, retaining a short coordinator lock for plan revisions.
8. Workers read back results, persist evidence and publish state events through the outbox. Refresh affected Vida indexes/calendar caches. A note claiming that an event moved depends on that event's verified result.
9. When a dependency creates a resource, bind its verified returned ID. If resolving it changes meaningful user-approved content or destination, request a fresh preview rather than silently broadening approval.

## Duplicate and failure handling

Use workflow/step/version idempotency keys and conditional status transitions. Repeated clicks, queue redelivery and notification replay must not repeat a completed write. Provider idempotency where supported supplements the local ledger; it does not replace it. Notion creates/appends are not assumed exactly-once: on a timeout after transmission mark needs_review and reconcile before retry. Do not blindly retry uncertain writes.

Rate-limit per provider/account, back off transient failures, stop on authentication/validation failures, and place exhausted queue deliveries in a dead-letter queue. Reconnection should resume only explicitly approved pending work. Cancelling a workflow stops unstarted steps; already running requests may finish and must be reported. Do not promise cross-provider atomic rollback. Undo is a separate reviewed compensating action.

WebSocket authorization checks owner identity on subscription and delivery. Never accept an arbitrary client-supplied owner ID. Durable user authentication and reconnectable workspace identity are prerequisites for long-lived background workflows; the current temporary browser sessions are a release limitation.

## UI

One workflow card: "4 changes: 2 complete, 1 needs approval, 1 blocked." Each row shows action, real destination, before/after, state and result link. Approval actions stay on the row and header. A quiet activity panel retains notifications; use a single grouped completion notice instead of a toast for every internal event. The chat never displays internal status JSON or treats model prose as a receipt.

## Delivery order

1. Harden the deployed multi-proposal patch: future-event resolution, clarification persistence independent of history, blocked-step revisions, per-step results and live cross-provider tests.
2. Add durable workflow records, version-bound approval, status APIs and idempotency/lease rules. Move approve-all execution from browser to server.
3. Add Step Functions Standard, provider queues/workers and bounded dependency scheduling. Verify browser-close survival and partial failure recovery before enabling parallel writes.
4. Add outbox/Streams/EventBridge fan-out, authenticated WebSocket delivery, activity feed and reconnect replay.
5. Enable larger batches after cost/rate-limit tests. Keep one coordinator call per planning revision and avoid LLM calls for polling, receipts or deterministic dispatch. Add resource tags, spend alerts and concurrency caps without assuming these services are free.

## Acceptance tests

- One calendar update plus one Notion append -> two previews, two verified results, no extra event.
- Clarify a calendar alias -> Notion intention retained.
- Approval double-click, queue redelivery and worker restart -> no repeated completed write.
- Google succeeds and Notion times out -> partial completion and uncertain Notion outcome; no blind retry.
- Two changes to one page serialize; unrelated pages can run concurrently.
- Resource edited after preview -> fresh approval, not stale overwrite.
- Close/reopen browser -> server continues and statuses recover.
- Duplicate/out-of-order push events -> UI uses step versions and authoritative snapshots.
- Cross-user workflow IDs, subscriptions and approvals -> rejected.
- Exact requested note appears in Notion; completed provider result is read back before displaying success.

## References

- https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-human-approval.html
- https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/eventbridge-for-dynamodb.html
