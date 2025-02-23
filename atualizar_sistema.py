import os
import subprocess
import time
import requests

# Caminho do repositório local
PROJETO_PATH = os.path.dirname(os.path.abspath(__file__))
GITHUB_REPO = "https://github.com/AriHenrique/notificacao-whats-condominio/commits/main"

def verificar_atualizacao():
    """Verifica se há uma nova atualização no GitHub"""
    try:
        # Obtém o commit mais recente do GitHub
        response = requests.get(GITHUB_REPO, timeout=10)
        response.raise_for_status()
        latest_commit = response.json()["sha"]

        # Obtém o commit atual local
        local_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJETO_PATH
        ).strip().decode("utf-8")

        if local_commit == latest_commit:
            return False  # Nenhuma atualização disponível

        # Executa o git pull silenciosamente
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=PROJETO_PATH,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Reinstala dependências do Python
        subprocess.run(
            ["pip", "install", "-r", "requirements.txt"],
            cwd=PROJETO_PATH,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Reinstala dependências do Node.js
        subprocess.run(
            ["npm", "install"],
            cwd=os.path.join(PROJETO_PATH, "back"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return True

    except Exception:
        return False  # Falhou ao verificar atualizações

def encerrar_processos():
    """Finaliza os processos do Node.js e do Python"""
    subprocess.run(["taskkill", "/F", "/IM", "node.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["taskkill", "/F", "/IM", "python.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)  # Espera antes de reiniciar

def reiniciar_servidores():
    """Reinicia o backend Flask e o Node.js silenciosamente"""
    script_bat = os.path.join(PROJETO_PATH, "start.bat")
    subprocess.Popen(["cmd.exe", "/c", "start", "/B", script_bat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    if verificar_atualizacao():
        print('atualizando sistema')
        encerrar_processos()
        reiniciar_servidores()
    else:
        print('nao possui atualizacao')
