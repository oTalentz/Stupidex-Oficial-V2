@echo off
cd /d C:\Users\leona\Downloads\Stupidex-SquareCloud\Stupidex-SquareCloud
git add -A
git commit -m "fix: corrige bugs de consistencia da interface - state.rightTab, botoes, profile-name"
echo Setting remote...
git remote remove origin 2>nul
git remote add origin https://github.com/oTalentz/Stupidex-Oficial-V2.git
git push -u origin main --force
echo Done!
pause