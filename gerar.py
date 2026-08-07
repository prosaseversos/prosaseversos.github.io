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

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "_site"
TEXTOS = RAIZ / "conteudo"
TEMA = RAIZ / "tema"


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
        f'<link rel="stylesheet" href="{prof}estilo.css">',
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
  <a class="marca" href="{prof}">{e(cfg['nome'])}</a>
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

    # Home
    destaques = "\n".join(cartao(t) for t in textos[:12])
    corpo_home = (f'<h1 class="capa">{html.escape(cfg["nome"])}</h1>'
                  f'<p class="sub">{html.escape(cfg["subtitulo"])}</p>')
    corpo_home += (f'<h2>Mais recentes</h2><ul class="lista">{destaques}</ul>'
                   if textos else
                   '<p class="vazio">Ainda não há textos publicados.</p>')
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

    escrever("sitemap.xml", monta_sitemap(cfg, urls))
    escrever("robots.txt",
             f"User-agent: *\nAllow: /\n\nSitemap: {cfg['url']}/sitemap.xml\n")
    escrever("feed.xml", monta_feed(cfg, textos))

    css = TEMA / "estilo.css"
    if css.exists():
        shutil.copy(css, SAIDA / "estilo.css")
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
def main():
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
