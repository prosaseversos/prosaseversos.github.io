#!/bin/zsh
# Duplo clique aqui depois de largar os arquivos em entrada/<seção>/.
# Importa, regera o site e abre no navegador para conferir antes de publicar.
cd "$(dirname "$0")" || exit 1

python3 importar.py
codigo=$?

echo
python3 gerar.py || { echo "\nO gerador falhou."; read; exit 1; }

if [ $codigo -ne 0 ]; then
  echo "\n  Houve arquivo com problema — veja acima. O que deu certo já entrou."
fi

echo "\n  Abrindo para conferir. Ctrl+C fecha o servidor."
(sleep 1 && open "http://localhost:8000") &
python3 -m http.server -d _site 8000
