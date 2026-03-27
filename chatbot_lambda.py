import boto3
import json
from datetime import datetime, timedelta
import re

ce_client = boto3.client("ce", region_name="us-east-1")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Content-Type": "application/json"
    }
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}
    body = json.loads(event.get("body", "{}"))
    question = body.get("question", "")
    if not question:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "No question provided"})}
    try:
        cost_data = fetch_cost_data(question)
        answer = ask_claude(question, cost_data)
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"answer": answer})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

def fetch_cost_data(question):
    today = datetime.utcnow().date()
    start_date = str(today - timedelta(days=30))
    end_date = str(today)
    question_lower = question.lower()
    if "yesterday" in question_lower:
        start_date = str(today - timedelta(days=2))
        end_date = str(today - timedelta(days=1))
    elif "this month" in question_lower:
        start_date = str(today.replace(day=1))
    elif "this week" in question_lower:
        start_date = str(today - timedelta(days=7))
    elif "last month" in question_lower:
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        start_date = str(last.replace(day=1))
        end_date = str(last)
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
    if date_match:
        d = date_match.group(1)
        start_date = d
        end_date = str(datetime.strptime(d, "%Y-%m-%d").date() + timedelta(days=1))
    last_n = re.search(r"last\s+(\d+)\s+days?", question_lower)
    if last_n:
        n = int(last_n.group(1))
        start_date = str(today - timedelta(days=n))
        end_date = str(today)
    service_map = {
        "ec2": "Amazon Elastic Compute Cloud - Compute",
        "s3": "Amazon Simple Storage Service",
        "rds": "Amazon Relational Database Service",
        "cloudwatch": "AmazonCloudWatch",
        "lambda": "AWS Lambda",
        "vpc": "Amazon Virtual Private Cloud",
        "eks": "Amazon Elastic Kubernetes Service",
        "ecs": "Amazon Elastic Container Service",
        "redshift": "Amazon Redshift",
        "opensearch": "Amazon OpenSearch Service",
        "route 53": "Amazon Route 53",
        "cloudtrail": "AWS CloudTrail",
        "config": "AWS Config",
        "bedrock": "Amazon Bedrock",
        "load balanc": "Amazon Elastic Load Balancing",
        "emr": "Amazon Elastic MapReduce",
        "direct connect": "AWS Direct Connect",
    }
    filters = None
    for keyword, service_name in service_map.items():
        if keyword in question_lower:
            filters = {"Dimensions": {"Key": "SERVICE", "Values": [service_name]}}
            break
    params = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]
    }
    if filters:
        params["GroupBy"] = [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}]
        params["Filter"] = filters
    response = ce_client.get_cost_and_usage(**params)
    results = {}
    for day in response["ResultsByTime"]:
        date = day["TimePeriod"]["Start"]
        total = 0
        items = {}
        for group in day["Groups"]:
            name = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if amount > 0.001:
                items[name] = round(amount, 4)
                total += amount
        if total > 0.001:
            results[date] = {"total": round(total, 4), "breakdown": items}
    return {"date_range": {"start": start_date, "end": end_date}, "daily_costs": results}

def ask_claude(question, cost_data):
    response = bedrock_client.invoke_model(
        modelId="anthropic.claude-sonnet-4-5",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "system": "You are an AWS cost analysis assistant. Answer questions about AWS costs using only the data provided. Be concise, use dollar amounts, keep to 2-4 sentences.",
            "messages": [{"role": "user", "content": "Question: " + question + "\n\nData:\n" + json.dumps(cost_data, indent=2) + "\n\nAnswer using only this data."}]
        })
    )
    return json.loads(response["body"].read())["content"][0]["text"]
