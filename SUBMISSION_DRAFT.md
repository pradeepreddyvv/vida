# Vida

Live app: https://dahb851px2bik.cloudfront.net
Judge entry: https://dahb851px2bik.cloudfront.net/test
Suggested category: **#daily-life-enhancement**
Suggested lane: **#startups** — use this only if your submission describes the intent to develop Vida into a product.

## The problem

Tasks, shopping lists, project notes, and calendar commitments live in different places. Remembering what belongs where becomes another task. Vida turns a brain dump into a set of reviewable changes and keeps the results in one workspace.

## Try Vida in two minutes

1. Open the judge entry and select **Try Vida with sample data**. No Google or Notion account is needed.
2. Explore the preloaded tasks, habits, notes, and sample schedule.
3. In Ask Vida, choose **Try organizing my Saturday**. Edit the prepared prompt if you wish, then send it.
4. Review the five proposed changes. Expand **Change details and results**, then approve the ready steps.
5. See **5 changes completed** and open the saved results. Ask **“What’s on my shopping list?”** to try retrieval from saved context.

Test workspaces contain fictional data. Sample Notion and Calendar actions write only inside Vida and never sync to personal accounts. Real integrations require a separate personal workspace, provider authorization, and shared destinations.

## What Vida does

- Retrieves relevant saved passages for source-backed answers.
- Separates a request into reviewable actions, with explicit approval before execution.
- Runs approved steps in background workflows and saves each result separately.
- Organizes tasks, habits, projects, notes, and a daily schedule.
- Creates planning drafts around commitments using selected priorities and conflict validation.
- Supports Google Calendar and Notion operations in separately authorized personal workspaces; the judge demo simulates these destinations locally.

## Engineering

React is hosted through S3 and CloudFront. API Gateway routes requests to Python Lambda functions, with DynamoDB storing workspace records, proposals, jobs, and results. Amazon Bedrock interprets requests and generates grounded responses. Step Functions runs approved actions with two concurrent workers; EventBridge delivers completion events and the client polls saved status. Validation checks supported operations, destination ownership, requested durations, dates, and schedule conflicts.

## Evidence and limits

See **JUDGE_EVIDENCE.md** for the specific checks and screenshots. Automated checks are engineering evidence, not a user study. No completion-rate, time-saved, or judging-score claim is made.

This is a prototype with temporary 24-hour browser sessions. Retrieval uses lexical document passages rather than a vector database. Personal calendar import covers seven days. AI interpretation can still require clarification. Sample destinations support appending notes and adding events, not every provider operation. Notion updates do not support unrestricted rich layouts. Automatic recovery from every failed external write has not been demonstrated; uncertain writes require review rather than blind retries.

## Before publishing

Attach the screenshot sequence and documented coding-agent/AWS connection evidence. The CLI evidence confirms authenticated AWS operations; it does not establish whether the contest's specific console-connection requirement is satisfied. Confirm eligibility and choose one category and one lane. This document does not publish or submit the project.
