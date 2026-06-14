# Deploy na Square Cloud

## 1. Preparação

1. Compacte o conteúdo do projeto, mantendo `squarecloud.app` na raiz.
2. Envie o ZIP pelo painel ou CLI da Square Cloud.
3. Configure no painel as variáveis de `.env.example`.
4. Gere um `STUPIDEX_SECRET` longo e aleatório.
5. Defina ao menos uma chave de provedor global ou deixe cada usuário configurar sua chave na interface.

## 2. Comando de inicialização

O arquivo `squarecloud.app` usa:

```bash
bash scripts/start-square.sh
```

O script respeita a variável `PORT`, cria os diretórios persistentes, inicializa o banco e executa Gunicorn.

## 3. Domínio e CORS

Troque:

```env
FRONTEND_URL=https://SEU-SUBDOMINIO.squareweb.app
STUPIDEX_CORS=https://SEU-SUBDOMINIO.squareweb.app
```

Para domínio próprio, use a URL HTTPS final nos dois campos.

## 4. Shell

O shell está ligado por padrão no pacote:

```env
STUPIDEX_ENABLE_SHELL=1
STUPIDEX_SHELL_REQUIRE_APPROVAL=1
```

Mantenha a aprovação obrigatória. Não adicione `bash`, `sh`, `curl`, `wget`, `env`, `sudo` ou ferramentas de acesso remoto à allowlist.

## 5. Persistência

O banco, cofre de chaves e workspaces ficam em `STUPIDEX_DATA_DIR`. Faça backup de:

- `stupidex.db`
- `.keyvault`
- `workspaces/`

Perder `.keyvault` impede descriptografar chaves já salvas.

## 6. Health check

Use:

```text
/api/health
```

Resposta esperada: `status: ok` e `database: ok`.

## 7. Limitações atuais

- Banco SQLite e um worker Gunicorn são adequados ao MVP.
- Não há Redis/PostgreSQL nesta entrega porque exigiriam uma migração estrutural maior e serviços adicionais.
- O agente conversa e manipula workspaces, mas ainda não possui orquestração persistente de subagentes.
- GitHub OAuth completo não está incluído; clone público HTTPS está funcional.
