#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PROFILE="hackathon"
STACK_NAME="vida"
REGION="us-east-2"

echo "=== Vida Deploy ==="

# --- Build first ---
"$PROJECT_DIR/scripts/build.sh"

# --- SAM Deploy ---
echo "Deploying backend..."
cd "$BACKEND_DIR"
python3 -m samcli deploy \
  --stack-name "$STACK_NAME" \
  --s3-bucket vida-sam-deploy-042170206023 \
  --capabilities CAPABILITY_IAM \
  --region "$REGION" \
  --profile "$PROFILE" \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

# --- Get outputs ---
echo "Getting stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --profile "$PROFILE" --query "Stacks[0].Outputs" --output json)

FRONTEND_BUCKET="vida-frontend-042170206023"
CF_DOMAIN=$(echo "$OUTPUTS" | python3 -c "import sys,json; [print(o['OutputValue']) for o in json.load(sys.stdin) if o['OutputKey']=='CloudFrontDomain']")
CF_DIST_ID=$(echo "$OUTPUTS" | python3 -c "import sys,json; [print(o['OutputValue']) for o in json.load(sys.stdin) if o['OutputKey']=='CloudFrontDistributionId']")
API_URL=$(echo "$OUTPUTS" | python3 -c "import sys,json; [print(o['OutputValue']) for o in json.load(sys.stdin) if o['OutputKey']=='ApiUrl']")

echo "API URL: $API_URL"
echo "Frontend Bucket: $FRONTEND_BUCKET"
echo "CloudFront Domain: $CF_DOMAIN"

# --- Deploy frontend to S3 ---
echo "Deploying frontend to S3..."
aws s3 sync "$FRONTEND_DIR/dist/" "s3://$FRONTEND_BUCKET/" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --profile "$PROFILE" \
  --region "$REGION"

# index.html should not be cached long
aws s3 cp "$FRONTEND_DIR/dist/index.html" "s3://$FRONTEND_BUCKET/index.html" \
  --cache-control "public, max-age=0, must-revalidate" \
  --content-type "text/html" \
  --profile "$PROFILE" \
  --region "$REGION"

# --- Invalidate CloudFront ---
echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id "$CF_DIST_ID" \
  --paths "/*" \
  --profile "$PROFILE" \
  --region "$REGION"

echo ""
echo "=== Deploy Complete ==="
echo "App URL: https://$CF_DOMAIN"
echo "API URL: $API_URL"
