import boto3
import json
import os
from datetime import datetime, timedelta, timezone

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
    email = body.get("email", os.environ.get("DEFAULT_EMAIL", "mattktam@gmail.com"))
    days = int(body.get("days", 7))
    try:
        ce = boto3.client("ce", region_name="us-east-1")
        ses = boto3.client("ses", region_name="us-east-1")
        today = datetime.now(timezone.utc).date()
        end = str(today)
        start = str(today - timedelta(days=days))
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
        )
        services = {}
        for result in response["ResultsByTime"]:
            for group in result["Groups"]:
                svc = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                services[svc] = services.get(svc, 0.0) + amount
        rows = sorted(services.items(), key=lambda x: -x[1])[:20]
        total = sum(v for _, v in rows)
        rows_html = ""
        for svc, cost in rows:
            pct = (cost / total * 100) if total else 0
            rows_html += "<tr><td style='padding:10px 14px;font-size:13px;color:#e6edf3;border-top:1px solid #21262d'>" + svc + "</td><td style='padding:10px 14px;font-size:13px;text-align:right;color:#e6edf3;border-top:1px solid #21262d'>$" + format(cost, ",.4f") + "</td><td style='padding:10px 14px;font-size:13px;text-align:right;color:#8b949e;border-top:1px solid #21262d'>" + format(pct, ".1f") + "%</td></tr>"
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        html = "<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body style='margin:0;padding:32px 16px;background:#0d1117;font-family:Segoe UI,sans-serif;color:#e6edf3'><div style='max-width:700px;margin:0 auto'><div style='font-size:22px;font-weight:700;margin-bottom:16px'>AWS Cost Report</div><div style='font-size:12px;color:#8b949e;margin-bottom:24px'>Last " + str(days) + " days - " + start + " to " + end + "</div><div style='background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px'><div style='font-size:11px;color:#8b949e;text-transform:uppercase'>Total spend</div><div style='font-size:2rem;font-weight:700;margin-top:6px'>$" + format(total, ",.2f") + "</div></div><table width='100%' cellpadding='0' cellspacing='0' style='background:#161b22;border:1px solid #30363d;border-radius:12px;border-collapse:separate'><tr style='background:#0d1117'><th style='padding:10px 14px;font-size:11px;color:#8b949e;text-align:left;border-bottom:1px solid #30363d'>Service</th><th style='padding:10px 14px;font-size:11px;color:#8b949e;text-align:right;border-bottom:1px solid #30363d'>Cost</th><th style='padding:10px 14px;font-size:11px;color:#8b949e;text-align:right;border-bottom:1px solid #30363d'>%</th></tr>" + rows_html + "</table><div style='text-align:center;font-size:12px;color:#444;margin-top:20px'>Generated " + generated + "</div></div></body></html>"
        ses.send_email(
            Source=email,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "AWS Cost Report - Last " + str(days) + " days ($" + format(total, ",.2f") + ")", "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html, "Charset": "UTF-8"}}
            }
        )
        return {"statusCode": 200, "headers": headers, "body": json.dumps({"message": "Report sent to " + email, "total": round(total, 2)})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
