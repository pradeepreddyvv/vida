#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${AWS_PROFILE:-hackathon}"
REGION="${AWS_REGION:-us-east-2}"
BACKEND_STACK="${BACKEND_STACK:-vida}"
WEB_STACK="${WEB_STACK:-vida-web}"
# Backend infrastructure is deliberately separate: never replace its data buckets
# or overwrite provider credentials merely to publish a frontend update.
API_URL=$(aws cloudformation describe-stacks --stack-name "$BACKEND_STACK" --region "$REGION" --profile "$PROFILE" --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue | [0]' --output text)
API_DOMAIN=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.urlparse(sys.argv[1]).netloc)' "$API_URL")
API_STAGE=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.urlparse(sys.argv[1]).path.strip("/"))' "$API_URL")
aws cloudformation deploy --template-file "$PROJECT_DIR/backend/hosting.yaml" --stack-name "$WEB_STACK" --parameter-overrides "ApiDomain=$API_DOMAIN" "ApiStage=$API_STAGE" --region "$REGION" --profile "$PROFILE" --no-fail-on-empty-changeset
BUCKET=$(aws cloudformation describe-stacks --stack-name "$WEB_STACK" --region "$REGION" --profile "$PROFILE" --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue | [0]' --output text)
DOMAIN=$(aws cloudformation describe-stacks --stack-name "$WEB_STACK" --region "$REGION" --profile "$PROFILE" --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue | [0]' --output text)
DIST_ID=$(aws cloudformation describe-stacks --stack-name "$WEB_STACK" --region "$REGION" --profile "$PROFILE" --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue | [0]' --output text)
VITE_API_URL='' npm --prefix "$PROJECT_DIR/sites/vida" run build
aws s3 sync "$PROJECT_DIR/sites/vida/dist/" "s3://$BUCKET/" --cache-control 'public,max-age=31536000,immutable' --region "$REGION" --profile "$PROFILE"
aws s3 cp "$PROJECT_DIR/sites/vida/dist/index.html" "s3://$BUCKET/index.html" --cache-control 'no-cache' --content-type text/html --region "$REGION" --profile "$PROFILE"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*' --profile "$PROFILE" --query Invalidation.Id --output text
printf 'Vida HTTPS URL: https://%s\n' "$DOMAIN"
