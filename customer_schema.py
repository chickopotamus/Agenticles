import os
import json
from datetime import datetime, timezone

SCHEMA_FILE = "customer_schema.json"

def now():
    return datetime.now(timezone.utc).isoformat()

def load():
    if os.path.exists(SCHEMA_FILE):
        with open(SCHEMA_FILE, 'r') as f:
            return json.load(f)
    return None

def save(schema):
    with open(SCHEMA_FILE, 'w') as f:
        json.dump(schema, f, indent=2)

def get(key_path, default=None):
    schema = load()
    if not schema:
        return default
    keys = key_path.split('.')
    val = schema
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return default
    return val

def update(key_path, value):
    schema = load()
    if not schema:
        return False
    keys = key_path.split('.')
    d = schema
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value
    save(schema)
    return True

def log_run(run_data):
    schema = load()
    if not schema:
        return
    schema["pipeline_runs"].append(run_data)
    schema["run_summary_log"].append({
        "timestamp": run_data["timestamp"],
        "topic": run_data.get("topic", ""),
        "wp_url": run_data.get("wp_url", ""),
        "brevo_id": run_data.get("brevo_id", ""),
        "photo": run_data.get("photo", ""),
        "success": run_data.get("success", False)
    })
    tracking = schema["pm_intelligence"]["cost_tracking"]
    tracking["total_spent"] = round(
        tracking["total_spent"] + run_data.get("cost", 0), 4
    )
    tracking["runs_this_month"] += 1
    if tracking["runs_this_month"] > 0:
        tracking["avg_cost_per_run"] = round(
            tracking["total_spent"] / tracking["runs_this_month"], 4
        )
    health = schema["pm_intelligence"]["pipeline_health"]
    if run_data.get("success"):
        health["consecutive_successes"] += 1
        health["consecutive_failures"] = 0
    else:
        health["consecutive_failures"] += 1
        health["consecutive_successes"] = 0
        health["last_failure"] = now()
        health["last_failure_reason"] = run_data.get("error", "unknown")
    save(schema)

def log_feedback(feedback_text, run_id=None):
    schema = load()
    if not schema:
        return
    schema["feedback_log"].append({
        "timestamp": now(),
        "feedback": feedback_text,
        "run_id": run_id,
        "processed": False
    })
    save(schema)

def mark_onboarding_complete():
    update("customer.status", "active")
    update("customer.onboarding_complete", True)

def get_topic_pool():
    return get("topic_intelligence.topic_pool", [])

def get_used_topics():
    return get("topic_intelligence.used_topics", [])

def add_used_topic(topic):
    used = get_used_topics()
    if topic not in used:
        used.append(topic)
        update("topic_intelligence.used_topics", used)

def get_niche_keywords():
    return get("topic_intelligence.niche_keywords", [])

def get_tone_profile():
    return get("tone_profile", {})

def get_platform_config(platform="website"):
    return get(f"content_platforms.{platform}", {})

def is_connected(platform="website"):
    return get(f"content_platforms.{platform}.connected", False)

def set_connected(platform, api_endpoint=None):
    update(f"content_platforms.{platform}.connected", True)
    if api_endpoint:
        update(f"content_platforms.{platform}.api_endpoint", api_endpoint)

def summary():
    schema = load()
    if not schema:
        print("No schema found.")
        return
    c = schema.get("customer", {})
    b = schema.get("brand", {})
    pi = schema.get("pm_intelligence", {})
    runs = len(schema.get("pipeline_runs", []))
    print(f"\nCustomer:    {c.get('name')} — {c.get('business_name')}")
    print(f"Niche:       {b.get('niche_label', b.get('niche'))}")
    print(f"Status:      {c.get('status')}")
    print(f"Runs:        {runs}")
    print(f"Total spent: ${pi.get('cost_tracking', {}).get('total_spent', 0):.4f}")
    print(f"WP:          {'connected' if is_connected('website') else 'not connected'}")
    print(f"Newsletter:  {'connected' if is_connected('newsletter') else 'not connected'}")

if __name__ == "__main__":
    summary()