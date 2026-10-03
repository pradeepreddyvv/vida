# Vida AWS deployment

Backend: stack `vida`, us-east-2, account `237226121208`.
API: https://opx3hs5amf.execute-api.us-east-2.amazonaws.com/prod
HTTPS frontend: https://dahb851px2bik.cloudfront.net — verified live.
Hosting stack: `vida-web`; private bucket `vida-web-frontendbucket-u6gfjakdqo25`.

The maintained interface is `sites/vida`. The directory name is historical; it is now hosted on AWS at the user's request. `scripts/deploy.sh` builds it and updates the independent hosting stack. It deliberately does not deploy the conflicting legacy backend template or reset Lambda environment credentials. Backend code updates were deployed separately while preserving runtime settings.

The old HTTP S3 website was left intact. Prefer the HTTPS address after verification.

## Notion configuration

Google OAuth client credentials are present in the deployed API. Notion's OAuth client ID is empty; no Secrets Manager or Parameter Store entry was found in us-east-2.

Open the existing public connection in the Notion Developer portal. Add the exact redirect URI:
https://opx3hs5amf.execute-api.us-east-2.amazonaws.com/prod/api/auth/notion/callback

Retrieve its OAuth client ID and client secret. Do not use an internal integration token in those fields. Configure them in both `vida-api` and `vida-ai` Lambda environment settings without removing existing settings, or run `scripts/configure-notion.py` using Python with boto3 installed. Its prompts hide the values and it updates AWS without printing them or saving them to a local file.

After saving, open the HTTPS site, choose Settings > Notion > Connect, authorize selected pages, then Sync. Real synchronization cannot be verified until those existing credentials are supplied and the user completes authorization.

Google's callback stays:
https://opx3hs5amf.execute-api.us-east-2.amazonaws.com/prod/api/auth/google/callback

## Verification boundaries

Ten backend tests passed. CloudFormation hosting template passed cfn-lint. User approved proceeding without cfn-guard. No durable CloudTrail trail was found; standard event history provides limited audit retention. Temporary browser session authentication remains a demo limitation.

Hosting verification completed: vida-web CREATE_COMPLETE; CloudFront Deployed; homepage and /projects returned 200; authenticated API profile returned 200 through CloudFront. Notion auth correctly returns 400 until credentials are configured.
