# BACKUP & RESTORE - Pipefy Validator (Demo)

Documento de backup pra sobreviver a formatacao de maquina, perda de HD, ou troca de equipamento.

Ultima analise: 2026-04-29.

---

## 1. PORTABILIDADE DA PASTA

A pasta inteira e portatil. Pode ser movida pra qualquer caminho em qualquer maquina (Windows, Linux, Mac com Docker) sem quebrar funcionalidade.

**Verificado:**
- `server.py` usa `os.getcwd()` em todos os paths internos
- `docker-compose.yml` usa volumes relativos (`./results`, `./config`, `./snapshots`, `./proposals`)
- `pytest.ini` usa caminho relativo (`tests/python`)
- `run-all-tests.ps1` resolve seu proprio diretorio via `Split-Path -Parent $MyInvocation`
- Dockerfile copia `.` (toda a pasta) pra dentro do container

---

## 2. ESTRATEGIA DE BACKUP (3 CAMADAS)

### Camada 1: Git + GitHub (versionado)

**Repo:** https://github.com/fourd-qa/pipefy-validator-demo (publico)

O `.gitignore` exclui:
- Tokens em plaintext (`config/environments.json`, `config/*.robot`)
- Dependencias regeneraveis (`node_modules/`, `__pycache__/`, `.pytest_cache/`)
- Outputs de runs (`results/`)
- Configs locais de editor

Como este e um demo publico, **nenhum token real** vive no repositorio. Cada usuario configura seus proprios via UI ou environments.json local.

### Camada 2: ZIP em cloud

ZIP completo da pasta INCLUINDO `config/environments.json` e os `.robot` se voce ja preencheu tokens locais. Sobe pra OneDrive ou Google Drive em pasta privada.

Versao light (sem node_modules, ~1.5MB):

```powershell
cd C:\Users\FourD\Documents\robothz
$stamp = Get-Date -Format 'yyyy-MM-dd'
$src = '.\pipefy-validator-demo'
$dst = ".\pipefy-validator-demo_LIGHT_$stamp"
robocopy $src $dst /E /XD node_modules __pycache__ .pytest_cache results /XF '*.pyc' | Out-Null
Compress-Archive -Path "$dst\*" -DestinationPath "$dst.zip" -Force
Remove-Item -Recurse -Force $dst
Write-Host "ZIP gerado: $dst.zip"
```

### Camada 3: HD externo ou pen drive

Defesa contra ransomware ou conta cloud bloqueada. Mesma pasta light, copiada pra midia fisica.

---

## 3. CHECKLIST DE RESTORE EM MAQUINA NOVA

### Pre-requisitos

- Docker Desktop
- Python 3.11
- Node.js LTS
- Git
- PowerShell 7+ (opcional)

### Passos

1. **Restaurar pasta:**
   ```powershell
   git clone https://github.com/fourd-qa/pipefy-validator-demo.git
   cd pipefy-validator-demo
   # Copiar config/environments.example.json -> config/environments.json e preencher tokens
   ```

2. **Instalar dependencias:**
   ```powershell
   python -m pip install -r requirements-dev.txt
   npm install
   ```

3. **Subir container:**
   ```powershell
   docker-compose up --build -d
   Start-Sleep -Seconds 10
   Start-Process http://localhost:8080
   ```

4. **Validar:**
   ```powershell
   .\run-all-tests.ps1
   ```

---

## 4. ARQUIVOS COM TOKEN EM PLAINTEXT (LOCAIS)

**Nunca commitam no git:**

| Arquivo | O que tem |
|---------|-----------|
| `config/environments.json` | Tokens Bearer dos ambientes locais |
| `config/*.robot` | Bearer copiado pelo backend pra rodar Robot |
| `config/active.robot` | Copia do preset ativo |
| `config/active_cross.robot` | Idem para cross |

Os `.robot` sao **regeneraveis** pela UI (modal Gerenciar Ambientes) a partir do `environments.json`. Em ultimo caso, basta restaurar o `environments.json` e usar a UI.

---

## 5. FREQUENCIA DE BACKUP

| Camada | Frequencia |
|--------|-----------|
| Git | A cada feature ou bug fix significativo |
| ZIP cloud | Semanal |
| HD externo | Mensal ou antes de viagem/formatacao |

---

## 6. CONTATO

- Mantenedor: Andre Zimermann
- Doc canonica do projeto: `HANDOFF.md`
- Repo: https://github.com/fourd-qa/pipefy-validator-demo
