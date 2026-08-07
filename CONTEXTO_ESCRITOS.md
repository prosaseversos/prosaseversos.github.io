# Tinta Lenta — site de poesia, composições, textos e artigos

Site estático, hospedado de graça no GitHub Pages. Custo mensal: **R$ 0**.
Só o domínio próprio (opcional, `nome.com.br` no Registro.br, ~R$ 40/ano) cobraria.

**"Tinta Lenta" é nome fictício, por escolha.** O nome pessoal não aparece no site
nem no `autor` do `site.json`. Consequência a ter em conta: ninguém chega aqui
buscando "André Boschetti" — o Google traz leitor **pelo conteúdo** (o verso, o
tema do artigo), não pelo nome. Para inverter isso um dia, basta trocar `nome` e
`autor` no `site.json` e republicar.

## Onde mora

- **Código e textos:** `/Volumes/AndreSA/SISTEMAS DO CLAUDE/Escritos/` (o HD, como os demais)
- **No ar:** https://boschettiandre.github.io — usuário GitHub `boschettiandre`
- **Publicação:** `git push` na `main` → GitHub Actions roda `gerar.py` → site sobe em ~1 min

## Seções

| pasta                  | seção        | formato |
|------------------------|--------------|---------|
| `conteudo/poesia`      | Poesia       | verso   |
| `conteudo/composicoes` | Composições  | verso (com `[Refrão]`) |
| `conteudo/textos`      | Textos       | prosa   |
| `conteudo/artigos`     | Artigos      | prosa   |

Criar uma seção nova = criar a pasta em `conteudo/` e acrescentar uma linha em
`secoes`, no `site.json`. A ordem da lista é a ordem do menu.

Não tem servidor, não tem banco, não tem processo rodando. Nada para reiniciar,
nada para cair. É a diferença deliberada em relação ao Flamma e ao ADM_PRO:
este projeto **não** disputa manutenção com os sistemas de produção.

## Como escrever um texto

Crie um `.md` na pasta da seção:

    conteudo/poesia/2026-08-14-o-nome-do-poema.md

    ---
    titulo: O nome do poema
    data: 2026-08-14
    resumo: Uma linha — é o que o Google mostra no resultado da busca.
    ---

    O texto vem aqui.

Campos do cabeçalho, todos opcionais menos na prática o `titulo`:

| campo       | para quê |
|-------------|----------|
| `titulo`    | título na página, na aba e no Google. Sem ele, usa o nome do arquivo |
| `data`      | `AAAA-MM-DD`. Sem ela, usa o prefixo do nome do arquivo; sem isso, a data do arquivo |
| `resumo`    | a descrição no resultado do Google. Sem ela, usa as primeiras linhas do texto |
| `slug`      | fixa o pedaço da URL. **Use ao renomear texto já publicado**, para não quebrar link |
| `publicado` | `nao` deixa o texto fora do site sem apagar o arquivo |

## O formato de cada gênero

**Poesia e composições** (`"verso": true` no `site.json`): cada quebra de linha é
um verso, cada recuo é preservado, linha em branco separa estrofe. Markdown de
prateleira faria o contrário — colaria os versos num parágrafo só. É a razão de
o gerador ser nosso e não Hugo/Jekyll.

**Composições** aceitam rótulo de estrofe, na convenção de quem escreve letra:

    [Refrão]
    O verso que sempre volta

`[Refrão]` ganha itálico e barra lateral. Qualquer outro rótulo (`[Ponte]`,
`[Verso 2]`) vira legenda discreta.

**Textos e artigos** (`"verso": false`): linhas seguidas viram parágrafo, como
num livro, e a coluna tem ~65 caracteres — a medida em que o olho chega ao fim da
linha e acha o começo da seguinte sem se perder.

Formatação disponível em todos: `*itálico*`, `**negrito**`, `## subtítulo`,
`> citação`, `---` separador, `[link](endereço)`. Só isso, de propósito.

## Cores

`tema/estilo.css` traz duas paletas prontas no alto do arquivo: **azul** (ativa) e
**vermelha** (logo abaixo, comentada). Trocar é comentar um bloco e descomentar o
outro — são os mesmos seis nomes de cor, e cada uma já vem com sua versão para
modo escuro. Nenhuma usa preto puro sobre branco puro: no contraste máximo o texto
vibra e cansa em leitura longa.

## Publicar

**Do Mac:** duplo clique em `run.command` para ver antes. Depois:

    git add -A && git commit -m "novo poema" && git push

**Do celular:** github.com → pasta da seção → "Add file" → escrever → "Commit".
O site se refaz sozinho.

⚠️ **Postou pelo celular? `git pull` no Mac antes de escrever de novo.** Senão o HD
e o GitHub viram duas cópias divergentes do mesmo acervo — o mesmo problema do
`portal.db` do Flamma, que existe em duas versões (HD e servidor) e diverge. Aqui,
divergir significa `git push` recusado, ou pior, um texto escrito no celular sendo
sobrescrito pela versão velha do HD.

## O que fizemos para aparecer no Google

A lição veio do Flamma Cordis: o sitemap dele listava **21 URLs** para um site de
~2.270 páginas, e o Google se comportou de acordo — 22 visitas em duas semanas.
Aqui, desde o primeiro dia:

- **`sitemap.xml` com todas as páginas**, uma a uma, com data de publicação
- **`robots.txt`** apontando o sitemap
- **JSON-LD por texto** — tipo `Poem` para verso (é tipo de verdade no schema.org),
  `Article` para prosa. Diz ao buscador que aquilo é um poema, não uma notícia
- **Canonical** em toda página, contra conteúdo duplicado
- **Open Graph**, para o link ficar apresentável ao ser compartilhado
- **Anterior/próximo** em cada texto: página sem link chegando nela o Google
  visita uma vez e esquece
- **`feed.xml`** (RSS), para quem quiser acompanhar
- **Título e descrição únicos** por página

`gerar.py` imprime a contagem do sitemap ao lado da contagem de textos, toda vez.
Se um dia não fecharem, o erro aparece no mesmo minuto.

**Falta fazer (depende de você, e é o que liga o Google de fato):** cadastrar o
site no [Google Search Console](https://search.google.com/search-console) e enviar
o `sitemap.xml`. Sem isso o Google acha o site sozinho, mas demora semanas.

## Armadilhas já pagas

- **HD é ExFAT** → o macOS cria arquivo-sombra `._nome.md`, binário, que casa com
  `*.md`. O gerador ignora nomes começados em ponto; o `.gitignore` também.
  Sem isso: `UnicodeDecodeError` no build, ou lixo binário no repositório.
- **`.nojekyll`** na saída: sem ele o GitHub Pages passa tudo pelo Jekyll e engole
  arquivos e pastas começados por `_`.
- **URL em `site.json`** alimenta canonical, sitemap e Open Graph. Publicar com a
  URL errada é apontar o Google para endereço que não existe. O Actions se recusa
  a publicar enquanto ela for o exemplo.
- **Trocar o título de um texto já no ar** muda o slug e quebra o link de quem
  compartilhou. Fixe com `slug:`.

## Backup

O repositório do GitHub **é** o backup dos textos — cópia fora do HD, com
histórico de cada versão. Vale a pena conferir de tempos em tempos que o `push`
está mesmo acontecendo. Ver `backup-do-que-nao-se-refaz`: poesia é exatamente o
tipo de coisa que não se refaz.
