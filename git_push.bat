@echo off
cd /d C:\Users\leona\Downloads\Stupidex-SquareCloud\Stupidex-SquareCloud
git add -A
git commit -m "fix: corrige implementacao visual para corresponder ao design de referencia

Correcoes visuais:
- Adiciona classe pulse-slow ao icone do brand na sidebar
- Adiciona padding px-2 no brand (como no design)
- Adiciona usage mini-stat (Claude 3.5 Uso 45k/100k)
- Adiciona avatar com imagem UI Avatars
- Adiciona label 'Pro Plan' ao usuario
- Remove close-left button do desktop (so mobile)
- Composer agora usa bg-zinc-900/90 backdrop-blur-xl
- Botao Terminal substituido por Web Search
- Panel toggle agora hidden lg:block
- Right panel: Terminal como aba ativa por padrao
- Adiciona diff badge (1) na aba Alteracoes
- Adiciona timer (0m 14s) no terminal
- Adiciona terminal com output mock de npm test"
echo Setting remote...
git remote remove origin 2>nul
git remote add origin https://github.com/oTalentz/Stupidex-Oficial-V2.git
git push -u origin main --force
echo Done!
pause