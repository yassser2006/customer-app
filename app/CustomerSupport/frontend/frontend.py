import json
import os
import uuid
import urllib.parse
from pathlib import Path
from flask import Flask, render_template
import boto3

app = Flask(__name__)

# The Workshop Studio Code Editor exposes local ports through CloudFront.
# Disable origin caching so proxies that honor origin headers request fresh
# content while participants iterate on the frontend.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def disable_cache(response):
    """Prevent browsers and compatible proxies from caching development output."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


REGION = os.getenv("AWS_REGION") or boto3.session.Session().region_name
if not REGION:
    raise RuntimeError("No AWS region configured. Set AWS_REGION or run 'aws configure'.")
ssm_client = boto3.client("ssm", region_name=REGION)
cognito_client = boto3.client("cognito-idp", region_name=REGION)
AGENTCORE_ENDPOINT = f"https://bedrock-agentcore.{REGION}.amazonaws.com"

WORKSHOP_USER = os.getenv("WORKSHOP_USER")
WORKSHOP_PASS = os.getenv("WORKSHOP_PASS")


def get_runtime_arn():
    state_file = Path(__file__).parent.parent.parent.parent / "agentcore" / ".cli" / "deployed-state.json"
    try:
        state = json.loads(state_file.read_text())
        runtimes = state.get("targets", {}).get("default", {}).get("resources", {}).get("runtimes", {})
        return runtimes.get("CustomerSupport", {}).get("runtimeArn", None)
    except Exception:
        pass
    return None

def get_ssm_param(name):
    return ssm_client.get_parameter(Name=name)["Parameter"]["Value"]


def mask_aws_account_id(arn: str) -> str:
    """Mask the account ID portion of an ARN for safe display in the UI."""
    if not arn or arn == "NOT_DEPLOYED":
        return arn

    parts = arn.split(":")
    if len(parts) >= 6 and parts[0] == "arn" and len(parts[4]) == 12 and parts[4].isdigit():
        parts[4] = "************"
        return ":".join(parts)
    return arn


def get_access_token():
    """Authenticate against Cognito and return an access token."""
    if not WORKSHOP_USER or not WORKSHOP_PASS:
        print("❌ Missing WORKSHOP_USER or WORKSHOP_PASS environment variables.")
        return None

    try:
        client_id = get_ssm_param("/app/customersupport/agentcore/web_client_id")
        resp = cognito_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=client_id,
            AuthParameters={"USERNAME": WORKSHOP_USER, "PASSWORD": WORKSHOP_PASS},
        )
        token = resp["AuthenticationResult"]["AccessToken"]
        print(f"✅ Authenticated as {WORKSHOP_USER}")
        return token
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return None


@app.route("/")
def index():
    token = get_access_token()
    if not token:
        return "<h2>Authentication failed. Check workshop user credentials and Cognito configuration.</h2>", 500
    runtime_arn = get_runtime_arn() or "NOT_DEPLOYED"
    runtime_arn_display = mask_aws_account_id(runtime_arn)
    return render_template("index.html",
                           token=token,
                           runtime_arn=runtime_arn,
                           runtime_arn_display=runtime_arn_display,
                           region=REGION,
                           endpoint=AGENTCORE_ENDPOINT,
                           username=WORKSHOP_USER)

if __name__ == "__main__":
    print(f"Runtime ARN: {get_runtime_arn() or 'NOT FOUND'}")
    # Verify auth works on startup
    get_access_token()
    app.run(host="0.0.0.0", port=8501)