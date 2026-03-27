# AWS Cost Dashboard v2

Interactive AWS cost dashboard with AI-powered chatbot and on-demand email reports — built entirely with AWS CLI.

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
- Backend: AWS Lambda + API Gateway
- AI: Amazon Nova Micro via Amazon Bedrock
- Data: AWS Cost Explorer API
- Email: AWS SES

---

## Deploy from scratch

Everything is deployed using AWS CLI in CloudShell. No console clicking required.

### Prerequisites
- AWS account
- Cost Explorer enabled (Billing console → Cost Explorer → Enable)
- Email verified in SES us-east-1 (see Step 7)

---

### Step 1 — Open CloudShell

Go to your AWS Console and click the CloudShell icon in the top navigation bar.

---

### Step 2 — Clone this repo
```bash
git clone https://github.com/mattktam/aws-cost-dashboard-v2.git
cd aws-cost-dashboard-v2
```

---

### Step 3 — Set your variables

Replace the values below with your own then run:
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="aws-cost-dashboard-v2"       # must be globally unique — change this
REGION="us-east-1"
ROLE_NAME="CostDashboardRole"
YOUR_EMAIL="you@example.com"         # must be verified in SES
echo "Account: $ACCOUNT_ID"
echo "Ready"
```

---

### Step 4 — Create IAM role
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

echo "Waiting for IAM to propagate..."
sleep 10
echo "IAM done"
```

---

### Step 5 — Create S3 bucket
```bash
aws s3api create-bucket \
  --bucket $BUCKET \
  --region $REGION

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

echo "S3 done"
```

---

### Step 6 — Deploy Lambda functions
```bash
cd ~/aws-cost-dashboard-v2

cp api/dashboard_lambda.py dashboard_lambda.py
zip dashboard_lambda.zip dashboard_lambda.py

cp api/chatbot_lambda.py chatbot_lambda.py
zip chatbot_lambda.zip chatbot_lambda.py

cp api/email_lambda.py email_lambda.py
zip email_lambda.zip email_lambda.py

aws lambda create-function \
  --function-name cost-dashboard-api \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler dashboard_lambda.lambda_handler \
  --zip-file fileb://dashboard_lambda.zip \
  --timeout 60
echo "Dashboard Lambda done"

aws lambda create-function \
  --function-name cost-chatbot \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler chatbot_lambda.lambda_handler \
  --zip-file fileb://chatbot_lambda.zip \
  --timeout 60
echo "Chatbot Lambda done"

aws lambda create-function \
  --function-name cost-email-report \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME \
  --handler email_lambda.lambda_handler \
  --zip-file fileb://email_lambda.zip \
  --timeout 60
echo "Email Lambda done"
```

---

### Step 7 — Verify your email in SES
```bash
aws ses verify-email-identity \
  --email-address $YOUR_EMAIL \
  --region $REGION
```

Check your inbox and click the verification link AWS sends you.

---

### Step 8 — Create API Gateway
```bash
API_ID=$(aws apigateway create-rest-api \
  --name cost-dashboard-api \
  --endpoint-configuration types=REGIONAL \
  --query id --output text)
echo "API_ID: $API_ID"

ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[?path==`/`].id' --output text)

# /costs endpoint
COSTS_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part costs \
  --query id --output text)

aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $COSTS_ID \
  --http-method GET \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $COSTS_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:cost-dashboard-api/invocations

aws lambda add-permission \
  --function-name cost-dashboard-api \
  --statement-id apigateway-costs \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/GET/costs

# /chat endpoint
CHAT_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part chat \
  --query id --output text)

aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method POST \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:cost-chatbot/invocations

aws lambda add-permission \
  --function-name cost-chatbot \
  --statement-id apigateway-chat \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/POST/chat

aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method OPTIONS \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json":"{\"statusCode\":200}"}'

aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers":false,"method.response.header.Access-Control-Allow-Methods":false,"method.response.header.Access-Control-Allow-Origin":false}'

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $CHAT_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'POST,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}'

# /email endpoint
EMAIL_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part email \
  --query id --output text)

aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method POST \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:cost-email-report/invocations

aws lambda add-permission \
  --function-name cost-email-report \
  --statement-id apigateway-email \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/POST/email

aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method OPTIONS \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json":"{\"statusCode\":200}"}'

aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers":false,"method.response.header.Access-Control-Allow-Methods":false,"method.response.header.Access-Control-Allow-Origin":false}'

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $EMAIL_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'POST,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}'

aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod

echo "API URL: https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
```

---

### Step 9 — Update index.html with your API URL
```bash
sed -i "s|const API='[^']*'|const API='https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod'|" index.html
```

---

### Step 10 — Upload site to S3
```bash
aws s3 cp index.html s3://$BUCKET/index.html
echo "Site uploaded"
```

---

### Step 11 — Create CloudFront distribution
```bash
CF_DOMAIN=$(aws cloudfront create-distribution \
  --origin-domain-name ${BUCKET}.s3-website-${REGION}.amazonaws.com \
  --default-root-object index.html \
  --query 'Distribution.DomainName' \
  --output text)

echo "Your dashboard: https://$CF_DOMAIN"
echo "Wait 5-10 mins for CloudFront to deploy"
```

---

### Step 12 — Update site after changes

Run this every time you update index.html:
```bash
aws s3 cp index.html s3://$BUCKET/index.html

DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Origins.Items[0].DomainName,'$BUCKET')].Id" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"

echo "Site updated"
```

---

## Related projects
- [aws-cost-report](https://github.com/mattktam/aws-cost-report) — daily automated email report
- [aws-cost-report-website](https://github.com/mattktam/aws-cost-report-website) — v1 dashboard
