import csv
import io
import re
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.cloud import storage

app = FastAPI(title="Inquérito - Engajamento e Retenção")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BUCKET_NAME = "survey-engajamento-retencao"
CSV_DIR = "respostas"

HEADERS = ["timestamp", "area_atuacao", "tempo_atuacao", "proximidade_motorista", "secao", "id", "metrica", "impacto"]


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _read_existing_csv(bucket, filename: str) -> str | None:
    blob = bucket.blob(filename)
    if blob.exists():
        return blob.download_as_text()
    return None


def _append_rows(existing_csv: str | None, rows: list, headers: list = HEADERS) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    if existing_csv:
        output.write(existing_csv)
        if not existing_csv.endswith("\n"):
            output.write("\n")
    else:
        writer.writerow(headers)

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/respostas")
async def salvar_respostas(request: Request):
    data = await request.json()

    if not data or "respostas" not in data:
        return JSONResponse(
            {"error": "JSON inválido. Envie {respostas: [...]}"}, status_code=400
        )

    timestamp = data.get("timestamp", datetime.utcnow().isoformat())
    area_atuacao = data.get("area_atuacao", "")
    tempo_atuacao = data.get("tempo_atuacao", "")
    proximidade = data.get("proximidade_motorista", "")
    respostas = data["respostas"]
    open_eng = data.get("open_engajamento", "")
    open_outras = data.get("open_outras", "")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # Agrupar por seção
    por_secao: dict[str, list] = {}
    all_rows = []
    for r in respostas:
        secao = r.get("secao", "outros")
        row = [
            timestamp,
            area_atuacao,
            tempo_atuacao,
            proximidade,
            secao,
            r.get("id", ""),
            r.get("metrica", ""),
            r.get("impacto", ""),
        ]
        all_rows.append(row)
        por_secao.setdefault(secao, []).append(row)

    # CSV por tema
    arquivos = []
    for secao, rows in por_secao.items():
        slug = _slugify(secao)
        filename = f"{CSV_DIR}/{slug}.csv"
        existing = _read_existing_csv(bucket, filename)
        updated = _append_rows(existing, rows)
        blob = bucket.blob(filename)
        blob.upload_from_string(updated, content_type="text/csv")
        arquivos.append(filename)

    # Consolidado
    consolidado_file = f"{CSV_DIR}/consolidado.csv"
    existing_consolidado = _read_existing_csv(bucket, consolidado_file)
    updated_consolidado = _append_rows(existing_consolidado, all_rows)
    blob = bucket.blob(consolidado_file)
    blob.upload_from_string(updated_consolidado, content_type="text/csv")

    # Perguntas abertas
    if open_eng or open_outras:
        open_file = f"{CSV_DIR}/perguntas_abertas.csv"
        open_headers = ["timestamp", "area_atuacao", "tempo_atuacao", "proximidade_motorista", "maior_impacto", "outras_metricas"]
        existing_open = _read_existing_csv(bucket, open_file)
        updated_open = _append_rows(
            existing_open, [[timestamp, area_atuacao, tempo_atuacao, proximidade, open_eng, open_outras]], headers=open_headers
        )
        blob = bucket.blob(open_file)
        blob.upload_from_string(updated_open, content_type="text/csv")
        arquivos.append(open_file)

    return {
        "ok": True,
        "linhas_adicionadas": len(all_rows),
        "arquivos_por_tema": arquivos,
        "consolidado": f"gs://{BUCKET_NAME}/{consolidado_file}",
    }


# Serve frontend — must be last
app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="frontend")
