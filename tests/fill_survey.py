"""
Preenche o inquérito 10 vezes com respostas aleatórias via Playwright.
"""

import random
import time
from playwright.sync_api import sync_playwright

URL = "https://survey-engajamento-retencao-427580506042.us-central1.run.app"
TOTAL_RUNS = 10


AREAS = [
    "Operações", "Produto", "Comercial", "Tecnologia",
    "RH", "Financeiro", "Marketing", "Logística",
    "Atendimento", "Data Science",
]

TEMPOS = [
    "0-6", "6-12", "12-18", "18-24", "24-30",
    "30-36", "36-42", "42-48", "48-54", "54-60", "60+",
]

PROXIMIDADES = [
    "varias_dia", "1_dia", "1_semana",
    "1_mes", "menos_1_mes", "sem_contato",
]


def fill_survey(page, run_number):
    page.goto(URL, wait_until="networkidle")

    # Limpar localStorage para começar limpo
    page.evaluate("localStorage.removeItem('sv3')")
    page.reload(wait_until="networkidle")

    # Preencher identificação do respondente
    page.fill("#id_area", random.choice(AREAS))
    page.select_option("#id_tempo", random.choice(TEMPOS))
    page.select_option("#id_proximidade", random.choice(PROXIMIDADES))

    # Pegar todos os radio buttons agrupados por name
    radio_groups = page.evaluate("""
        () => {
            const names = new Set();
            document.querySelectorAll('input[type="radio"]').forEach(r => names.add(r.name));
            return Array.from(names);
        }
    """)

    print(f"  Run {run_number}: {len(radio_groups)} grupos de radio encontrados")

    # Para cada grupo, escolher um valor aleatório (1-5)
    for name in radio_groups:
        value = random.randint(1, 5)
        page.evaluate(f"""
            () => {{
                const radio = document.querySelector('input[name="{name}"][value="{value}"]');
                if (radio) {{
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
        """)

    # Preencher perguntas abertas
    open_eng_options = [
        "Contratos concluídos e faturamento",
        "Retenção operacional e DAU/MAU",
        "Score de habitualidade",
        "Engajamento com ofertas",
        "Tempo até primeiro frete",
        "Avaliações e taxa de atendimento",
        "Notificações e sessões no app",
        "Candidaturas e visualizações de frete",
        "Score do motorista",
        "Perfil completo e preferências",
    ]
    open_ret_options = [
        "Churn por janela temporal",
        "Retenção D30/D60/D90",
        "Faturamento mensal e pagamentos",
        "Contratos cancelados e remoções",
        "CNH vencendo e documentos",
        "Sinais clássicos de churn",
        "Queda de atividade e faturamento",
        "Distância ao ponto de coleta",
        "Bloqueios por empresa",
        "Alertas automatizados",
    ]

    page.fill("#open_eng", random.choice(open_eng_options))
    page.fill("#open_ret", random.choice(open_ret_options))

    # Submeter
    page.click("#submitBtn")

    # Aguardar resposta (sucesso ou erro)
    try:
        page.wait_for_selector("#thankyou", state="visible", timeout=15000)
        print(f"  Run {run_number}: OK - resposta enviada")
        return True
    except Exception as e:
        # Verificar se tem alert de erro
        alert = page.query_selector(".alert.show")
        if alert:
            print(f"  Run {run_number}: FALHA - {alert.inner_text()}")
        else:
            print(f"  Run {run_number}: FALHA - {e}")
        return False


def main():
    print(f"Preenchendo inquérito {TOTAL_RUNS} vezes em {URL}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        success = 0
        for i in range(1, TOTAL_RUNS + 1):
            page = context.new_page()
            try:
                if fill_survey(page, i):
                    success += 1
            except Exception as e:
                print(f"  Run {i}: ERRO - {e}")
            finally:
                page.close()
            time.sleep(0.5)

        browser.close()

    print(f"\nResultado: {success}/{TOTAL_RUNS} respostas enviadas com sucesso")


if __name__ == "__main__":
    main()
