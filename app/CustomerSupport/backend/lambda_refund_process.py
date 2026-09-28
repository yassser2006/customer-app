import json
import os
import time
import random
import boto3
from botocore.config import Config

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.environ["AWS_REGION"],
    config=Config(
        retries={"max_attempts": 4, "mode": "standard"}
    ),
)
table = dynamodb.Table(os.environ["REFUND_LEDGER_TABLE"])

class TransientRefundError(Exception):
    pass

class PermanentRefundError(Exception):
    pass


def is_refund_allowed(amount):
    try:
        return float(amount) <= 1000.0
    except (TypeError, ValueError):
        return False


def normalize_order_id(order_id):
    return str(order_id).strip().upper()


def refund_logic(order_id, amount, reason):
    """
    Replace this with your real refund backend call.
    This function should raise TransientRefundError for retryable issues.
    """
    # Example business rules
    if order_id == "ORD-98765":
        raise PermanentRefundError("Order is cancelled")

    # Simulate transient failures
    if order_id == "ORD-99999":
        raise TransientRefundError("Temporary downstream timeout")

    return {
        "status": "processed",
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "message": "Refund succeeded"
    }

def get_retry_delay(attempt_number):
    base_delay = 1
    return base_delay * (2 ** (attempt_number - 1)) + random.uniform(0, 0.5)


def retryable_refund(order_id, amount, reason):
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        try:
            return refund_logic(order_id, amount, reason)
        except TransientRefundError:
            if attempt == max_attempts:
                raise
            time.sleep(get_retry_delay(attempt))
        except PermanentRefundError:
            raise


def refund_is_already_processed(existing):
    if not existing:
        return False
    return existing.get("status") in {"COMPLETED", "PENDING", "FAILED", "REJECTED"}

def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        payload = json.loads(body)
    else:
        payload = event

    order_id = normalize_order_id(payload.get("order_id"))
    amount = payload.get("amount")
    reason = payload.get("reason", "")

    if not order_id or amount is None:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "order_id and amount are required"})
        }

    if not is_refund_allowed(amount):
        rejected = {
            "status": "rejected",
            "order_id": order_id,
            "error": "Refund amount exceeds policy limit of 1000"
        }
        return {
            "statusCode": 403,
            "body": json.dumps(rejected)
        }

    key = {"order_id": order_id}

    existing = table.get_item(Key=key).get("Item")
    if refund_is_already_processed(existing):
        status = existing.get("status")
        if status == "COMPLETED":
            return {
                "statusCode": 200,
                "body": json.dumps(existing["result"])
            }
        if status == "PENDING":
            return {
                "statusCode": 202,
                "body": json.dumps({
                    "status": "in_progress",
                    "order_id": order_id,
                    "message": "Refund already being processed"
                })
            }
        if status in ("FAILED", "REJECTED"):
            return {
                "statusCode": 200,
                "body": json.dumps(existing["result"])
            }

    try:
        table.put_item(
            Item={
                "order_id": order_id,
                "status": "PENDING",
                "result": {"status": "pending"},
                "updated_at": str(time.time())
            },
            ConditionExpression="attribute_not_exists(order_id)"
        )
    except Exception:
        # Another request already reserved this key
        existing = table.get_item(Key=key).get("Item")
        if existing and existing.get("status") == "COMPLETED":
            return {
                "statusCode": 200,
                "body": json.dumps(existing["result"])
            }
        if existing and existing.get("status") == "PENDING":
            return {
                "statusCode": 202,
                "body": json.dumps({
                    "status": "in_progress",
                    "order_id": order_id,
                    "message": "Refund already being processed"
                })
            }

    try:
        result = retryable_refund(order_id, amount, reason)
        table.update_item(
            Key=key,
            UpdateExpression="SET #status = :status, result = :result, updated_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":result": result,
                ":ts": str(time.time())
            }
        )
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except PermanentRefundError as e:
        failed_result = {
            "status": "rejected",
            "order_id": order_id,
            "error": str(e)
        }
        table.update_item(
            Key=key,
            UpdateExpression="SET #status = :status, result = :result, updated_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "REJECTED",
                ":result": failed_result,
                ":ts": str(time.time())
            }
        )
        return {
            "statusCode": 400,
            "body": json.dumps(failed_result)
        }

    except Exception as e:
        failed_result = {
            "status": "failed",
            "order_id": order_id,
            "error": str(e)
        }
        table.update_item(
            Key=key,
            UpdateExpression="SET #status = :status, result = :result, updated_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "FAILED",
                ":result": failed_result,
                ":ts": str(time.time())
            }
        )
        return {
            "statusCode": 500,
            "body": json.dumps(failed_result)
        }