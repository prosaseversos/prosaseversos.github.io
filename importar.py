#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importador — joga Word, PDF, RTF, ODT ou texto na pasta `entrada/` e vira post.

COMO USAR
    1. Arraste o arquivo para a subpasta da seção:  entrada/poesia/meu-poema.docx
    2. Duplo clique em `importar.command` (ou `python3 importar.py`)
    3. O texto vira `conteudo/poesia/AAAA-MM-DD-meu-poema.md` e o original é
       **movido** (nunca apagado) para `entrada/_ja-importados/`

    A seção sai da pasta em que você soltou o arquivo. É de propósito: adivinhar
    se um texto é poema ou crônica dá errado justamente nos casos interessantes —
    o poema em prosa, a crônica em versos. Você já sabe; o programa não.

O PROBLEMA QUE ESTE IMPORTADOR RESOLVE
    No Word, um poema costuma ter os versos separados por Shift+Enter, que no
    arquivo é `<w:br/>` DENTRO do parágrafo. As bibliotecas comuns de leitura de
    .docx devolvem só o texto do parágrafo e descartam esses `<w:br/>` — o poema
    chega com a estrofe inteira numa linha só. Aqui o XML é lido à mão para que
    cada `<w:br/>` vire uma quebra de verso de verdade.

FERRAMENTAS
    .docx            leitura própria do XML (stdlib) — preserva Shift+Enter
    .doc .rtf .odt   `textutil`, nativo do macOS, nada a instalar
    .html .htm       `textutil`
    .pdf             `pdftotext -layout` se houver; senão `pypdf`
    .txt .md         direto

    Nada disso é exigido pelo site: `gerar.py` continua sem dependência nenhuma e
    o GitHub Actions só roda ele. Este importador é ferramenta de escrivaninha, e
    só precisa funcionar aqui no Mac.
"""

import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar import ler_config, slugificar, texto_puro   # noqa: E402

RAIZ = Path(__file__).resolve().parent
ENTRADA = RAIZ / "entrada"
GUARDADOS = ENTRADA / "_ja-importados"
CONTEUDO = RAIZ / "conteudo"

LIDOS_PELO_TEXTUTIL = {".doc", ".rtf", ".odt", ".html", ".htm", ".rtfd", ".wordml"}
TEXTO_PURO = {".txt", ".md", ".markdown", ".text"}


# ── Extração ─────────────────────────────────────────────────────────────────
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def de_docx(arq):
    """Lê `word/document.xml` na mão.

    Um .docx é um ZIP com XML dentro — dá para ler com a biblioteca padrão, sem
    instalar nada. E lendo à mão dá para tratar o que interessa:
      <w:p>   parágrafo  -> uma linha
      <w:br>  Shift+Enter -> quebra de verso (o motivo de tudo isto)
      <w:tab> tabulação   -> recuo, que em poesia é forma
    """
    with zipfile.ZipFile(arq) as z:
        nomes = z.namelist()
        if "word/document.xml" not in nomes:
            raise ValueError("não parece um .docx (falta word/document.xml)")
        xml = z.read("word/document.xml")

    linhas = []
    for paragrafo in ET.fromstring(xml).iter(W + "p"):
        partes = []
        for no in paragrafo.iter():
            if no.tag == W + "t":
                partes.append(no.text or "")
            elif no.tag in (W + "br", W + "cr"):
                partes.append("\n")
            elif no.tag == W + "tab":
                partes.append("    ")
        linhas.append("".join(partes))
    return "\n".join(linhas)


def de_textutil(arq):
    """`textutil` vem no macOS e lê .doc, .rtf, .odt e .html sem instalar nada."""
    r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(arq)],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise ValueError((r.stderr.decode("utf-8", "replace").strip() or "textutil falhou"))
    return r.stdout.decode("utf-8", "replace")


def de_pdf(arq):
    """`pdftotext -layout` primeiro: o `-layout` é o que preserva a disposição
    das linhas na página, e num poema a disposição é o texto. `pypdf` é reserva."""
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(arq), "-"],
                           capture_output=True, timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.decode("utf-8", "replace")

    try:
        import pypdf
    except ImportError:
        raise ValueError("PDF precisa de `pdftotext` ou da biblioteca `pypdf`. "
                         "Instale com: pip3 install pypdf")
    texto = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(str(arq)).pages)
    if not texto.strip():
        # PDF escaneado é imagem: não há texto para extrair, só pixels. Dizer isso
        # é melhor do que devolver um arquivo vazio e deixar a pessoa procurando.
        raise ValueError("PDF sem texto — provavelmente escaneado (imagem). "
                         "Precisaria de OCR; por ora, redigite ou envie em .docx")
    return texto


def extrair(arq):
    ext = arq.suffix.lower()
    if ext == ".docx":
        return de_docx(arq)
    if ext == ".pdf":
        return de_pdf(arq)
    if ext in LIDOS_PELO_TEXTUTIL:
        return de_textutil(arq)
    if ext in TEXTO_PURO:
        for cod in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return arq.read_text(encoding=cod)
            except UnicodeDecodeError:
                continue
        raise ValueError("não consegui descobrir a codificação do arquivo")
    if ext == ".pages":
        raise ValueError("o Pages guarda um pacote fechado. No Pages: "
                         "Arquivo → Exportar para → Word, e importe o .docx")
    raise ValueError(f"formato {ext or '(sem extensão)'} não suportado")


# ── Limpeza ──────────────────────────────────────────────────────────────────
def limpar(bruto):
    """Tira o lixo da conversão sem tocar na forma do texto.

    ⚠️ O que NÃO se faz aqui: juntar linhas, tirar recuo relativo, "arrumar"
    estrofe. Num poema tudo isso é decisão do autor, e um importador que
    reescreve o texto é pior que nenhum importador.
    """
    t = bruto.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\xa0", " ").replace("​", "")          # espaço fixo, largura zero
    t = t.replace("", "•").replace("\x0c", "\n\n")      # marcador do Word, fim de página
    t = "\n".join(l.rstrip() for l in t.split("\n"))

    # Número de página solto numa linha (típico de PDF). Só o número puro sai:
    # uma linha que seja "1997" pode ser um verso, mas nunca está sozinha entre
    # duas linhas vazias num poema — e mesmo assim o relatório avisa quantas saíram.
    linhas, removidas = [], 0
    for i, l in enumerate(t.split("\n")):
        if re.fullmatch(r"\s*-?\s*\d{1,4}\s*-?\s*", l) and l.strip():
            antes = linhas[-1].strip() if linhas else ""
            if not antes:
                removidas += 1
                continue
        linhas.append(l)
    t = "\n".join(linhas)

    # Margem do PDF: `-layout` empurra tudo para a direita com espaços iguais.
    # Tira-se só a margem COMUM, para o recuo relativo entre os versos sobreviver.
    uteis = [l for l in t.split("\n") if l.strip()]
    if uteis:
        margem = min(len(l) - len(l.lstrip(" ")) for l in uteis)
        if margem:
            t = "\n".join(l[margem:] if l.strip() else l for l in t.split("\n"))

    t = re.sub(r"\n{3,}", "\n\n", t)   # 3+ linhas vazias viram uma separação só
    return t.strip("\n"), removidas


MARCADOR = re.compile(r"^\s*(#{1,6}\s|>|[-*•]\s|\d+[.)]\s)")


def juntar_paragrafos(texto):
    """Só para PROSA: refaz o parágrafo que o PDF quebrou em linhas.

    Num PDF a linha acaba onde a margem mandou, não onde o autor quis. Deixar
    essas quebras no arquivo faz o site colar as linhas com espaço, e palavra
    cortada vira "prova d e que". Em prosa a unidade é o parágrafo, então o
    parágrafo é reconstruído aqui.

    ⚠️ Nunca chamada para verso — lá a quebra É o texto.

    Devolve (texto, junções_com_hífen): o hífen no fim da linha quase sempre é
    translineação ("pala-/vras") e o certo é colar sem ele, mas de vez em quando
    é palavra composta partida ("guarda-/chuva") e colar sem o hífen erra. Como
    não há como distinguir sem dicionário, cola-se sem o hífen — que é o caso
    comum — e o relatório diz quantas vezes isso aconteceu, para conferência.
    """
    blocos, hifens = [], 0
    for bloco in re.split(r"\n\s*\n", texto):
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        if not linhas:
            continue
        montado = []
        for linha in linhas:
            # Título, citação e item de lista vivem sozinhos na própria linha.
            if not montado or MARCADOR.match(linha) or MARCADOR.match(montado[-1]):
                montado.append(linha)
            elif montado[-1].endswith("-") and not montado[-1].endswith(("--", " -")):
                montado[-1] = montado[-1][:-1] + linha
                hifens += 1
            else:
                montado[-1] += " " + linha
        blocos.append("\n".join(montado))
    return "\n\n".join(blocos), hifens


def separar_titulo(texto, arq):
    """Primeira linha curta e sem ponto final é título. Na dúvida, nome do arquivo.

    Devolve (titulo, corpo, veio_do_arquivo) — o terceiro entra no relatório, para
    você saber onde o palpite foi dado e conferir.
    """
    linhas = texto.split("\n")
    for i, l in enumerate(linhas):
        if not l.strip():
            continue
        cabeca = l.strip().lstrip("#").strip()
        seguinte_vazia = i + 1 < len(linhas) and not linhas[i + 1].strip()
        if (len(cabeca) <= 70 and not cabeca.endswith((".", ",", ";", ":"))
                and seguinte_vazia):
            return cabeca, "\n".join(linhas[i + 1:]).strip("\n"), False
        break

    nome = re.sub(r"^\d{4}-\d{2}-\d{2}[-_ ]+", "", arq.stem)
    return re.sub(r"[-_]+", " ", nome).strip().capitalize(), texto, True


def conferir_forma(corpo, verso):
    """Não corrige nada — só avisa quando a pasta e o texto parecem discordar."""
    linhas = [l for l in corpo.split("\n") if l.strip()]
    if len(linhas) < 4:
        return None
    longas = sum(1 for l in linhas if len(l) > 75) / len(linhas)
    if verso and longas > 0.6:
        return "está em pasta de verso, mas as linhas são longas como prosa"
    if not verso and longas < 0.15:
        return "está em pasta de prosa, mas as linhas são curtas como verso"
    return None


# ── Importação ───────────────────────────────────────────────────────────────
def cabecalho(titulo, quando, resumo):
    esc = lambda s: str(s).replace("\n", " ").strip()
    return ("---\n"
            f"titulo: {esc(titulo)}\n"
            f"data: {quando.isoformat()}\n"
            f"resumo: {esc(resumo)}\n"
            "---\n\n")


def importar_um(arq, secao, avisos):
    bruto = extrair(arq)
    texto, numeros_fora = limpar(bruto)
    if not texto.strip():
        raise ValueError("o arquivo abriu, mas não havia texto dentro")

    hifens = 0
    if not secao["verso"]:
        texto, hifens = juntar_paragrafos(texto)

    titulo, corpo, do_nome = separar_titulo(texto, arq)
    if not corpo.strip():
        titulo, corpo = re.sub(r"[-_]+", " ", arq.stem).capitalize(), texto

    # Data de modificação do arquivo, não a de hoje. É um palpite — e por ser
    # palpite entra no relatório, para você corrigir no `data:` quando souber.
    quando = date.fromtimestamp(arq.stat().st_mtime)

    slug = slugificar(titulo)
    destino = CONTEUDO / secao["pasta"] / f"{quando.isoformat()}-{slug}.md"
    if destino.exists():
        raise ValueError(f"já existe {destino.name} — renomeie o arquivo de origem")

    destino.write_text(cabecalho(titulo, quando, texto_puro(corpo, 150)) + corpo + "\n",
                       encoding="utf-8")

    if do_nome:
        avisos.append(f"{destino.name}: título tirado do nome do arquivo")
    if numeros_fora:
        avisos.append(f"{destino.name}: {numeros_fora} linha(s) de número de página removida(s)")
    if hifens:
        avisos.append(f"{destino.name}: {hifens} palavra(s) coladas por hífen de fim de "
                      f"linha — confira se alguma era composta (guarda-chuva)")
    d = conferir_forma(corpo, secao["verso"])
    if d:
        avisos.append(f"{destino.name}: {d}")

    GUARDADOS.mkdir(parents=True, exist_ok=True)
    guardado = GUARDADOS / arq.name
    n = 1
    while guardado.exists():
        guardado = GUARDADOS / f"{arq.stem} ({n}){arq.suffix}"
        n += 1
    shutil.move(str(arq), str(guardado))   # move, nunca apaga

    return destino, len([l for l in corpo.split("\n") if l.strip()])


def main():
    cfg = ler_config()
    secoes = {s["pasta"]: s for s in cfg["secoes"]}

    for pasta in secoes:
        (ENTRADA / pasta).mkdir(parents=True, exist_ok=True)
    GUARDADOS.mkdir(parents=True, exist_ok=True)

    soltos = [a for a in ENTRADA.glob("*")
              if a.is_file() and not a.name.startswith(".")]

    tarefas = []
    for nome, secao in secoes.items():
        for arq in sorted((ENTRADA / nome).glob("*")):
            # `._nome` é o arquivo-sombra que o macOS cria em HD ExFAT.
            if arq.is_file() and not arq.name.startswith("."):
                tarefas.append((arq, secao))

    print(f"\n  Importador — {cfg['nome']}")
    print(f"  entrada: {ENTRADA}\n")

    if soltos:
        print(f"  ⚠️ {len(soltos)} arquivo(s) solto(s) na raiz de entrada/, sem seção:")
        for a in soltos:
            print(f"       {a.name}")
        print(f"     Mova para uma das subpastas: {', '.join(secoes)}\n")

    if not tarefas:
        if not soltos:
            print("  Nada para importar.")
            print(f"  Arraste .docx, .pdf, .rtf, .odt ou .txt para uma destas pastas:")
            for nome in secoes:
                print(f"       entrada/{nome}/")
        print()
        return 0

    feitos, falhas, avisos = [], [], []
    for arq, secao in tarefas:
        try:
            destino, n = importar_um(arq, secao, avisos)
            feitos.append((arq.name, destino, n))
            print(f"  ✓ {arq.name}")
            print(f"      → conteudo/{secao['pasta']}/{destino.name}  ({n} linhas)")
        except Exception as e:
            falhas.append((arq.name, str(e)))
            print(f"  ✗ {arq.name}")
            print(f"      {e}")

    print(f"\n  {len(feitos)} importado(s), {len(falhas)} com problema.")
    if avisos:
        print("\n  Confira:")
        for a in avisos:
            print(f"    · {a}")
    if feitos:
        print("\n  ⚠️ A DATA de cada texto veio da data do arquivo, que raramente é a")
        print("     data em que foi escrito. Ajuste o campo `data:` antes de publicar.")
        print("     Os originais estão em entrada/_ja-importados/ — nada foi apagado.")
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
