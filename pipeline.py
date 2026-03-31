import os
import json
import random
import base64
import urllib.request
import urllib.error
import urllib.parse
import re
from datetime import datetime, timezone
import customer_schema as schema

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

def wp_auth_header():
    username = os.environ.get("WP_USERNAME")
    password = os.environ.get("WP_APP_PASSWORD")
    credentials = f"{username}:{password}"
    token = base64.b64encode(credentials.encode()).decode()
    return f"Basic {token}"

def get_dropbox_token():
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    if not all([app_key, app_secret, refresh_token]):
        return None
    credentials = base64.b64encode(f"{app_key}:{app_secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }).encode()
    req = urllib.request.Request(
        "https://api.dropbox.com/oauth2/token",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            return result.get("access_token")
    except:
        return None

def get_existing_wp_titles():
    wp_config = schema.get_platform_config("website")
    api_endpoint = wp_config.get("api_endpoint")
    if not api_endpoint:
        return []
    print("Fetching existing WordPress posts...")
    titles = []
    page = 1
    while True:
        url = f"{api_endpoint}/posts?per_page=100&page={page}&status=publish,draft"
        req = urllib.request.Request(url, headers={"Authorization": wp_auth_header()})
        try:
            with urllib.request.urlopen(req) as r:
                posts = json.loads(r.read().decode())
                if not posts:
                    break
                for post in posts:
                    titles.append(post["title"]["rendered"].lower())
                page += 1
        except:
            break
    print(f"Found {len(titles)} existing posts.")
    return titles

def pick_topic(existing_titles):
    niche_keywords = schema.get_niche_keywords()
    used_topics = schema.get_used_topics()
    topic_pool = schema.get_topic_pool()

    available = [t for t in topic_pool if t not in used_topics]

    if len(available) <= 3:
        print(f"WARNING: Only {len(available)} topics remaining in pool. Add more soon.")

    if not available:
        print("Topic pool empty — using niche keywords to generate topic.")
        return f"how {random.choice(niche_keywords)} affects your business" if niche_keywords else "content strategy tips"

    random.shuffle(available)
    for topic in available:
        topic_words = set(topic.lower().split())
        too_similar = False
        for title in existing_titles:
            title_words = set(title.lower().split())
            if len(topic_words & title_words) >= 3:
                too_similar = True
                break
        if not too_similar:
            print(f"Selected topic: {topic}")
            return topic

    topic = available[0]
    print(f"Selected topic (all similar): {topic}")
    return topic

def get_unsplash_photo(keywords):
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None, None
    query = "+".join(keywords[:2]) if keywords else "business"
    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Client-ID {access_key}"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            photo_url = result["urls"]["regular"]
            photo_id = result["id"]
            photo_req = urllib.request.Request(photo_url)
            with urllib.request.urlopen(photo_req) as pr:
                return pr.read(), f"unsplash-{photo_id}.jpg"
    except Exception as e:
        print(f"Unsplash fetch failed: {e}")
        return None, None

def upload_photo_to_wp(photo_bytes, filename, api_endpoint):
    print("Uploading photo to WordPress...")
    req = urllib.request.Request(
        f"{api_endpoint}/media",
        data=photo_bytes,
        headers={
            "Authorization": wp_auth_header(),
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            media_id = result.get("id")
            print(f"Photo uploaded — media ID: {media_id}")
            return media_id
    except Exception as e:
        print(f"Photo upload failed: {e}")
        return None

def research_topic(topic):
    print(f"Researching: {topic}...")
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        print("No Perplexity API key — skipping research.")
        return f"Write about: {topic}"
    niche = schema.get("brand.niche_label", "general")
    payload = json.dumps({
        "model": "sonar",
        "messages": [{
            "role": "user",
            "content": f"Research this topic for a {niche} content creator: {topic}. Return key findings, data points, and insights in plain text paragraphs. No bullet points or markdown."
        }],
        "max_tokens": 1000
    }).encode()
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            content = result["choices"][0]["message"]["content"]
            print("Research complete.")
            return content
    except Exception as e:
        print(f"Research failed: {e}")
        return f"Write about: {topic}"

def draft_content(topic, research):
    print("Drafting content...")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    tone = schema.get_tone_profile()
    brand = schema.get("brand", {})
    wp_config = schema.get_platform_config("website")

    system_prompt = f"""You are a content drafter for {brand.get('business_name', 'this business')}.

BUSINESS: {brand.get('what_they_do', '')}
AUDIENCE: {brand.get('audience', '')}
POINT OF VIEW: {brand.get('point_of_view', '')}
NEVER SOUNDS LIKE: {brand.get('never_sounds_like', '')}
SIGN OFF: {tone.get('signature_phrases', [''])[0] if tone.get('signature_phrases') else ''}
TONE: {', '.join(tone.get('tone_adjectives', ['conversational', 'direct']))}

RULES:
- Write in second person ("you")
- Short paragraphs, 1-2 sentences
- Plain language, no jargon
- Never use: {', '.join(tone.get('forbidden_words', []))}
- Always end with the sign-off above
- Use HTML heading tags <h2> and <h3> — never markdown ## symbols

BLOG POST: {wp_config.get('min_words', 350)}-{wp_config.get('max_words', 600)} words
NEWSLETTER: 150-250 words, no headers, reads like a personal email

OUTPUT FORMAT — return exactly this:
---WORDPRESS_DRAFT---
TITLE: [direct title, nothing else]
CONTENT:
[full post with <h2> and <h3> tags]
CATEGORY: General
STATUS: draft
---END_WORDPRESS_DRAFT---

---NEWSLETTER_DRAFT---
SUBJECT: [subject line]
CONTENT:
[newsletter content]
---END_NEWSLETTER_DRAFT---"""

    payload = json.dumps({
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 2000,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": f"Topic: {topic}\n\nResearch:\n{research}"
        }]
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
            content = result["content"][0]["text"]
            print("Drafting complete.")
            return content
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Claude API failed: {e} — {error_body}")
        return None

def parse_drafts(output):
    wp_match = re.search(r'---WORDPRESS_DRAFT---(.*?)---END_WORDPRESS_DRAFT---', output, re.DOTALL)
    nl_match = re.search(r'---NEWSLETTER_DRAFT---(.*?)---END_NEWSLETTER_DRAFT---', output, re.DOTALL)
    wp_block = wp_match.group(1).strip() if wp_match else ""
    nl_block = nl_match.group(1).strip() if nl_match else ""
    title_match = re.search(r'TITLE:\s*(.+)', wp_block)
    content_match = re.search(r'CONTENT:\s*\n(.*?)(?=\nCATEGORY:)', wp_block, re.DOTALL)
    subject_match = re.search(r'SUBJECT:\s*(.+)', nl_block)
    nl_content_match = re.search(r'CONTENT:\s*\n(.*)', nl_block, re.DOTALL)
    return {
        "wp_title": title_match.group(1).strip() if title_match else "Untitled",
        "wp_content": content_match.group(1).strip() if content_match else "",
        "nl_subject": subject_match.group(1).strip() if subject_match else "",
        "nl_content": nl_content_match.group(1).strip() if nl_content_match else ""
    }

def push_to_wordpress(title, content, media_id=None):
    wp_config = schema.get_platform_config("website")
    api_endpoint = wp_config.get("api_endpoint")
    if not api_endpoint:
        print("WordPress not connected — skipping publish.")
        return "NOT_CONNECTED"
    print("Pushing to WordPress...")
    payload = {
        "title": title,
        "content": content,
        "status": "draft",
        "categories": [int(wp_config.get("category_id", 1))],
        "author": int(wp_config.get("author_id", 1))
    }
    if media_id:
        payload["featured_media"] = media_id
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{api_endpoint}/posts",
        data=data,
        headers={
            "Authorization": wp_auth_header(),
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            return result.get("link", "No URL returned")
    except urllib.error.HTTPError as e:
        return f"ERROR: {e.read().decode()}"

def push_to_brevo(subject, content, wp_title=""):
    nl_config = schema.get_platform_config("newsletter")
    if not nl_config.get("enabled") or not nl_config.get("connected"):
        print("Newsletter not connected — skipping.")
        return "NOT_CONNECTED"
    print("Pushing to Brevo...")
    business_name = schema.get("brand.business_name", "")
    slug = wp_title.lower().strip()
    for char in ["'", ":", ",", "?", "!"]:
        slug = slug.replace(char, "")
    slug = slug.replace(" ", "-")
    wp_config = schema.get_platform_config("website")
    site_url = wp_config.get("url", "")
    post_url = f"{site_url}/{slug}/"
    html = f"""<html><body style='margin:0;padding:0;background-color:#f9f6f1;'>
<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#f9f6f1;padding:40px 0;'>
<tr><td align='center'>
<table width='600' cellpadding='0' cellspacing='0' style='background-color:#ffffff;padding:48px 40px;font-family:Georgia,serif;color:#1a1a1a;font-size:17px;line-height:1.8;'>
<tr><td>{content.replace(chr(10), '<br>')}</td></tr>
<tr><td style='padding-top:40px;border-top:1px solid #e8e3dc;font-size:13px;color:#888;font-family:Georgia,serif;'>
<a href='{post_url}' style='color:#1a1a1a;text-decoration:none;'>Read the full post →</a> &nbsp;·&nbsp;
<a href='{site_url}' style='color:#1a1a1a;text-decoration:none;'>{business_name}</a>
</td></tr>
</table></td></tr></table></body></html>"""
    api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL", nl_config.get("sender_email", ""))
    payload = json.dumps({
        "name": f"{subject} — draft",
        "subject": subject,
        "sender": {"name": business_name, "email": sender_email},
        "type": "classic",
        "htmlContent": html,
        "status": "draft"
    }).encode()
    req = urllib.request.Request(
        "https://api.brevo.com/v3/emailCampaigns",
        data=payload,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            return result.get("id", "No ID returned")
    except urllib.error.HTTPError as e:
        return f"ERROR: {e.read().decode()}"

def run_pipeline():
    load_env()
    print("\n=== AGENTICLES PIPELINE START ===\n")

    if not schema.load():
        print("ERROR: No customer schema found. Run onboarding.py first.")
        return

    business_name = schema.get("brand.business_name", "your business")
    print(f"Running pipeline for: {business_name}\n")

    existing_titles = get_existing_wp_titles()
    topic = pick_topic(existing_titles)

    media_id = None
    photo_path = None
    unsplash_keywords = schema.get("media_library.unsplash_keywords", [])
    photo_bytes, filename = get_unsplash_photo(unsplash_keywords)
    if photo_bytes:
        wp_config = schema.get_platform_config("website")
        api_endpoint = wp_config.get("api_endpoint")
        if api_endpoint:
            media_id = upload_photo_to_wp(photo_bytes, filename, api_endpoint)
            photo_path = filename

    research = research_topic(topic)
    if not research:
        print("Research failed — stopping.")
        return

    raw_output = draft_content(topic, research)
    if not raw_output:
        print("Drafting failed — stopping.")
        return

    drafts = parse_drafts(raw_output)
    wp_url = push_to_wordpress(drafts["wp_title"], drafts["wp_content"], media_id)
    brevo_id = push_to_brevo(drafts["nl_subject"], drafts["nl_content"], drafts["wp_title"])

    estimated_cost = 0.024
    run_data = {
        "timestamp": now(),
        "topic": topic,
        "wp_url": wp_url,
        "brevo_id": str(brevo_id),
        "photo": photo_path,
        "cost": estimated_cost,
        "success": wp_url not in ["NOT_CONNECTED", ""] and "ERROR" not in str(wp_url),
        "approved": False,
        "quality_score": None,
        "error": None
    }
    schema.log_run(run_data)
    schema.add_used_topic(topic)

    print("\n=== RUN SUMMARY ===")
    print(f"Business:    {business_name}")
    print(f"Topic:       {topic}")
    print(f"Post:        {wp_url}")
    print(f"Newsletter:  {brevo_id}")
    print(f"Photo:       {photo_path or 'none'}")
    print("==================\n")

if __name__ == "__main__":
    run_pipeline()