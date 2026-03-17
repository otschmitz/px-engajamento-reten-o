"""
Teste E2E: responde o questionario (Google Forms style) e verifica artefatos no GCS.
"""
import subprocess
import time
from playwright.sync_api import sync_playwright, expect

BASE_URL = "https://survey-engajamento-retencao-427580506042.us-central1.run.app"
BUCKET = "gs://survey-engajamento-retencao/respostas"


def gcs_list():
    r = subprocess.run(["gcloud", "storage", "ls", f"{BUCKET}/"], capture_output=True, text=True)
    return r.stdout.strip().splitlines() if r.returncode == 0 else []


def gcs_cat(path):
    r = subprocess.run(["gcloud", "storage", "cat", path], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def gcs_cleanup():
    subprocess.run(["gcloud", "storage", "rm", "-r", f"{BUCKET}/"], capture_output=True, text=True)


def test_survey():
    print("\n=== Limpando dados anteriores ===")
    gcs_cleanup()

    print("\n=== Teste E2E ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Acessando formulario...")
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        expect(page.locator(".card-header h1")).to_be_visible()
        print("Pagina carregada OK")

        # Clicar 3a opcao (Moderado) de cada grid
        grids = page.locator("table.likert-grid")
        grid_count = grids.count()
        print(f"Grids encontrados: {grid_count}")

        for gi in range(grid_count):
            grid = grids.nth(gi)
            rows = grid.locator("tbody tr")
            n = rows.count()
            for ri in range(n):
                # 3a opcao = indice 2 dos g-radio dentro da row
                rows.nth(ri).locator(".g-radio").nth(2).click()
            print(f"  Grid {gi+1}: {n} linhas respondidas")

        # Verificar progresso
        page.wait_for_timeout(500)
        pct = page.locator("#pbar").evaluate("el => el.style.width")
        print(f"Progresso: {pct}")

        # Preencher abertas
        page.fill("#open_eng", "Teste auto - engajamento")
        page.fill("#open_ret", "Teste auto - retencao")

        # Enviar
        print("Enviando...")
        page.locator("#submitBtn").click()
        page.wait_for_timeout(3000)

        expect(page.locator(".thankyou h2")).to_be_visible()
        print("Tela de agradecimento OK")

        browser.close()

    # Verificar GCS
    print("\n=== Verificando artefatos ===")
    time.sleep(2)
    files = gcs_list()
    print(f"Arquivos: {len(files)}")
    for f in files:
        print(f"  {f.split('/')[-1]}")

    assert len(files) >= 3, f"Esperado >=3 arquivos, tem {len(files)}"

    consolidado = [f for f in files if "consolidado.csv" in f]
    assert consolidado, "consolidado.csv nao encontrado"
    content = gcs_cat(consolidado[0])
    lines = content.strip().split("\n")
    print(f"\nConsolidado: {len(lines)-1} respostas")
    assert len(lines) >= 49

    abertas = [f for f in files if "perguntas_abertas.csv" in f]
    assert abertas, "perguntas_abertas.csv nao encontrado"
    assert "Teste auto" in gcs_cat(abertas[0])

    temas = [f for f in files if "consolidado.csv" not in f and "perguntas_abertas.csv" not in f]
    print(f"CSVs por tema: {len(temas)}")
    assert len(temas) >= 15

    print("\n=== TODOS OS TESTES PASSARAM ===")


if __name__ == "__main__":
    test_survey()
    print("\nDados mantidos no bucket.")
