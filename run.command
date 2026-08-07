#!/bin/zsh
# Duplo clique aqui: gera o site e abre no navegador. Ctrl+C fecha.
cd "$(dirname "$0")" || exit 1

python3 gerar.py || { echo "\nO gerador falhou. Nada foi aberto."; read; exit 1; }

(sleep 1 && open "http://localhost:8000") &
python3 -m http.server -d _site 8000
