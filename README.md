# Stupidex Square Cloud

Versão integrada da interface criada no AI Designer com backend funcional para chat multimodelo, sessões, workspaces, arquivos, clonagem Git e terminal restrito ao workspace.

## Funcionalidades entregues

- Interface minimalista de três painéis, responsiva.
- Cadastro, login e cookies HttpOnly.
- Conversas persistentes e streaming SSE.
- Integração LiteLLM com provedores e endpoints OpenAI-compatible.
- Configuração BYOK por usuário, cifrada em repouso.
- Workspaces separados por usuário.
- Upload, árvore, leitura e edição de arquivos.
- Clone HTTPS de GitHub/GitLab.
- Shell ligado, sem `shell=True`, com allowlist, timeout, ambiente mínimo, bloqueios e aprovação.
- Auditoria básica.
- Configuração pronta para Square Cloud.

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
bash scripts/start-square.sh
```

Abra `http://localhost:5000`.

## Aviso de segurança

O terminal é restrito logicamente ao workspace, mas roda no mesmo ambiente da aplicação. Ele não equivale a uma microVM isolada. Para uma operação pública de alto risco, mova as execuções para runners externos descartáveis.
