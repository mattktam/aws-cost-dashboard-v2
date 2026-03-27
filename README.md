# AWS Cost Dashboard v2

Interactive AWS cost dashboard with AI-powered chatbot and on-demand email reports.

## Live demo
https://d3swdga24vd6e7.cloudfront.net

## Features
- Top 20 services by cost with drill-down by usage type, region and instance type
- 7 / 14 / 30 day range selector
- Daily spend trend chart and service donut chart
- AI-powered chatbot — ask questions like "How much did EC2 cost yesterday?"
- Email report button — sends formatted HTML report on demand

## Tech stack
- Frontend: HTML + CSS + Chart.js hosted on S3 + CloudFront
- Backend: AWS Lambda + API Gateway (3 endpoints)
- AI: Amazon Nova Micro via Amazon Bedrock
- Data: AWS Cost Explorer API
- Email: AWS SES

## Files
- `index.html` — full dashboard
- `api/dashboard_lambda.py` — cost data API (/costs endpoint)
- `api/chatbot_lambda.py` — AI chatbot (/chat endpoint)
- `api/email_lambda.py` — email report sender (/email endpoint)

## Deploy from scratch (AWS CLI)

All infrastructure is deployed entirely via AWS CLI in CloudShell. No console clicking required.

### Prerequisites
- AWS account with Cost Explorer enabled
- Email verified in AWS SES (us-east-1)
- Open AWS CloudShell

### Step 1 — Set variables
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="aws-cost-dashboard-v2"
REGION="us-east-1"
ROLE_NAME="CostDashboardRole"
```

### Step 2 — Create IAM role
```bash
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name CostDashboardPermissions \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ce:GetCostAndUsage","ce:GetCostForecast","ses:SendEmail","ses:SendRawEmail","bedrock:InvokeModel"],"Resource":"*"}]}'

sleep 10
```

### Step 3 — Create S3 bucket
```bash
aws s3api create-bucket --bucket $BUCKET --region $REGION

aws s3api put-public-access-block \
  --bucket $BUCKET \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy \
  --bucket $BUCKET \
  --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicRead\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]}"

aws s3api put-bucket-website \
  --bucket $BUCKET \
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}'
```

### Step 4 — Deploy Lambda functions
```bash
zip dashboard_lambda.zip api/dashboard_lambda.py
zip chatbot_lambda.zip api/chatbot_lambda.py
zip email_lambda.zip api/email_lambda.py

aws lambda create-function \
  --function-name cost-dashboard-api \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler dashboard_lambda.lambda_handler \
  --zip-file fileb://dashboard_lambda.zip \
  --timeout 60

aws lambda create-function \
  --function-name cost-chatbot \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler chatbot_lambda.lambda_handler \
  --zip-file fileb://chatbot_lambda.zip \
  --timeout 60

aws lambda create-function \
  --function-name cost-email-report \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler email_lambda.lambda_handler \
  --zip-file fileb://email_lambda.zip \
  --timeout 60
```

### Step 5 — Create API Gateway
```bash
API_ID=$(aws apigateway create-rest-api \
  --name cost-dashboard-api \
  --endpoint-configuration types=REGIONAL \
  --query id --output text)

ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[?path==`/`].id' --output text)

# Create /costs, /chat, /email resources and wire to Lambdas
# (see full deployment script in deploy.sh)

aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod

echo "API URL: https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
```

### Step 6 — Upload site and create CloudFront
```bash
aws s3 cp index.html s3://$BUCKET/index.html

CF_DOMAIN=$(aws cloudfront create-distribution \
  --origin-domain-name ${BUCKET}.s3-website-${REGION}.amazonaws.com \
  --default-root-object index.html \
  --query 'Distribution.DomainName' \
  --output text)

echo "Live at: https://$CF_DOMAIN"
```

### Step 7 — Update site after changes
```bash
aws s3 cp index.html s3://aws-cost-dashboard-v2/index.html

DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?DomainName=='d3swdga24vd6e7.cloudfront.net'].Id" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"
```

## Related projects
- [aws-cost-report](https://github.com/mattktam/aws-cost-report) — daily automated email report
- [aws-cost-report-website](https://github.com/mattktam/aws-cost-report-website) — v1 dashboard
