import functions_framework
import csv
import io
import re
from datetime import datetime
from google.cloud import storage

BUCKET_NAME = "tschmitz-data-science-site"
CSV_DIR = "respostas"
CSV_CONSOLIDADO = "respostas/consolidado.csv"

HEADERS = ["timestamp", "secao", "id", "metrica", "impacto_engajamento", "impacto_retencao"]


def _slugify(text):
    """Converte nome de seção em slug para nome de arquivo."""
    text = text.lower().strip()
    text = re.sub(r'^\d+\.\s*', '', text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def _read_existing_csv(bucket, filename):
    blob = bucket.blob(filename)
    if blob.exists():
        return blob.download_as_text()
    return None


def _append_rows(existing_csv, rows, headers=HEADERS):
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


@functions_framework.http
def salvar_respostas(request):
    # CORS
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    cors_headers = {"Access-Control-Allow-Origin": "*"}

    if request.method != "POST":
        return ({"error": "Use POST"}, 405, cors_headers)

    data = request.get_json(silent=True)
    if not data or "respostas" not in data:
        return ({"error": "JSON inválido. Envie {respostas: [...]}"}, 400, cors_headers)

    timestamp = data.get("timestamp", datetime.utcnow().isoformat())
    respostas = data["respostas"]
    open_eng = data.get("open_engajamento", "")
    open_ret = data.get("open_retencao", "")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # Agrupar respostas por seção
    por_secao = {}
    all_rows = []
    for r in respostas:
        secao = r.get("secao", "outros")
        row = [
            timestamp,
            secao,
            r.get("id", ""),
            r.get("metrica", ""),
            r.get("engajamento", ""),
            r.get("retencao", ""),
        ]
        all_rows.append(row)
        por_secao.setdefault(secao, []).append(row)

    # Salvar CSV por tema/seção
    arquivos = []
    for secao, rows in por_secao.items():
        slug = _slugify(secao)
        filename = f"{CSV_DIR}/{slug}.csv"
        existing = _read_existing_csv(bucket, filename)
        updated = _append_rows(existing, rows)
        blob = bucket.blob(filename)
        blob.upload_from_string(updated, content_type="text/csv")
        arquivos.append(filename)

    # Salvar consolidado
    existing_consolidado = _read_existing_csv(bucket, CSV_CONSOLIDADO)
    updated_consolidado = _append_rows(existing_consolidado, all_rows)
    blob = bucket.blob(CSV_CONSOLIDADO)
    blob.upload_from_string(updated_consolidado, content_type="text/csv")

    # Salvar perguntas abertas
    if open_eng or open_ret:
        open_file = f"{CSV_DIR}/perguntas_abertas.csv"
        open_headers = ["timestamp", "maior_impacto_engajamento", "maior_impacto_retencao"]
        existing_open = _read_existing_csv(bucket, open_file)
        updated_open = _append_rows(existing_open, [[timestamp, open_eng, open_ret]], headers=open_headers)
        blob = bucket.blob(open_file)
        blob.upload_from_string(updated_open, content_type="text/csv")
        arquivos.append(open_file)

    return ({
        "ok": True,
        "linhas_adicionadas": len(all_rows),
        "arquivos_por_tema": arquivos,
        "consolidado": f"gs://{BUCKET_NAME}/{CSV_CONSOLIDADO}",
    }, 200, cors_headers)
