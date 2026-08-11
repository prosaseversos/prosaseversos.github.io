#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A marca do site — desenhada uma vez aqui, servida em todos os formatos.

A FORMA
    Seis barras em duas colunas. À esquerda, três do mesmo comprimento: prosa,
    que preenche a margem. À direita, três de comprimentos diferentes: verso,
    que termina onde o poeta decidiu.

        ▬▬▬▬▬   ▬▬▬▬▬
        ▬▬▬▬▬   ▬▬
        ▬▬▬▬▬   ▬▬▬▬

    Não é enfeite: é a mesma distinção que `gerar.py` faz entre uma seção com
    `verso: true` e uma com `verso: false`.

POR QUE RASTERIZAR EM PYTHON PURO
    O navegador pede `/favicon.ico` sozinho, sem olhar o `<link rel=icon>` — no
    Flamma isso deu 249 requisições em 404 no log do nginx. Então o site precisa
    de PNG e ICO de verdade, não só do SVG. Converter SVG→PNG exigiria cairo,
    rsvg ou Pillow; como a forma é feita só de retângulos de cantos arredondados,
    rasterizar à mão custa 100 linhas e mantém a promessa do projeto: nada de
    `pip install`, e o build roda igual no Mac e no Linux do GitHub Actions.
"""

import struct
import zlib

# Barras em coordenadas de 0 a 32: (x, y, largura, altura, raio).
# Coluna da prosa (x=3) toda com 11 de largura; coluna do verso (x=18) com 11, 6 e 9.
FORMA = [
    (3,  8.5,  11, 2.6, 1.3), (3,  14.7, 11, 2.6, 1.3), (3,  20.9, 11, 2.6, 1.3),
    (18, 8.5,  11, 2.6, 1.3), (18, 14.7, 6,  2.6, 1.3), (18, 20.9, 9,  2.6, 1.3),
]

# As mesmas duas cores do site (ver `estilo.css`): a prosa em azul, o verso em
# vermelho. No ícone da aba elas aparecem juntas — é o que o distingue de
# qualquer outro quadradinho na barra do navegador.
AZUL_CLARO = "#4a7fa8"      # prosa, sobre fundo claro
AZUL_ESCURO = "#9dc4e4"     # prosa, sobre fundo escuro
VERM_CLARO = "#c2706b"      # verso, sobre fundo claro
VERM_ESCURO = "#e8a9a4"     # verso, sobre fundo escuro
PAPEL = "#ffffff"


def _barras_svg(indent="  ", classes=False):
    """`classes=True` marca cada coluna, para o CSS poder pintar a prosa de uma
    cor e o verso de outra. Sem isso as seis barras saem todas iguais."""
    linhas = []
    for i, (x, y, w, h, r) in enumerate(FORMA):
        cls = ""
        if classes:
            cls = f' class="{"prosa-barra" if x < 16 else "verso-barra"}" fill="currentColor"'
        linhas.append(f'{indent}<rect{cls} x="{x:g}" y="{y:g}" '
                      f'width="{w:g}" height="{h:g}" rx="{r:g}"/>')
    return "\n".join(linhas)


def svg_inline(classe="simbolo"):
    """Para o topo da página. Inline e com `currentColor`: sem requisição extra,
    e a cor acompanha o tema claro/escuro sozinha."""
    return (f'<svg class="{classe}" viewBox="0 0 32 32" fill="currentColor" '
            f'aria-hidden="true" focusable="false">\n'
            f'{_barras_svg(classes=True)}\n</svg>')


def svg_favicon():
    """Ícone da aba, nas duas cores. O `@media` dentro do próprio SVG é respeitado
    pelo navegador no favicon — é assim que o ícone se ajusta sozinho quando a aba
    está no escuro."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">\n'
            f'  <style>\n'
            f'    .prosa-barra {{ fill: {AZUL_CLARO}; }}\n'
            f'    .verso-barra {{ fill: {VERM_CLARO}; }}\n'
            f'    @media (prefers-color-scheme: dark) {{\n'
            f'      .prosa-barra {{ fill: {AZUL_ESCURO}; }}\n'
            f'      .verso-barra {{ fill: {VERM_ESCURO}; }}\n'
            f'    }}\n'
            f'  </style>\n{_barras_svg(classes=True)}\n</svg>\n')


# ── Ornamentos ───────────────────────────────────────────────────────────────
# Desenhos pequenos, para o texto ter começo, meio e fim visíveis. Vêm da mesma
# gramática da marca — traço fino, canto arredondado, as duas cores — para
# parecerem da mesma casa e não adesivos colados por cima.

def filete_fim():
    """Fecha o texto. Dois traços e um losango: a marca de fim que os livros usam
    há séculos, aqui com as duas cores do site."""
    return ('<svg class="ornamento fim" viewBox="0 0 120 12" aria-hidden="true" '
            'focusable="false">'
            '<line class="tr" x1="4" y1="6" x2="46" y2="6"/>'
            '<path class="lo azul" d="M60 1.5 66.5 6 60 10.5 53.5 6Z"/>'
            '<line class="tr" x1="74" y1="6" x2="116" y2="6"/>'
            '</svg>')


def filete_estrofe():
    """Entre blocos longos. Três pontos que crescem — o mesmo gesto do símbolo:
    o que se adensa da esquerda para a direita."""
    return ('<svg class="ornamento entre" viewBox="0 0 44 8" aria-hidden="true" '
            'focusable="false">'
            '<circle class="p1" cx="8" cy="4" r="1.6"/>'
            '<circle class="p2" cx="22" cy="4" r="2.2"/>'
            '<circle class="p3" cx="37" cy="4" r="2.8"/>'
            '</svg>')


# ── Rasterizador ─────────────────────────────────────────────────────────────
def _cobertura(lado, amostras=4, barras=None):
    """Quanto de cada pixel a forma cobre, de 0 a 1.

    Amostra `amostras`×`amostras` pontos por pixel e tira a média — é o que dá a
    borda suave. Sem isso, a barra de 2,6 unidades num ícone de 32 pixels sai
    serrilhada e o ícone parece quebrado.

    Só percorre a área de cada barra, não a tela toda: são seis retângulos
    pequenos, e varrer o resto seria trabalho jogado fora.
    """
    cob = [0.0] * (lado * lado)
    escala = lado / 32.0
    passo = 1.0 / amostras
    peso = 1.0 / (amostras * amostras)

    for bx, by, bw, bh, br in (FORMA if barras is None else barras):
        x0, y0 = bx * escala, by * escala
        x1, y1 = (bx + bw) * escala, (by + bh) * escala
        r = br * escala
        # núcleo: o retângulo encolhido pelo raio. A distância até ele define o canto.
        nx0, ny0, nx1, ny1 = x0 + r, y0 + r, x1 - r, y1 - r

        for py in range(max(0, int(y0)), min(lado, int(y1) + 1)):
            for px in range(max(0, int(x0)), min(lado, int(x1) + 1)):
                dentro = 0
                for sy in range(amostras):
                    ay = py + (sy + 0.5) * passo
                    for sx in range(amostras):
                        ax = px + (sx + 0.5) * passo
                        cx = nx0 if ax < nx0 else (nx1 if ax > nx1 else ax)
                        cy = ny0 if ay < ny0 else (ny1 if ay > ny1 else ay)
                        dx, dy = ax - cx, ay - cy
                        if dx * dx + dy * dy <= r * r:
                            dentro += 1
                if dentro:
                    i = py * lado + px
                    # as barras não se tocam, mas o teto protege contra soma > 1
                    cob[i] = min(1.0, cob[i] + dentro * peso)
    return cob


def _rgb(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _png(lado, dados_rgba):
    """PNG mínimo: assinatura + IHDR + IDAT + IEND. Cada linha leva o byte 0
    na frente, que é o filtro 'nenhum' exigido pelo formato."""
    cru = b"".join(b"\x00" + dados_rgba[y * lado * 4:(y + 1) * lado * 4]
                   for y in range(lado))

    def bloco(tipo, dados):
        corpo = tipo + dados
        return (struct.pack(">I", len(dados)) + corpo
                + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(cru, 9))
            + bloco(b"IEND", b""))


def png(lado, escuro=False, fundo=None):
    """Rasteriza o ícone nas DUAS cores: prosa em azul, verso em vermelho.

    `fundo=None` deixa transparente. Para o ícone do iOS passe uma cor: o iPhone
    pinta de preto o que for transparente no apple-touch-icon.
    """
    prosa = [b for b in FORMA if b[0] < 16]
    verso = [b for b in FORMA if b[0] >= 16]
    cor_p = _rgb(AZUL_ESCURO if escuro else AZUL_CLARO)
    cor_v = _rgb(VERM_ESCURO if escuro else VERM_CLARO)
    am = 4 if lado <= 64 else 3
    cob_p = _cobertura(lado, amostras=am, barras=prosa)
    cob_v = _cobertura(lado, amostras=am, barras=verso)
    fr, fg, fb = _rgb(fundo) if fundo else (0, 0, 0)

    saida = bytearray(lado * lado * 4)
    for i in range(lado * lado):
        ap, av = cob_p[i], cob_v[i]
        a = ap + av                      # as colunas não se tocam: soma é segura
        if a <= 0:
            if fundo:
                j = i * 4
                saida[j], saida[j+1], saida[j+2], saida[j+3] = fr, fg, fb, 255
            continue
        # cor média ponderada pela cobertura de cada coluna naquele pixel
        cr = (cor_p[0] * ap + cor_v[0] * av) / a
        cg = (cor_p[1] * ap + cor_v[1] * av) / a
        cb = (cor_p[2] * ap + cor_v[2] * av) / a
        a = min(1.0, a)
        j = i * 4
        if fundo:
            saida[j]   = round(fr + (cr - fr) * a)
            saida[j+1] = round(fg + (cg - fg) * a)
            saida[j+2] = round(fb + (cb - fb) * a)
            saida[j+3] = 255
        else:
            saida[j], saida[j+1], saida[j+2] = round(cr), round(cg), round(cb)
            saida[j+3] = round(255 * a)
    return _png(lado, bytes(saida))


def ico(png_32):
    """ICO com um PNG dentro — formato aceito por todo navegador atual. Existe
    para que `/favicon.ico`, que o navegador pede por conta própria, responda 200."""
    cabecalho = struct.pack("<HHH", 0, 1, 1)          # reservado, tipo ícone, 1 imagem
    entrada = struct.pack("<BBBBHHII",
                          32, 32, 0, 0, 1, 32, len(png_32), 6 + 16)
    return cabecalho + entrada + png_32


if __name__ == "__main__":
    print(svg_favicon())
