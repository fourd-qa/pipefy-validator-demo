import json
import os
import time

RESULTS_DIR = os.path.join(os.getcwd(), 'results')
PROGRESS_FILE = os.path.join(RESULTS_DIR, 'progress.json')
LOG_FILE = os.path.join(RESULTS_DIR, 'console.log')

_start_time = None


class ProgressLibrary:
    """Biblioteca auxiliar para cronômetro, progresso e logs."""

    def iniciar_cronometro(self):
        global _start_time
        _start_time = time.time()
        os.makedirs(RESULTS_DIR, exist_ok=True)

    def limpar_progresso(self):
        for f in [PROGRESS_FILE, LOG_FILE]:
            if os.path.exists(f):
                os.remove(f)

    def atualizar_progresso(self, step, total, label, status='running'):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        data = {
            "step": int(step),
            "total": int(total),
            "label": str(label),
            "status": str(status)
        }
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(data, f)

    def registrar_log(self, mensagem):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        ts = time.strftime('%H:%M:%S')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {mensagem}\n")

    def registrar_tempo_total(self):
        if _start_time:
            duracao = round(time.time() - _start_time, 1)
            return f"{duracao}s"
        return "N/A"
