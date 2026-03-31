import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCHEMA_FILE = "customer_schema.json"

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def now():
    return datetime.now(timezone.utc).isoformat()

def ask(question, hint=None, multiline=True):
    print(f"\n{question}")
    if hint:
        print(f"  ({hint})")
    print()
    if multiline:
        print("  Type your answer, then press Enter twice when done:")
        lines = []
        while True:
            line = input("  ")
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        return " ".join(l for l in lines if l).strip()
    else:
        return input("  > ").strip()

def detect_niche(answers):
    import urllib.request
    import json
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "general"
    prompt = f"""Based on these answers from a new customer, identify their business niche.
    
What they do: {answers.get('what_you_do', '')}
Their opinion: {answers.get('point_of_view', '')}
Their audience: {answers.get('audience', '')}

Return ONLY a JSON object with these fields:
{{
  "niche": "one of: food_lifestyle, creative_arts, business_finance, health_fitness, education_coaching, automotive_lifestyle, tech_gaming, travel_outdoor, fashion_beauty, sports_fitness, general",
  "niche_label": "human readable label like Food + Lifestyle",
  "topic_keywords": ["list", "of", "8", "relevant", "topic", "keywords"],
  "tone_adjectives": ["list", "of", "4", "tone", "words", "derived", "from", "their", "answers"]
}}

Return only the JSON, no other text."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            text = result["content"][0]["text"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
    except Exception as e:
        print(f"  Niche detection failed: {e}")
        return {
            "niche": "general",
            "niche_label": "General Business",
            "topic_keywords": ["content", "business", "growth", "audience"],
            "tone_adjectives": ["clear", "helpful", "direct", "friendly"]
        }

def build_tone_profile(answers, niche_data):
    return {
        "source": "onboarding_questions",
        "confidence": "medium",
        "voice": f"derived from: {answers.get('what_you_do', '')[:100]}",
        "sentence_style": "short paragraphs, conversational, direct",
        "person": "second",
        "formality": "conversational",
        "emotion": "warm and authentic",
        "forbidden_words": ["leverage", "synergy", "optimize", "unlock", "game-changer"],
        "signature_phrases": [answers.get('sign_off', 'Until next time').strip()],
        "never_sounds_like": answers.get('never_sounds_like', ''),
        "point_of_view": answers.get('point_of_view', ''),
        "audience_description": answers.get('audience', ''),
        "tone_adjectives": niche_data.get('tone_adjectives', []),
        "tone_version": 1,
        "last_updated": now(),
        "tone_history": []
    }

def build_schema(answers, niche_data, has_newsletter):
    business_name = answers.get('business_name', 'My Business')
    slug = business_name.lower().strip().replace(' ', '-').replace("'", "")

    return {
        "schema_version": "1.0",
        "product": "agenticles",
        "customer": {
            "id": f"customer_{int(datetime.now().timestamp())}",
            "name": answers.get('customer_name', ''),
            "email": answers.get('customer_email', ''),
            "business_name": business_name,
            "created_at": now(),
            "plan": "starter",
            "status": "onboarding",
            "onboarding_complete": False
        },
        "brand": {
            "business_name": business_name,
            "niche": niche_data.get('niche', 'general'),
            "niche_label": niche_data.get('niche_label', 'General'),
            "what_they_do": answers.get('what_you_do', ''),
            "audience": answers.get('audience', ''),
            "point_of_view": answers.get('point_of_view', ''),
            "never_sounds_like": answers.get('never_sounds_like', ''),
            "sign_off": answers.get('sign_off', '')
        },
        "tone_profile": build_tone_profile(answers, niche_data),
        "content_platforms": {
            "website": {
                "platform": "wordpress",
                "url": f"https://{slug}.com",
                "api_endpoint": None,
                "category_id": 1,
                "author_id": 1,
                "default_status": "draft",
                "connected": False,
                "post_format": {
                    "min_words": 350,
                    "max_words": 600,
                    "requires_exercise_block": False,
                    "heading_structure": ["h2", "h3"],
                    "always_includes_signoff": True
                }
            },
            "newsletter": {
                "platform": "brevo" if has_newsletter else None,
                "enabled": has_newsletter,
                "sender_name": business_name,
                "sender_email": answers.get('customer_email', ''),
                "default_status": "draft",
                "list_id": None,
                "connected": False,
                "post_format": {
                    "min_words": 150,
                    "max_words": 250,
                    "no_headers": True,
                    "reads_like_email": True,
                    "always_includes_signoff": True
                }
            },
            "social": []
        },
        "media_library": {
            "source": "unsplash",
            "unsplash_keywords": niche_data.get('topic_keywords', [])[:3],
            "used_photos": [],
            "total_photos": 0,
            "fallback_source": "unsplash"
        },
        "topic_intelligence": {
            "niche_keywords": niche_data.get('topic_keywords', []),
            "topic_pool": [],
            "used_topics": [],
            "retired_topics": [],
            "suggested_topics": [],
            "topic_version": 1
        },
        "pipeline_runs": [],
        "feedback_log": [],
        "pm_intelligence": {
            "quality_scores": [],
            "tone_drift_alerts": [],
            "topic_gap_suggestions": [],
            "pipeline_health": {
                "consecutive_successes": 0,
                "consecutive_failures": 0,
                "last_failure": None,
                "last_failure_reason": None
            },
            "cost_tracking": {
                "total_spent": 0.00,
                "runs_this_month": 0,
                "avg_cost_per_run": 0.00,
                "month_start": None
            },
            "content_quality_baseline": None,
            "last_analysis": None
        },
        "run_summary_log": []
    }

def run_onboarding():
    load_env()

    print("\n" + "="*50)
    print("Welcome to Agenticles")
    print("Let's set up your business in a few minutes.")
    print("="*50)

    answers = {}

    # Basic info
    print("\n--- Your details ---")
    answers['customer_name'] = ask("What's your name?", multiline=False)
    answers['customer_email'] = ask("What's your email address?", multiline=False)
    answers['business_name'] = ask("What's your business called?", multiline=False)

    # The 5 tone questions
    print("\n--- Tell us about your business ---")

    answers['what_you_do'] = ask(
        "What do you do? Explain it like you're telling a friend at a bar.",
        hint="Casual, no jargon — 2 or 3 sentences is perfect"
    )

    answers['point_of_view'] = ask(
        "What does your industry get wrong that you believe differently about?",
        hint="This is your point of view — what makes your content worth reading"
    )

    answers['audience'] = ask(
        "Who is your content for? Describe one specific person who would love it.",
        hint="Not a demographic — a real person. The more specific, the better"
    )

    answers['never_sounds_like'] = ask(
        "What do you never want to sound like?",
        hint="A word, a brand, a person — anything that represents the wrong tone"
    )

    answers['sign_off'] = ask(
        "Write your sign-off — the last line you'd put at the bottom of every post or email.",
        hint="This anchors every piece of content we produce for you",
        multiline=False
    )

    # Newsletter
    print("\n--- One more thing ---")
    print("\nWe strongly recommend setting up a newsletter.")
    print("It's the fastest way to build a loyal audience.")
    print("You won't send anything until you're ready.\n")
    newsletter_choice = ask("Set up a newsletter? (yes/no)", multiline=False).lower()
    has_newsletter = newsletter_choice in ['yes', 'y', 'yeah', 'yep', 'sure']

    # Detect niche
    print("\n  Analyzing your answers...")
    niche_data = detect_niche(answers)
    print(f"  Niche detected: {niche_data.get('niche_label', 'General')}")

    # Build schema
    schema = build_schema(answers, niche_data, has_newsletter)

    # Save schema
    with open(SCHEMA_FILE, 'w') as f:
        json.dump(schema, f, indent=2)

    # Summary
    print("\n" + "="*50)
    print("ONBOARDING COMPLETE")
    print("="*50)
    print(f"Business:    {answers['business_name']}")
    print(f"Niche:       {niche_data.get('niche_label', 'General')}")
    print(f"Newsletter:  {'Yes' if has_newsletter else 'Skipped for now'}")
    print(f"Schema:      {SCHEMA_FILE} created")
    print("\nNext step: connect your platforms and run the pipeline.")
    print("="*50)

    return schema

if __name__ == "__main__":
    run_onboarding()