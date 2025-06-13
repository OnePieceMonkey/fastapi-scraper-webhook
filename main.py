from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

app = FastAPI()

WEBHOOK_URL = "https://n8n.srv850304.hstgr.cloud/webhook-test/webhook-to-doc"

class ScrapeRequest(BaseModel):
    url: str

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

    content = f"""URL: {url}

Titel: {title}

Beschreibung: {description}

Bild: {image_url}

Inhalt:
{text}
"""

    payload = {"title": title, "content": content, "folderId": ""}

    try:
        wh_resp = requests.post(WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        wh_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Senden an n8n: {str(e)}")

    return {"message": "OK – gescraped & an n8n gesendet", "title": title, "image": image_url}
import os

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

