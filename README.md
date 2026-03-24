# AWS Cost Dashboard v2

Interactive AWS cost dashboard with Claude-powered chatbot and on-demand email reports.

## Live demo
https://d3swdga24vd6e7.cloudfront.net

## Features
- Top 20 services by cost with drill-down by usage type, region, instance type
- 7 / 14 / 30 day range selector
- Daily spend trend and service donut chart
- Claude-powered chatbot — ask questions like "How much did EC2 cost yesterday?"
- Email report button — sends formatted HTML report on demand

## Tech stack
- Frontend: HTML + CSS + Chart.js hosted on S3 + CloudFront
- Backend: AWS Lambda + API Gateway
- AI: Claude via Amazon Bedrock
- Data: AWS Cost Explorer API
- Email: AWS SES

## Files
- index.html — full dashboard
- api/dashboard_lambda.py — cost data API
- api/chatbot_lambda.py — Claude chatbot
- api/email_lambda.py — email report sender

## Deploy from scratch (AWS CLI)
All infrastructure deployed via AWS CLI in CloudShell.
API URL: https://9rq6s1b7od.execute-api.us-east-1.amazonaws.com/prod
