
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import openai
import os

app = FastAPI()

WEBHOOK_URL = "https://n8n.srv850304.hstgr.cloud/webhook-test/webhook-to-doc"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

class ScrapeRequest(BaseModel):
    url: str

def classify_content(text: str) -> str:
    if not OPENAI_API_KEY:
        return "unkategorisiert"

    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Du bist ein Content-Classifier. Kategorisiere den folgenden Text als 'technisch', 'faq' oder 'sonstiges'."},
                {"role": "user", "content": text[:1000]}
            ],
            max_tokens=10,
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        return result
    except Exception as e:
        return f"Fehler bei Kategorisierung: {str(e)}"

@app.post("/scrape-and-send")
def scrape_and_send(data: ScrapeRequest):
    url = data.url

    try:
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Abrufen der URL: {str(e)}")

    soup = BeautifulSoup(resp.text, 'html.parser')
    for tag in soup(["script", "style", "noscript", "form", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = ' '.join(soup.stripped_strings)
    title = soup.title.string.strip() if soup.title else "Ohne Titel"

    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    description = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

    og_image = soup.find("meta", property="og:image")
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else ""

    img_tags = soup.find_all("img")
    images = []
    for img in img_tags:
        src = img.get("src")
        alt = img.get("alt", "").strip()
        if src:
            full_url = urljoin(url, src)
            images.append({
                "url": full_url,
                "description": alt or "kein Alt-Text"
            })

    category = classify_content(text)

    payload = {
        "url": url,
        "title": title,
        "content": text,
        "category": category,
        "images": images
    }

    try:
        wh_resp = requests.post(WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        wh_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Senden an n8n: {str(e)}")

    return {
        "message": "Scraping abgeschlossen & an n8n gesendet.",
        "title": title,
        "category": category,
        "image_count": len(images)
    }
