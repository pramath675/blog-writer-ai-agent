#!/usr/bin/env python3
"""
Automated Blog Writer Agent
Usage:
    export OPENAI_API_KEY="sk-..."
    python agent.py --topic "Your topic here" --tone friendly --words 800
Outputs:
    writes markdown to ./output/<slug>/post.md
    writes json metadata to ./output/<slug>/metadata.json
"""

import os
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv
import openai

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in environment")

openai.api_key = OPENAI_API_KEY


def slugify(s):
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def call_model(system_prompt, user_prompt, max_tokens=800, temperature=0.2):
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return resp["choices"][0]["message"]["content"].strip()


def generate_title_and_headlines(topic, tone):
    system = "You are a helpful editor who creates SEO-friendly titles and headline variants."
    prompt = f"""Topic: {topic}
Tone: {tone}

Return a JSON with:
- title: a single SEO-friendly clickable title (<= 70 chars)
- headline_variations: list of 3 alternative headlines
"""
    out = call_model(system, prompt, max_tokens=200)
    try:
        return json.loads(out)
    except:
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return {"title": lines[0], "headline_variations": lines[1:4]}


def generate_outline(topic, tone, sections=5):
    system = "You are an experienced editor who drafts article outlines."
    prompt = f"""Topic: {topic}
Tone: {tone}
Create a {sections}-section outline. Return JSON: {{
  "outline": [
    {{"heading": "", "summary": ""}}
  ]
}}"""
    out = call_model(system, prompt, max_tokens=400)
    try:
        return json.loads(out)["outline"]
    except:
        parts = [p.strip() for p in out.split("\n\n") if p.strip()]
        outline = []
        for p in parts[:sections]:
            if ":" in p:
                h, s = p.split(":", 1)
            else:
                h = p.split("\n")[0]
                s = " ".join(p.split("\n")[1:])
            outline.append({"heading": h.strip(), "summary": s.strip()})
        return outline


def generate_full_post(title, outline, tone, word_target):
    system = "You are an expert copywriter. Use the provided outline to write a consistent article."
    outline_text = "\n".join(
        f"{i+1}. {sec['heading']}\n{sec.get('summary','')}"
        for i, sec in enumerate(outline)
    )
    prompt = f"""Title: {title}
Tone: {tone}
Word target: {word_target}

Outline:
{outline_text}

Write a full article in Markdown. Include headings matching the outline. Add a short intro and a conclusion.
"""
    return call_model(system, prompt, max_tokens=1600, temperature=0.3)


def generate_seo_assets(title, topic):
    system = "You are an SEO expert."
    prompt = f"""Title: {title}
Topic: {topic}
Return JSON: {{
 "meta_description": "",
 "keywords": ["kw1", "kw2"]
}}"""
    out = call_model(system, prompt, max_tokens=200)
    try:
        return json.loads(out)
    except:
        return {"meta_description": out.split("\n")[0], "keywords": []}


def generate_image_prompts(outline):
    system = "You are a creative art director suggesting image prompts and captions."
    outline_text = "\n".join([sec["heading"] for sec in outline])
    prompt = f"""Headings:
{outline_text}

Return JSON: [
  {{"prompt": "", "caption": ""}}
]"""
    out = call_model(system, prompt, max_tokens=400)
    try:
        return json.loads(out)
    except:
        return [{"prompt": f"Photo of {outline[0]['heading']}", "caption": outline[0]['heading']}]


def save_outputs(topic, title, headlines, outline, post, seo, images):
    slug = slugify(topic + "-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"))
    outdir = os.path.join("output", slug)
    os.makedirs(outdir, exist_ok=True)
    meta = {
        "topic": topic,
        "title": title,
        "headlines": headlines,
        "outline": outline,
        "seo": seo,
        "images": images,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
    with open(os.path.join(outdir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    with open(os.path.join(outdir, "post.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(post)

    print(f"Saved outputs to {outdir}")
    return outdir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=True)
    p.add_argument("--tone", default="friendly")
    p.add_argument("--words", type=int, default=800)
    args = p.parse_args()

    topic = args.topic
    tone = args.tone
    word_target = args.words

    print("Generating title & headlines...")
    th = generate_title_and_headlines(topic, tone)
    title = th.get("title") if isinstance(th, dict) else str(th)
    headlines = th.get("headline_variations", []) if isinstance(th, dict) else []

    print("Generating outline...")
    outline = generate_outline(topic, tone, sections=5)

    print("Generating post...")
    post = generate_full_post(title, outline, tone, word_target)

    print("Generating SEO assets...")
    seo = generate_seo_assets(title, topic)

    print("Generating image prompts...")
    images = generate_image_prompts(outline)

    outdir = save_outputs(topic, title, headlines, outline, post, seo, images)
    print("Done. Check:", outdir)


if _name_ == "_main_":
    main()