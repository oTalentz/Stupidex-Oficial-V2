# Segurança

## Controles aplicados

- Cookies HttpOnly, SameSite Lax e Secure configurável.
- Hash de senha pelo Werkzeug.
- Tokens armazenados apenas como SHA-256.
- Chaves de API cifradas com Fernet.
- Verificação de propriedade em sessões e workspaces.
- Proteção contra path traversal e symlink escape.
- Extração ZIP validada.
- Shell sem interpretador, com `shell=False`.
- Allowlist de executáveis e bloqueio de operadores.
- Ambiente mínimo sem chaves, banco ou tokens.
- Timeout, encerramento de grupo de processos e limite de saída.
- Aprovação para instalação e comandos Git sensíveis.
- Headers de segurança e CSP.

## Limite importante

A Square Cloud não fornece, dentro desta aplicação, uma microVM por comando. Código executado no terminal continua compartilhando o container da aplicação, embora receba ambiente e diretório restritos. Não conceda acesso a usuários não confiáveis sem runners externos.
