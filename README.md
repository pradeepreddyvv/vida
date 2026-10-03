# Vida

Turn scattered tasks, notes, and calendar commitments into changes you can review and approve.

**[Try the isolated demo](https://dahb851px2bik.cloudfront.net/test)** · **[Live app](https://dahb851px2bik.cloudfront.net)**

## Try it in two minutes

1. Choose **Try Vida with sample data** and a fictional profile.
2. In Ask Vida, choose **Try organizing my Saturday**.
3. Send the editable prompt and review the five changes before approving.
4. Open the saved results, then ask **“What’s on my shopping list?”**

Sample tasks, notes, a Notion-style page, and a calendar stay inside an isolated Vida workspace. Nothing syncs to personal Google or Notion accounts. Real integrations require a separate personal workspace and authorization.

## What works

- Task, project, habit, note, and schedule management.
- Saved-context retrieval with source passages.
- AI request classification and reviewable multi-action proposals.
- Explicit approval, background execution, individual saved results, and repeat-approval protection.
- Daily planning drafts with selected priorities and conflict checks.
- Google Calendar and Notion integrations for separately authorized personal workspaces.

## Architecture

React/Vite → CloudFront/S3 → API Gateway → Python Lambda → DynamoDB.
Amazon Bedrock handles AI requests. Step Functions runs approved workflow steps with concurrency two. EventBridge records completion notifications; the browser polls persisted progress.

See [judge evidence](JUDGE_EVIDENCE.md) for the diagram, verification scope, and screenshots, and [deployment notes](AWS_DEPLOYMENT.md) for the existing stack.

## Repository layout

- `sites/vida/` — current deployed React frontend.
- `backend/functions/api/` — authenticated workspace routes and approval endpoints.
- `backend/functions/ai/` — asynchronous AI/job handler.
- `backend/functions/shared/` — retrieval, planning, validation, and sample workspace logic.
- `backend/tests/` — backend regression tests.
- `backend/hosting.yaml`, `backend/template-sites.yaml`, `backend/workflows.json` — deployment definitions.
- `scripts/` — build, hosting, and integration configuration helpers.
- `frontend/` — earlier frontend retained for history; use `sites/vida/` for current work.

## Local frontend

Requires Node.js and an accessible Vida backend; this is not a fully offline app.

```sh
npm --prefix sites/vida ci
cp sites/vida/.env.example sites/vida/.env.local
# Set VITE_API_URL in .env.local to your own backend/CloudFront base URL.
npm --prefix sites/vida run dev
```

Use an empty `VITE_API_URL` for same-origin deployed hosting. Never put provider secrets into frontend variables.

## Backend checks

Requires Python 3.11. Tests use mocked AWS resources.

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r backend/functions/requirements.txt 'moto[dynamodb,s3]>=5,<6'
.venv/bin/python -m unittest discover -s backend/tests -q
npm --prefix sites/vida run build
sam build --template-file backend/template-sites.yaml
```

Deployment needs your own AWS credentials, Bedrock access, stack configuration, and provider OAuth configuration. Review deployment notes before running scripts; deployment creates or updates billable resources. Do not commit credentials or copy another person's OAuth tokens.

## Limits

This hackathon prototype uses temporary 24-hour browser sessions, not permanent account sign-in. Retrieval is lexical, not a vector database. Personal calendar import covers seven days. AI may require clarification; uncertain external results require review. Sample Notion/calendar operations cover note append and event creation. No universal rich-page editing, continuous two-way sync, automatic recovery guarantee, or measured productivity gain is claimed.

The original planning/design documents describe broader intentions; deployed behavior and the verification notes are the current reference. No contest eligibility or score is guaranteed.
