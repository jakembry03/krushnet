from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory="app/web/static"),
    name="static"
)

templates = Jinja2Templates(
    directory="app/web/templates"
)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "server_time": datetime.now(timezone.utc).isoformat()
    }





