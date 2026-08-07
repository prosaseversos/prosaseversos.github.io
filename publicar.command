#!/bin/zsh
# Duplo clique aqui para mandar o que está no Mac para o site.
cd "$(dirname "$0")" || exit 1
export GH_NO_UPDATE_NOTIFIER=1

SITE="https://prosaseversos.github.io"
REPO="prosaseversos/prosaseversos.github.io"

echo ""
echo "  ── Publicar em $SITE ──"
echo ""

# Gera antes de mandar: se o gerador reclamar, é melhor descobrir aqui do que
# ver o site quebrado depois.
python3 gerar.py || { echo "\n  O gerador falhou. NADA foi publicado."; echo; read "?Enter para fechar "; exit 1; }

# ⚠️ Traz primeiro o que foi escrito pelo celular. Sem isto, o push é recusado
# (ou pior: o HD e o GitHub viram duas cópias que divergem).
echo "\n  Trazendo o que possa ter sido escrito pelo celular..."
if ! git pull --rebase --autostash origin main 2>&1 | tail -3; then
  echo "\n  ⚠️ Não consegui juntar o que está aqui com o que está no GitHub."
  echo "     Nada foi publicado. Me chame para resolver."
  echo; read "?Enter para fechar "; exit 1
fi

if [ -z "$(git status --porcelain)" ]; then
  echo "\n  Nada de novo para publicar — o site já está igual ao que está aqui."
  echo; read "?Enter para fechar "; exit 0
fi

echo "\n  O que vai para o site:"
git status --short | sed 's/^/     /'

echo ""
read "descricao?  Descreva em poucas palavras (Enter aceita \"novos textos\"): "
[ -z "$descricao" ] && descricao="novos textos"

git add -A
git commit -q -m "$descricao" || { echo "  Nada commitado."; read "?Enter "; exit 1; }

echo "\n  Enviando..."
if ! git push origin main 2>&1 | tail -3; then
  echo "\n  ⚠️ O envio falhou. Me chame."
  echo; read "?Enter para fechar "; exit 1
fi

# O push só entrega os arquivos. Quem monta e publica o site é o GitHub Actions,
# e é ele que pode falhar — então esperamos a resposta em vez de dar por certo.
echo "\n  Enviado. O GitHub está montando o site (leva cerca de 1 minuto)..."
if command -v gh >/dev/null 2>&1; then
  sleep 5
  id=$(gh run list --repo "$REPO" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null)
  if [ -n "$id" ] && gh run watch "$id" --repo "$REPO" --exit-status --interval 10 >/dev/null 2>&1; then
    echo "\n  ✓ NO AR: $SITE"
    open "$SITE"
  else
    echo "\n  ⚠️ A publicação falhou no GitHub. Os textos estão salvos, o site é que"
    echo "     não se atualizou. Veja o motivo em:"
    echo "     https://github.com/$REPO/actions"
  fi
else
  echo "\n  Confira em $SITE daqui a pouco."
fi

echo ""
read "?Enter para fechar "
