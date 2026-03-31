import os
import json
from datetime import datetime, timezone
import customer_schema as schema

def now():
    return datetime.now(timezone.utc).isoformat()

def score_quality(wp_content, nl_content, tone_profile):
    score = 100
    flags = []

    if not wp_content or len(wp_content.strip()) < 100:
        score -= 40
        flags.append("blog post content missing or too short")

    if not nl_content or len(nl_content.strip()) < 50:
        score -= 20
        flags.append("newsletter content missing or too short")

    wp_words = len(wp_content.split()) if wp_content else 0
    if wp_words < 300:
        score -= 15
        flags.append(f"blog post too short: {wp_words} words")
    elif wp_words > 700:
        score -= 5
        flags.append(f"blog post too long: {wp_words} words")

    nl_words = len(nl_content.split()) if nl_content else 0
    if nl_words < 100:
        score -= 10
        flags.append(f"newsletter too short: {nl_words} words")
    elif nl_words > 300:
        score -= 5
        flags.append(f"newsletter too long: {nl_words} words")

    forbidden = tone_profile.get("forbidden_words", [])
    combined = (wp_content or "") + (nl_content or "")
    for word in forbidden:
        if word.lower() in combined.lower():
            score -= 5
            flags.append(f"forbidden word used: {word}")

    sign_off = tone_profile.get("signature_phrases", [""])[0] if tone_profile.get("signature_phrases") else ""
    if sign_off and sign_off.lower() not in combined.lower():
        score -= 10
        flags.append("sign-off missing from content")

    score = max(0, score)
    return score, flags

def detect_tone_drift(wp_content, tone_profile):
    alerts = []

    if not wp_content:
        return alerts

    words = wp_content.split()
    sentences = wp_content.split('.')
    avg_sentence_length = len(words) / max(len(sentences), 1)

    if avg_sentence_length > 25:
        alerts.append("sentences running long — may feel too formal")

    formal_words = ["furthermore", "however", "nevertheless", "subsequently",
                    "notwithstanding", "aforementioned", "utilize", "endeavor"]
    for word in formal_words:
        if word.lower() in wp_content.lower():
            alerts.append(f"formal word detected: {word}")

    if " I " in wp_content or wp_content.startswith("I "):
        person = tone_profile.get("person", "second")
        if person == "second":
            alerts.append("first person detected — tone profile says second person")

    return alerts

def check_photo_warning(media_library):
    used = len(media_library.get("used_photos", []))
    total = media_library.get("total_photos", 0)
    remaining = total - used

    if total == 0:
        return None

    if remaining <= 1:
        return f"URGENT: Only {remaining} photo(s) remaining — add more immediately"
    elif remaining <= 2:
        return f"WARNING: Only {remaining} photos remaining — add more soon"
    elif remaining <= 3:
        return f"NOTICE: {remaining} photos remaining in library"
    return None

def check_topic_warning(topic_intelligence):
    pool = topic_intelligence.get("topic_pool", [])
    used = topic_intelligence.get("used_topics", [])
    remaining = [t for t in pool if t not in used]

    if len(remaining) <= 5:
        return f"WARNING: Only {len(remaining)} topics remaining — consider generating more"
    elif len(remaining) <= 10:
        return f"NOTICE: {len(remaining)} topics remaining in pool"
    return None

def run_pm_analysis(run_data, wp_content, nl_content):
    current_schema = schema.load()
    if not current_schema:
        print("PM Agent: No schema found.")
        return

    tone_profile = schema.get_tone_profile()
    media_library = current_schema.get("media_library", {})
    topic_intelligence = current_schema.get("topic_intelligence", {})
    brand = current_schema.get("brand", {})

    quality_score, quality_flags = score_quality(wp_content, nl_content, tone_profile)
    tone_alerts = detect_tone_drift(wp_content, tone_profile)
    photo_warning = check_photo_warning(media_library)
    topic_warning = check_topic_warning(topic_intelligence)

    pm_data = {
        "timestamp": now(),
        "run_id": run_data.get("timestamp"),
        "topic": run_data.get("topic"),
        "quality_score": quality_score,
        "quality_flags": quality_flags,
        "tone_alerts": tone_alerts,
        "photo_warning": photo_warning,
        "topic_warning": topic_warning
    }

    current_schema["pm_intelligence"]["quality_scores"].append({
        "timestamp": now(),
        "topic": run_data.get("topic"),
        "score": quality_score,
        "flags": quality_flags
    })

    if tone_alerts:
        current_schema["pm_intelligence"]["tone_drift_alerts"].append({
            "timestamp": now(),
            "alerts": tone_alerts
        })

    schema.save(current_schema)

    print("\n" + "="*50)
    print("PM AGENT ANALYSIS")
    print("-"*50)
    print(f"Business:      {brand.get('business_name', '')}")
    print(f"Topic:         {run_data.get('topic', '')}")
    print(f"Quality score: {quality_score}/100")

    if quality_flags:
        print(f"Quality flags:")
        for flag in quality_flags:
            print(f"  - {flag}")
    else:
        print(f"Quality:       no issues detected")

    if tone_alerts:
        print(f"Tone alerts:")
        for alert in tone_alerts:
            print(f"  - {alert}")
    else:
        print(f"Tone:          consistent with profile")

    if photo_warning:
        print(f"Photos:        {photo_warning}")

    if topic_warning:
        print(f"Topics:        {topic_warning}")

    runs = current_schema.get("pipeline_runs", [])
    cost = current_schema["pm_intelligence"]["cost_tracking"]
    health = current_schema["pm_intelligence"]["pipeline_health"]

    print("-"*50)
    print(f"Total runs:    {len(runs)}")
    print(f"Total spent:   ${cost.get('total_spent', 0):.4f}")
    print(f"Pipeline:      {health.get('consecutive_successes', 0)} consecutive successes")
    print("="*50)

    return pm_data

if __name__ == "__main__":
    current_schema = schema.load()
    if current_schema:
        runs = current_schema.get("pipeline_runs", [])
        scores = current_schema["pm_intelligence"].get("quality_scores", [])
        print(f"\nPM Agent Summary")
        print(f"Total runs: {len(runs)}")
        print(f"Quality scores logged: {len(scores)}")
        if scores:
            avg = sum(s["score"] for s in scores) / len(scores)
            print(f"Average quality score: {avg:.1f}/100")
    else:
        print("No schema found.")