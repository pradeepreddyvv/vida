# Vida — AI Life Assistant with Personal RAG

An intelligent life management assistant that uses AWS Bedrock (Amazon Nova Lite) and a multi-agent pipeline to help users plan their day, track goals, build habits, and stay accountable — all powered by their own documents and context.

**Live:** [https://dieldwu0y5z3o.cloudfront.net](https://dieldwu0y5z3o.cloudfront.net)

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     CloudFront (CDN)                         │
│  ┌──────────────┐                    ┌────────────────────┐  │
│  │  S3: Frontend │ ← static assets   │ API Gateway (HTTP) │  │
│  │  React + Vite │                    │   /api/* → Lambda  │  │
│  └──────────────┘                    └────────┬───────────┘  │
└───────────────────────────────────────────────┼──────────────┘
                                                │
                    ┌───────────────────────────┼──────────┐
                    │           vida-api (Lambda)          │
                    │  Session auth · 43 routes · Job mgmt │
                    │  Async invokes vida-ai for AI work   │
                    └───────────┬──────────────────────────┘
                                │ async invoke
                    ┌───────────▼──────────────────────────┐
                    │           vida-ai (Lambda)            │
                    │  Multi-agent pipeline · Bedrock Nova  │
                    │  Planner → Reviewer → Validator       │
                    └───────────┬──────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼──────┐  ┌──────▼──────┐  ┌───────▼──────┐
     │  DynamoDB      │  │   Bedrock   │  │  S3: Docs    │
     │  vida-main     │  │  Nova Lite  │  │  User files  │
     │  Single-table  │  │  Converse   │  │  RAG source  │
     │  3 GSIs        │  │  API        │  │              │
     └────────────────┘  └─────────────┘  └──────────────┘
```

## Features

- **AI Chat** — Context-aware assistant that knows your goals, tasks, habits, and documents via RAG
- **Smart Day Planner** — Multi-agent pipeline: Planner (creates schedule) → Reviewer (validates) → Validator (checks overlaps/conflicts) → Executor (saves blocks)
- **Goal & Task Tracking** — CRUD with priority, due dates, estimated time, and progress tracking
- **Habit Builder** — Daily habit tracking with streak counting and completion logging
- **Journal** — Freeform entries with mood tracking, organized by date
- **Document Library** — Upload documents (PDF, MD, TXT) for personal RAG context
- **Onboarding** — Upload a resume or bio; AI extracts profile, goals, tasks, and habits automatically
- **Daily Reports** — AI-generated end-of-day summaries comparing planned vs. actual

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, Lucide icons |
| API | AWS API Gateway HTTP API (v2) |
| Compute | AWS Lambda (Python 3.11, ARM64) |
| Database | Amazon DynamoDB (single-table, on-demand, 3 GSIs) |
| AI | Amazon Bedrock — Nova Lite (`amazon.nova-lite-v1:0`) |
| Storage | Amazon S3 (frontend hosting + document storage) |
| CDN | Amazon CloudFront (OAC + SPA rewrite function) |
| IaC | AWS SAM (CloudFormation) |

## Multi-Agent Pipeline

The planner uses a code-orchestrated multi-agent design:

1. **Router** (code) — classifies request type and dispatches to the right agent
2. **Planner** (AI, temp 0.3) — generates a time-blocked daily schedule considering tasks, goals, availability, and existing locked blocks
3. **Reviewer** (AI, temp 0.2) — validates the plan for conflicts, overcommitment, and missing breaks; can request one repair cycle
4. **Validator** (code) — programmatic checks for time overlaps, locked block conflicts, and duration limits
5. **Executor** (code) — sole writer to DynamoDB; accepts only validated plans

## API Design

- **Session-based auth** — `POST /api/session` creates a server-issued bearer token (SHA-256 hashed, stored in DynamoDB)
- **Async AI jobs** — AI-intensive operations (chat, plan generation, reports) are submitted as jobs via `POST`, processed asynchronously by vida-ai Lambda, and polled via `GET /api/jobs/{id}`
- **43 routes** covering profiles, goals, tasks, calendar blocks, habits, journal, documents, plans, reports, and chat

## Project Structure

```
├── backend/
│   ├── template.yaml          # SAM template (IaC)
│   └── functions/
│       ├── shared/            # Shared modules (db, ai, models, utils, prompts, agents)
│       ├── api/               # vida-api Lambda (handler + 11 route modules)
│       └── ai/                # vida-ai Lambda (async worker)
├── frontend/
│   └── src/
│       ├── pages/             # TodayPage, PlanPage, ProgressPage, LibraryPage, OnboardingPage
│       ├── components/        # AppShell, Sidebar, ChatPanel
│       └── lib/               # API client, session management
└── scripts/
    ├── build.sh               # Copy shared modules + SAM build + frontend build
    └── deploy.sh              # Full deploy pipeline
```

## Deployment

```bash
# Prerequisites: AWS CLI, SAM CLI, Node.js, Python 3.11
# Configure: aws configure --profile hackathon

# Build everything
./scripts/build.sh

# Deploy
./scripts/deploy.sh
```

All infrastructure is managed via SAM/CloudFormation in `us-east-2`. Resources use `DeletionPolicy: Retain` for data safety.

## AWS Services Used

- **Amazon Bedrock** — Nova Lite model for all AI reasoning (chat, planning, review, extraction, reports)
- **AWS Lambda** — Two functions: vida-api (256MB, 29s) for HTTP routes, vida-ai (512MB, 90s) for async AI work
- **Amazon DynamoDB** — Single-table design with 3 GSIs for efficient access patterns
- **Amazon S3** — Two buckets: frontend hosting and document storage
- **Amazon CloudFront** — CDN with OAC for S3 and API origin routing
- **AWS API Gateway** — HTTP API (v2) with CORS support
- **AWS IAM** — Least-privilege roles for each Lambda function

## Built For

[AWS "Zero to Shipped" Hackathon](https://awszerotoshipped.devpost.com/) — October 2026
