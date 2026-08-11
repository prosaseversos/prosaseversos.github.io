#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador do site de escritos — lê `textos/<secao>/*.md` e escreve o site pronto em `_site/`.

Só biblioteca padrão do Python. Nada de `pip install`, nada de `npm`. O site é HTML
estático: qualquer hospedagem serve, e daqui a dez anos ainda gera.

POR QUE NÃO USAMOS HUGO/JEKYLL DE PRATELEIRA
    Markdown padrão COLA linhas seguidas num parágrafo só. Num poema isso é fatal:

        Eu vi o mar                     ->   <p>Eu vi o mar e ele não me viu</p>
        e ele não me viu

    O verso é a unidade da poesia. Aqui, seção com `"verso": true` preserva cada
    quebra de linha e cada recuo; seção com `"verso": false` age como prosa normal.

A LIÇÃO DO FLAMMA (custou caro, não repetir)
    O sitemap do Flamma Cordis listava 21 URLs para um site de ~2.270 páginas.
    O Google acreditou: 22 visitas em duas semanas. Aqui, TODO texto publicado entra
    no sitemap, e o gerador IMPRIME a contagem no fim — se o número não bate com o
    que você escreveu, o erro aparece na hora, não seis meses depois.
"""

import html
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

import marca

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "_site"
TEXTOS = RAIZ / "conteudo"
TEMA = RAIZ / "tema"

# ── Variações de aparência ───────────────────────────────────────────────────
# O site pode ser gerado com caras diferentes para comparar antes de decidir.
# `python3 gerar.py --previa` monta as três em `_site/previa/<letra>/`.
#
#   modo da home:
#     lista   só os títulos, em ordem — o índice de um livro
#     capa    o texto mais recente inteiro na primeira tela, e a lista abaixo
#     indice  tudo à mostra, agrupado por seção, com as primeiras linhas
# As três atuais nasceram de pesquisa nos cinco maiores sites de poesia do mundo
# (Poetry Foundation, Poets.org, AllPoetry, Paris Review, HelloPoetry) e nas
# tendências de 2026 — não de gosto. O achado que derrubou as três primeiras:
# TODOS eles usam branco e preto, com cor em um lugar só. As paletas de creme,
# verde e tijolo que eu vinha propondo não existem no segmento.
VARIACOES = {
    "a": {"nome": "Galeria", "css": "visual-galeria.css", "home": "capa",
          "de": "Poetry Foundation + Paris Review"},
    "b": {"nome": "Diário",  "css": "visual-diario.css",  "home": "capa",
          "de": "Poets.org — o Poem-a-Day"},
    "c": {"nome": "Noturno", "css": "visual-noturno.css", "home": "lista",
          "de": "as tendências de 2026: escuro por padrão"},
}
ESTILO = "estilo.css"     # trocados quando se gera uma prévia
HOME = "capa"
NOINDEX = False


# ── Configuração ─────────────────────────────────────────────────────────────
def ler_config():
    cfg = json.loads((RAIZ / "site.json").read_text(encoding="utf-8"))
    cfg["url"] = cfg["url"].rstrip("/")
    return cfg


# ── Leitura dos textos ───────────────────────────────────────────────────────
RE_DATA_NOME = re.compile(r"^(\d{4}-\d{2}-\d{2})[-_ ]+(.*)$")


def slugificar(s):
    """Título -> pedaço de URL. Sem acento, sem espaço, minúsculo.

    ⚠️ O slug entra na URL, e URL publicada não se troca sem quebrar link de quem
    já compartilhou. Se mudar o título de um texto já no ar, fixe o slug antigo no
    frontmatter (`slug: o-de-antes`) em vez de deixar o gerador criar um novo.
    """
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "sem-titulo"


def ler_frontmatter(bruto):
    """Frontmatter simples entre `---`, uma `chave: valor` por linha.

    Deliberadamente não é YAML completo: YAML de verdade exigiria dependência
    externa e traz armadilhas (o famoso `nao` virando booleano). Aqui é texto.
    """
    meta, corpo = {}, bruto
    if bruto.startswith("---"):
        partes = bruto.split("---", 2)
        if len(partes) >= 3:
            for linha in partes[1].strip().splitlines():
                if ":" in linha:
                    k, v = linha.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            corpo = partes[2]
    return meta, corpo.strip("\n")


def carregar_textos(cfg, avisos):
    textos = []
    for secao in cfg["secoes"]:
        pasta = TEXTOS / secao["pasta"]
        if not pasta.is_dir():
            continue
        # ⚠️ Ignorar o que começa com ponto. O HD é ExFAT, e nele o macOS grava um
        # arquivo-sombra `._nome.md` ao lado de cada arquivo — binário, e que casa
        # com `*.md`. Sem este filtro o gerador morre em UnicodeDecodeError.
        for arq in sorted(pasta.glob("*.md")):
            if arq.name.startswith("."):
                continue
            try:
                bruto = arq.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                avisos.append(f"⚠️ não é UTF-8, ignorado: {secao['pasta']}/{arq.name}")
                continue
            meta, corpo = ler_frontmatter(bruto)

            if meta.get("publicado", "sim").lower() in ("nao", "não", "no", "false", "0"):
                avisos.append(f"rascunho (fora do site): {secao['pasta']}/{arq.name}")
                continue
            if not corpo.strip():
                avisos.append(f"VAZIO, ignorado: {secao['pasta']}/{arq.name}")
                continue

            nome = arq.stem
            m = RE_DATA_NOME.match(nome)
            titulo = meta.get("titulo") or (m.group(2) if m else nome).replace("-", " ").strip()

            # Data: frontmatter > prefixo do nome do arquivo > data de modificação.
            # Nunca "hoje": data que muda a cada build suja o `lastmod` do sitemap e
            # ensina o Google que o site inteiro se reescreve todo dia.
            crua = meta.get("data") or (m.group(1) if m else "")
            try:
                dt = date.fromisoformat(crua[:10])
            except ValueError:
                dt = date.fromtimestamp(arq.stat().st_mtime)
                avisos.append(f"sem data, usei a do arquivo ({dt}): {secao['pasta']}/{arq.name}")

            textos.append({
                "titulo": titulo,
                "slug": meta.get("slug") or slugificar(titulo),
                "data": dt,
                "secao": secao,
                "corpo": corpo,
                "resumo": meta.get("resumo", ""),
                "arquivo": arq,
            })

    # Mais novo primeiro. Empate resolvido pelo título, para a ordem não dançar
    # entre um build e outro (build instável = sitemap instável).
    textos.sort(key=lambda t: (t["data"], t["titulo"]), reverse=True)

    vistos = {}
    for t in textos:
        chave = (t["secao"]["pasta"], t["slug"])
        if chave in vistos:
            avisos.append(
                f"⚠️ URL DUPLICADA /{chave[0]}/{chave[1]}/ — "
                f"'{t['arquivo'].name}' sobrescreve '{vistos[chave]}'. Ponha um `slug:` diferente.")
        vistos[chave] = t["arquivo"].name
    return textos


# ── Markdown mínimo ──────────────────────────────────────────────────────────
RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_FORTE = re.compile(r"\*\*(.+?)\*\*")
RE_ENFASE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def inline(txt):
    """Escapa o HTML e devolve só o mínimo de formatação que escrita precisa."""
    txt = html.escape(txt, quote=False)
    txt = RE_LINK.sub(r'<a href="\2">\1</a>', txt)
    txt = RE_FORTE.sub(r"<strong>\1</strong>", txt)
    txt = RE_ENFASE.sub(r"<em>\1</em>", txt)
    return txt


def recuo(linha):
    """Recuo do verso é forma, não enfeite — o HTML come espaço no começo da linha,
    então viram `&nbsp;` para o poema ficar na página como está no arquivo."""
    corpo = linha.lstrip(" ")
    return "&nbsp;" * (len(linha) - len(corpo)) + inline(corpo)


RE_ROTULO = re.compile(r"^\[(.{1,40})\]$")


def render(corpo, verso):
    """Blocos separados por linha em branco. Em verso, cada linha é um verso."""
    out = []
    for bloco in re.split(r"\n\s*\n", corpo.strip()):
        linhas = [l.rstrip() for l in bloco.splitlines() if l.strip()]
        if not linhas:
            continue

        # Rótulo de estrofe — a convenção de quem escreve letra de música:
        #
        #     [Refrão]
        #     Vem comigo, que o tempo passa
        #
        # O refrão é reconhecido pelo nome e ganha destaque próprio no visual;
        # qualquer outro rótulo ([Ponte], [Verso 2], [Final]) vira legenda discreta.
        rotulo = None
        m = RE_ROTULO.match(linhas[0].strip())
        if m and len(linhas) > 1:
            rotulo, linhas = m.group(1).strip(), linhas[1:]

        if rotulo is not None:
            eh_refrao = "refr" in slugificar(rotulo)
            classe = "estrofe refrao" if eh_refrao else "estrofe"
            out.append(f'<p class="{classe}"><span class="rotulo">{inline(rotulo)}</span>'
                       + "<br>\n".join(recuo(l) for l in linhas) + "</p>")
        elif all(re.fullmatch(r"[-*_]{3,}", l.strip()) for l in linhas):
            out.append("<hr>")
        elif linhas[0].startswith("#"):
            n = min(len(linhas[0]) - len(linhas[0].lstrip("#")), 4) + 1
            out.append(f"<h{n}>{inline(linhas[0].lstrip('# ').strip())}</h{n}>")
            resto = "\n".join(linhas[1:])
            if resto.strip():
                out.append(render(resto, verso))
        elif linhas[0].startswith(">"):
            dentro = [l.lstrip("> ").rstrip() for l in linhas]
            sep = "<br>\n" if verso else " "
            out.append("<blockquote><p>" + sep.join(inline(l) for l in dentro) + "</p></blockquote>")
        elif verso:
            out.append('<p class="estrofe">' + "<br>\n".join(recuo(l) for l in linhas) + "</p>")
        else:
            out.append("<p>" + " ".join(inline(l) for l in linhas) + "</p>")
    return "\n".join(out)


def texto_puro(corpo, limite=155):
    """Para a meta description e o resumo do índice: só as palavras."""
    t = re.sub(r"[#>*_`]", "", corpo)
    t = RE_LINK.sub(r"\1", t)
    t = " ".join(t.split())
    if len(t) <= limite:
        return t
    return t[:limite].rsplit(" ", 1)[0] + "…"


# ── HTML ─────────────────────────────────────────────────────────────────────
MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def por_extenso(d):
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def pagina(cfg, *, titulo, descricao, caminho, conteudo, jsonld=None, capa=False):
    """Molde de toda página. Tudo que o Google e as redes leem mora aqui.

    `caminho` é o endereço a partir da raiz ("" = home, "poesia/o-mar/"). Dele saem
    a URL canônica e a profundidade do link para o CSS.
    """
    url = f"{cfg['url']}/{caminho}"
    prof = "../" * caminho.count("/") or "./"
    titulo_aba = titulo if capa else f"{titulo} — {cfg['nome']}"
    e = lambda s: html.escape(str(s), quote=True)

    cabeca = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{e(titulo_aba)}</title>",
        f'<meta name="description" content="{e(descricao)}">',
        f'<meta name="author" content="{e(cfg["autor"])}">',
        # Canônica: diz ao Google qual é o endereço oficial desta página. Sem ela,
        # o mesmo texto acessível por dois caminhos vira conteúdo duplicado.
        f'<link rel="canonical" href="{e(url)}">',
        f'<link rel="alternate" type="application/rss+xml" title="{e(cfg["nome"])}" href="{e(cfg["url"])}/feed.xml">',
        f'<link rel="stylesheet" href="{prof}{ESTILO}">',
        # SVG primeiro: é o que os navegadores atuais preferem, e é o único que
        # troca de cor sozinho quando a aba está no tema escuro. O PNG fica de
        # reserva para quem não lê SVG, e o apple-touch-icon é o da tela do iPhone.
        f'<link rel="icon" type="image/svg+xml" href="{prof}favicon.svg">',
        f'<link rel="icon" type="image/png" sizes="32x32" href="{prof}favicon.png">',
        f'<link rel="apple-touch-icon" href="{prof}apple-touch-icon.png">',
        f'<meta property="og:type" content="{"website" if capa else "article"}">',
        f'<meta property="og:title" content="{e(titulo_aba)}">',
        f'<meta property="og:description" content="{e(descricao)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:site_name" content="{e(cfg["nome"])}">',
        f'<meta property="og:locale" content="{e(cfg["idioma"].replace("-", "_"))}">',
        '<meta name="twitter:card" content="summary">',
        '<meta name="theme-color" content="#f7f5f0" media="(prefers-color-scheme: light)">',
        '<meta name="theme-color" content="#14161a" media="(prefers-color-scheme: dark)">',
    ]
    # Prévia não entra na busca: são três cópias do mesmo acervo, e conteúdo
    # duplicado é exatamente o que a tag canônica existe para evitar.
    if NOINDEX:
        cabeca.append('<meta name="robots" content="noindex, nofollow">')
    if jsonld:
        cabeca.append('<script type="application/ld+json">'
                      + json.dumps(jsonld, ensure_ascii=False) + "</script>")

    menu = " ".join(
        f'<a href="{prof}{s["pasta"]}/">{e(s["titulo"])}</a>' for s in cfg["secoes"])

    return f"""<!doctype html>
<html lang="{e(cfg['idioma'])}">
<head>
{chr(10).join(cabeca)}
</head>
<body>
<a class="pular" href="#conteudo">Ir para o conteúdo</a>
<header class="topo">
  <a class="marca" href="{prof}">{marca.svg_inline()}<span>{e(cfg['nome'])}</span></a>
  <nav>{menu}</nav>
</header>
<main id="conteudo">
{conteudo}
</main>
<footer class="rodape">
  <p>© {date.today().year} {e(cfg['autor'])}. Todos os textos são de autoria própria.</p>
  <p><a href="{prof}feed.xml">Assinar por RSS</a></p>
</footer>
</body>
</html>
"""


def cartao(t, prefixo=""):
    """Item de índice. O resumo aparece para o leitor E é o que o Google mostra."""
    e = lambda s: html.escape(str(s), quote=True)
    resumo = t["resumo"] or texto_puro(t["corpo"], 120)
    return (f'<li class="cartao">'
            f'<a href="{prefixo}{t["secao"]["pasta"]}/{t["slug"]}/">{e(t["titulo"])}</a>'
            f'<time datetime="{t["data"].isoformat()}">{por_extenso(t["data"])}</time>'
            f'<p>{e(resumo)}</p></li>')


# ── Escrita ──────────────────────────────────────────────────────────────────
def escrever(caminho, conteudo):
    destino = SAIDA / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")


def gerar():
    cfg = ler_config()
    avisos = []
    textos = carregar_textos(cfg, avisos)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True)

    # `urls` é a lista que vira o sitemap. Toda página gerada se registra aqui na
    # hora em que é escrita — é o que impede o site de crescer e o sitemap não.
    urls = []

    # Home — três modos, para comparar antes de decidir (ver VARIACOES)
    e = lambda s: html.escape(str(s), quote=True)
    corpo_home = (f'<h1 class="capa">{e(cfg["nome"])}</h1>'
                  f'<p class="sub">{e(cfg["subtitulo"])}</p>')

    if not textos:
        corpo_home += '<p class="vazio">Ainda não há textos publicados.</p>'

    elif HOME == "capa":
        # O texto mais recente inteiro na primeira tela. A home É a leitura —
        # quem chega já está lendo, em vez de escolher numa lista.
        t = textos[0]
        s = t["secao"]
        blocos = re.split(r"\n\s*\n", t["corpo"].strip())

        # Poema cabe inteiro na home; crônica de trinta parágrafos, não — ela
        # empurraria o resto do site para fora da tela e a home viraria o texto.
        # Verso vai inteiro até 8 estrofes; prosa mostra a abertura e convida.
        limite = 8 if s["verso"] else 2
        cortado = len(blocos) > limite
        trecho = "\n\n".join(blocos[:limite]) if cortado else t["corpo"]

        corpo_home += (
            f'<article class="destaque {"verso" if s["verso"] else "prosa"}">'
            f'<span class="etiqueta">{e(s["titulo"])}</span>'
            f'<h2 class="tituloDestaque"><a href="{s["pasta"]}/{t["slug"]}/">{e(t["titulo"])}</a></h2>'
            f'<time datetime="{t["data"].isoformat()}">{por_extenso(t["data"])}</time>'
            f'{render(trecho, s["verso"])}'
            + (f'<p class="continuar"><a href="{s["pasta"]}/{t["slug"]}/">'
               f'continuar lendo</a></p>' if cortado else "")
            + '</article>')
        if len(textos) > 1:
            corpo_home += ('<h2>Antes disso</h2><ul class="lista">'
                           + "\n".join(cartao(x) for x in textos[1:13]) + "</ul>")

    elif HOME == "indice":
        # Tudo à mostra, por seção. Nada escondido atrás de clique.
        for s in cfg["secoes"]:
            dela = [x for x in textos if x["secao"]["pasta"] == s["pasta"]]
            if not dela:
                continue
            corpo_home += (f'<section class="bloco"><h2><a href="{s["pasta"]}/">'
                           f'{e(s["titulo"])}</a> <span class="qtd">{len(dela)}</span></h2>'
                           '<ul class="lista">'
                           + "\n".join(cartao(x) for x in dela) + "</ul></section>")

    else:  # lista — o índice de um livro: títulos, datas, nada mais
        corpo_home += ('<ul class="lista nua">' + "\n".join(
            f'<li><a href="{x["secao"]["pasta"]}/{x["slug"]}/">{e(x["titulo"])}</a>'
            f'<span class="meta">{e(x["secao"]["titulo"].lower())} · '
            f'{por_extenso(x["data"])}</span></li>' for x in textos) + "</ul>")
    escrever("index.html", pagina(
        cfg, titulo=f"{cfg['nome']} — {cfg['subtitulo']}", descricao=cfg["descricao"],
        caminho="", conteudo=corpo_home, capa=True,
        jsonld={"@context": "https://schema.org", "@type": "WebSite",
                "name": cfg["nome"], "url": cfg["url"] + "/",
                "description": cfg["descricao"],
                "author": {"@type": "Person", "name": cfg["autor"]}}))
    urls.append(("", None, "1.0"))

    # Índice de cada seção
    for s in cfg["secoes"]:
        dela = [t for t in textos if t["secao"]["pasta"] == s["pasta"]]
        lista = ("\n".join(cartao(t, "../") for t in dela) if dela else "")
        corpo = f'<h1>{html.escape(s["titulo"])}</h1>'
        corpo += (f'<ul class="lista">{lista}</ul>' if dela
                  else '<p class="vazio">Nada publicado nesta seção ainda.</p>')
        escrever(f"{s['pasta']}/index.html", pagina(
            cfg, titulo=s["titulo"],
            descricao=f"{s['descricao']} {len(dela)} texto(s) de {cfg['autor']}.".strip(),
            caminho=f"{s['pasta']}/", conteudo=corpo,
            jsonld={"@context": "https://schema.org", "@type": "CollectionPage",
                    "name": s["titulo"], "url": f"{cfg['url']}/{s['pasta']}/"}))
        urls.append((f"{s['pasta']}/", None, "0.7"))

    # Cada texto
    for t in textos:
        s = t["secao"]
        caminho = f"{s['pasta']}/{t['slug']}/"
        desc = t["resumo"] or texto_puro(t["corpo"])

        # Anterior/próximo dentro da mesma seção. Serve para ler em sequência —
        # e de quebra é o que faz o buscador alcançar texto antigo: página sem
        # link chegando nela é página que o Google visita uma vez e esquece.
        dela = [x for x in textos if x["secao"]["pasta"] == s["pasta"]]
        i = dela.index(t)
        vizinhos = []
        if i + 1 < len(dela):  # a lista é do mais novo ao mais antigo
            v = dela[i + 1]
            vizinhos.append(f'<a class="ant" href="../{v["slug"]}/">'
                            f'← {html.escape(v["titulo"])}</a>')
        if i > 0:
            v = dela[i - 1]
            vizinhos.append(f'<a class="prox" href="../{v["slug"]}/">'
                            f'{html.escape(v["titulo"])} →</a>')

        corpo = (f'<article class="{"verso" if s["verso"] else "prosa"}">'
                 f'<h1>{html.escape(t["titulo"])}</h1>'
                 f'<time datetime="{t["data"].isoformat()}">{por_extenso(t["data"])}</time>'
                 f'{render(t["corpo"], s["verso"])}'
                 f'</article>'
                 f'<nav class="vizinhos">{"".join(vizinhos)}</nav>'
                 f'<p class="volta"><a href="../">Todos os textos de '
                 f'{html.escape(s["titulo"].lower())}</a></p>')
        escrever(caminho + "index.html", pagina(
            cfg, titulo=t["titulo"], descricao=desc, caminho=caminho, conteudo=corpo,
            # `Poem` é tipo de verdade no schema.org. Dizer ao buscador que aquilo é
            # um poema, e não uma notícia, muda como e para quem ele mostra.
            jsonld={"@context": "https://schema.org",
                    "@type": "Poem" if s["verso"] else "Article",
                    "headline": t["titulo"], "name": t["titulo"],
                    "datePublished": t["data"].isoformat(),
                    "inLanguage": cfg["idioma"], "description": desc,
                    "url": f"{cfg['url']}/{caminho}",
                    "author": {"@type": "Person", "name": cfg["autor"]},
                    "publisher": {"@type": "Person", "name": cfg["autor"]}}))
        urls.append((caminho, t["data"].isoformat(), "0.8"))

    # 404 — o GitHub Pages usa este arquivo sozinho. Fora do sitemap, de propósito.
    escrever("404.html", pagina(
        cfg, titulo="Página não encontrada", descricao="Este endereço não existe.",
        caminho="404.html",
        conteudo='<h1>Não encontrei esta página</h1>'
                 '<p class="vazio">O endereço pode ter mudado. '
                 '<a href="./">Voltar ao começo</a>.</p>'))

    # Painel de escrita, quando existe. Roda inteiro no navegador e conversa com a
    # API do GitHub — o GitHub Pages não executa código, então não há outro jeito
    # de ter um painel "dentro do site". Fora do sitemap e barrado no robots: é
    # ferramenta de trabalho, não conteúdo. Sem token não faz nada.
    painel = TEMA / "admin.html"
    if painel.exists():
        # Carimba a hora do build no painel. O GitHub Pages manda o navegador
        # guardar a página por 10 minutos (`cache-control: max-age=600`), e sem
        # esta marca não há como saber, olhando a tela, se o painel é o de agora
        # ou um de antes — o que já custou uma confusão inteira.
        escrever("admin/index.html",
                 painel.read_text(encoding="utf-8")
                       .replace("{{VERSAO}}", datetime.now().strftime("%d/%m %H:%M")))

    escrever("sitemap.xml", monta_sitemap(cfg, urls))
    escrever("robots.txt",
             f"User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /previa/\n\n"
             f"Sitemap: {cfg['url']}/sitemap.xml\n")
    escrever("feed.xml", monta_feed(cfg, textos))

    css = TEMA / ESTILO
    if css.exists():
        shutil.copy(css, SAIDA / ESTILO)

    # A fonte é servida daqui, não de CDN: o site não pode depender de servidor
    # de terceiro para ter cara — e sem a fonte, o desenho todo muda.
    fontes = TEMA / "fontes"
    if fontes.is_dir():
        (SAIDA / "fontes").mkdir(parents=True, exist_ok=True)
        for f in fontes.glob("*.woff2"):
            shutil.copy(f, SAIDA / "fontes" / f.name)

    # Ícones. O `favicon.ico` existe porque o navegador o pede na raiz por conta
    # própria, sem olhar as tags do <head> — e 404 repetido polui log e é feio.
    png32 = marca.png(32)
    (SAIDA / "favicon.svg").write_text(marca.svg_favicon(), encoding="utf-8")
    (SAIDA / "favicon.png").write_bytes(png32)
    (SAIDA / "favicon.ico").write_bytes(marca.ico(png32))
    (SAIDA / "apple-touch-icon.png").write_bytes(
        marca.png(180, fundo=marca.PAPEL))   # iOS pinta de preto o que for transparente
    # `.nojekyll`: sem ele o GitHub Pages passa tudo pelo Jekyll e engole arquivos
    # e pastas que começam com `_`.
    (SAIDA / ".nojekyll").write_text("")

    return cfg, textos, urls, avisos


def monta_sitemap(cfg, urls):
    e = lambda s: html.escape(str(s), quote=True)
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for caminho, lastmod, prio in urls:
        lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        linhas.append(f"<url><loc>{e(cfg['url'])}/{e(caminho)}</loc>{lm}"
                      f"<priority>{prio}</priority></url>")
    linhas.append("</urlset>")
    return "\n".join(linhas) + "\n"


def monta_feed(cfg, textos):
    e = lambda s: html.escape(str(s), quote=False)
    itens = []
    for t in textos[:30]:
        link = f"{cfg['url']}/{t['secao']['pasta']}/{t['slug']}/"
        pub = datetime(t["data"].year, t["data"].month, t["data"].day, 12, 0)
        itens.append(
            f"<item><title>{e(t['titulo'])}</title><link>{e(link)}</link>"
            f"<guid isPermaLink=\"true\">{e(link)}</guid>"
            f"<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{e(t['resumo'] or texto_puro(t['corpo'], 300))}</description></item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>'
            f"<title>{e(cfg['nome'])}</title><link>{e(cfg['url'])}/</link>"
            f"<description>{e(cfg['descricao'])}</description>"
            f"<language>{e(cfg['idioma'])}</language>"
            + "".join(itens) + "</channel></rss>\n")


# ── Relatório ────────────────────────────────────────────────────────────────
def gerar_previas():
    """Monta as três variações em `_site/previa/<letra>/` para comparar de verdade,
    com os textos reais dentro. Escolher aparência olhando descrição não funciona."""
    global SAIDA, ESTILO, HOME, NOINDEX
    original = SAIDA
    cfg = ler_config()

    # O site de verdade primeiro: `gerar()` limpa a pasta de saída, e se as
    # prévias viessem antes seriam apagadas por ele.
    gerar()

    NOINDEX = True
    print(f"\n  Prévias — {cfg['nome']}\n")
    for letra, v in VARIACOES.items():
        SAIDA, ESTILO, HOME = original / "previa" / letra, v["css"], v["home"]
        _, textos, urls, _ = gerar()
        print(f"    {letra})  {v['nome']:<9} {len(textos)} textos · home '{v['home']}'"
              f"  →  /previa/{letra}/")

    # Uma página para escolher, com link para as três.
    SAIDA, NOINDEX = original, False
    cores = TEMA / "cores.html"
    if cores.exists():
        (SAIDA / "previa").mkdir(parents=True, exist_ok=True)
        (SAIDA / "previa" / "cores.html").write_text(
            cores.read_text(encoding="utf-8"), encoding="utf-8")
    cartoes = "".join(
        f'<li><a href="{L}/"><b>{v["nome"]}</b>'
        f'<span>inspirado em {html.escape(v.get("de", ""))}</span></a></li>'
        for L, v in VARIACOES.items())
    (SAIDA / "previa").mkdir(parents=True, exist_ok=True)
    (SAIDA / "previa" / "index.html").write_text(f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Três aparências — {html.escape(cfg['nome'])}</title>
<style>
 :root{{--bg:#ffffff;--tx:#0a0a0a;--su:#6b6b6b;--ln:#e5e5e5;--ac:#0b57d0}}
 @media(prefers-color-scheme:dark){{:root{{--bg:#0d0d0d;--tx:#f2f2f2;--su:#9a9a9a;--ln:#242424;--ac:#8ab4f8}}}}
 *{{box-sizing:border-box}}
 body{{font:16px/1.65 -apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
   max-width:40rem;margin:0 auto;padding:4rem 1.4rem 6rem;background:var(--bg);color:var(--tx)}}
 h1{{font-weight:800;font-size:1.9rem;letter-spacing:-.03em;margin:0 0 .4rem}}
 .sub{{color:var(--su);margin:0 0 2.6rem}}
 h2{{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
   color:var(--su);margin:3rem 0 1rem}}
 ul.esc{{list-style:none;padding:0;margin:0}} ul.esc li{{margin-bottom:.8rem}}
 ul.esc a{{display:block;padding:1.15rem 1.2rem;border:1px solid var(--ln);border-radius:12px;
   text-decoration:none;color:inherit}}
 ul.esc a:hover{{border-color:var(--ac)}}
 ul.esc b{{display:block;font-size:1.1rem;letter-spacing:-.01em}}
 ul.esc span{{color:var(--su);font-size:.88rem}}
 table{{width:100%;border-collapse:collapse;font-size:.88rem}}
 td,th{{text-align:left;padding:.5rem .3rem;border-bottom:1px solid var(--ln);vertical-align:top}}
 th{{font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--su);font-weight:600}}
 .achado{{border-left:3px solid var(--ac);padding:.2rem 0 .2rem 1rem;margin:1.4rem 0;
   color:var(--su);font-size:.94rem;line-height:1.6}}
 .achado b{{color:var(--tx)}}
 .nota{{font-size:.84rem;color:var(--su);line-height:1.6;margin-top:2.5rem;
   border-top:1px solid var(--ln);padding-top:1.4rem}}
</style></head><body>
<h1>Três aparências</h1>
<p class="sub">Feitas a partir dos maiores sites de poesia do mundo, não de gosto meu.
   Abra as três — inclusive no celular — e diga qual fica.</p>

<ul class="esc">{cartoes}</ul>

<h2>o que eu pesquisei</h2>
<table>
  <tr><th>site</th><th>tamanho</th><th>o que faz</th></tr>
  <tr><td>Poetry Foundation</td><td>7M visitas/mês</td><td>branco, sans-serif pesada, cards</td></tr>
  <tr><td>Poets.org</td><td>Academy of American Poets</td><td>poema inteiro na primeira tela</td></tr>
  <tr><td>AllPoetry</td><td>1º da categoria Literatura</td><td>comunidade de autores</td></tr>
  <tr><td>Paris Review</td><td>referência editorial</td><td>alto contraste, muito ar</td></tr>
  <tr><td>HelloPoetry</td><td>top do segmento</td><td>publicação simples</td></tr>
</table>

<div class="achado">
  <b>O que derrubou as três propostas anteriores:</b> todos eles usam
  <b>branco e preto</b>, e a cor aparece em um lugar só — o link. As paletas de
  creme, verde-mato e vermelho-tijolo que eu vinha propondo não existem no
  segmento. Por isso pareciam erradas.
</div>

<div class="achado">
  <b>E o que 2026 aponta:</b> a tipografia toma o lugar da imagem (título grande,
  serifada de alto contraste), espaço em branco generoso, e escuro por padrão —
  em tela OLED o preto puro não gasta bateria. É de onde vem a terceira proposta.
</div>

<p class="nota">Se ainda assim nenhuma servir, me diga o que cada uma errou —
  ou aponte um site que você gosta, de qualquer assunto. Com uma referência de
  verdade eu paro de tentar adivinhar.</p>
</body></html>""", encoding="utf-8")
    print(f"\n    escolher em:  /previa/\n")


def main():
    if "--previa" in sys.argv:
        gerar_previas()
        return 0

    cfg, textos, urls, avisos = gerar()

    print(f"\n  {cfg['nome']} — {cfg['url']}")
    print(f"  saída: {SAIDA}\n")
    for s in cfg["secoes"]:
        n = sum(1 for t in textos if t["secao"]["pasta"] == s["pasta"])
        print(f"    {s['titulo']:<16} {n:>4} texto(s)")
    print(f"    {'—' * 26}")
    print(f"    {'total':<16} {len(textos):>4} texto(s)")

    # A contagem do sitemap fica em pé de igualdade com a dos textos, de propósito:
    # é a conferência que faltou no Flamma. Páginas geradas e páginas declaradas ao
    # Google têm que fechar.
    print(f"\n    sitemap.xml: {len(urls)} URLs "
          f"(1 home + {len(cfg['secoes'])} seções + {len(textos)} textos)")
    esperado = 1 + len(cfg["secoes"]) + len(textos)
    if len(urls) != esperado:
        print(f"    ⚠️ ESPERAVA {esperado} — conferir o gerador.")

    if "SEU-USUARIO" in cfg["url"]:
        print("\n    ⚠️ A URL em site.json ainda é o exemplo. Trocar ANTES de publicar:")
        print("       canonical, sitemap e Open Graph estão todos apontando para o vazio.")

    if avisos:
        print(f"\n    {len(avisos)} aviso(s):")
        for a in avisos:
            print(f"      · {a}")

    print(f"\n  ver agora:  python3 -m http.server -d '{SAIDA}' 8000")
    print("              http://localhost:8000\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
