# Prosas e Versos — site de poesia, composições, textos e artigos

Site estático, hospedado de graça no GitHub Pages. Custo mensal: **R$ 0**.
Só o domínio próprio (opcional, `nome.com.br` no Registro.br, ~R$ 40/ano) cobraria.

**O nome pessoal não aparece em lugar nenhum**, por escolha: nem no site, nem no
`autor` do `site.json`, nem na URL. Foi por isso que o site vive numa conta GitHub
própria (`prosaseversos`) e não na pessoal — repositório de site do GitHub Pages
herda o nome do dono na URL, e `boschettiandre.github.io` estamparia o nome.
Consequência a ter em conta: ninguém chega aqui buscando "André Boschetti" — o
Google traz leitor **pelo conteúdo** (o verso, o tema do artigo), não pelo nome.

## Onde mora

- **Código e textos:** `/Volumes/AndreSA/SISTEMAS DO CLAUDE/Escritos/` (o HD, como os demais)
- **No ar:** https://prosaseversos.github.io
- **Conta GitHub:** `prosaseversos` — **separada** da pessoal `boschettiandre`
- **Publicação:** `git push` na `main` → GitHub Actions roda `gerar.py` → site sobe em ~1 min

⚠️ **Uma chave SSH pertence a uma conta só, no GitHub.** A `~/.ssh/github_ed25519`
está registrada na conta `prosaseversos`. Se um dia ela for para a `boschettiandre`,
o push deste site passa a ser recusado — e a mensagem de erro não diz o motivo.

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

## O painel — escrever pelo navegador

**https://prosaseversos.github.io/admin/** — de qualquer lugar, inclusive do celular.

Editor com prévia ao lado, lista dos textos, importação de `.docx` e botão de
publicar. Cmd/Ctrl+S publica.

### Por que não é um Flask com login, como o do Flamma

O GitHub Pages **não executa código** — só entrega arquivos. Não há onde rodar um
servidor. Então o painel é uma página que roda **no navegador** e conversa direto
com a API do GitHub: cada "Publicar" é um commit, o commit dispara o Actions, o
Actions republica. Sem banco e sem cópia intermediária — a fonte é o repositório.

Consequência: não há sessão com senha. O acesso é um **token do GitHub** que fica
no `localStorage` do aparelho. Peça o token com o mínimo: *Only select
repositories* → este repositório, e *Contents: Read and write* (mais *Actions:
Read-only* para ver o andamento). Assim, se vazar, o alcance é um repositório de
poesia que já é público — e revoga-se na mesma página onde foi criado.

O painel é público (não dá para esconder arquivo em site estático), mas **sem
token não faz nada**: a API do GitHub recusa. Está fora do sitemap, com
`Disallow: /admin/` no robots e `noindex` na página.

### O que ele faz e o que não faz

- **`.docx` é lido no próprio navegador.** Um .docx é ZIP + XML, e o navegador
  sabe descompactar (`DecompressionStream`) e ler XML (`DOMParser`). O `<w:br/>`
  do Shift+Enter vira quebra de verso, como no importador do Mac.
- **PDF não dá pelo navegador** — extrair texto de PDF exige interpretar fontes e
  streams. Para PDF, use o `importar.command` no Mac.
- **Renomear texto publicado**: o painel avisa que o endereço vai mudar e apaga o
  arquivo antigo, para o texto não ficar no site em dois endereços (o Google
  trataria como conteúdo duplicado).
- **A prévia espelha o `render()` do `gerar.py`.** Se um dia divergirem, o site é
  a verdade — mexeu na regra de um, mexa no outro.

⚠️ **`SECOES` no `admin.html` precisa espelhar `secoes` do `site.json`.** Se
divergirem, o texto vai para uma pasta que o gerador não conhece e some do site
sem dar erro nenhum.

## Importar do Word, do PDF, do que já está escrito

Arraste os arquivos para a subpasta da seção e dê duplo clique em
`importar.command` (ele importa, regera o site e abre para conferir):

    entrada/poesia/meu-poema.docx
    entrada/artigos/ensaio.pdf

| formato | como é lido |
|---------|-------------|
| `.docx` | leitura própria do XML, só stdlib |
| `.doc` `.rtf` `.odt` `.html` | `textutil`, nativo do macOS |
| `.pdf` | `pdftotext -layout`; se faltar, `pypdf` |
| `.txt` `.md` | direto (tenta UTF-8, cp1252, latin-1) |
| `.pages` | **não dá** — no Pages: Arquivo → Exportar para → Word |

**A seção vem da pasta em que você soltou o arquivo**, não de adivinhação. Chutar
se um texto é poema ou crônica erra justamente nos casos interessantes: o poema em
prosa, a crônica em versos. O importador só *avisa* quando a pasta e a cara do
texto discordam — e nunca corrige por conta própria.

### O que o importador faz de diferente

- **Shift+Enter do Word vira quebra de verso.** No .docx isso é `<w:br/>` dentro
  do parágrafo, e as bibliotecas comuns descartam — a estrofe chegaria numa linha
  só. Por isso o XML é lido à mão. Tabulação vira recuo, que em poesia é forma.
- **Em prosa, o parágrafo é remontado.** No PDF a linha acaba onde a margem
  mandou, não onde o autor quis; deixar essas quebras faria o site colar as linhas
  com espaço no meio. Hífen de fim de linha é colado (translineação) e o relatório
  diz quantas vezes, porque de vez em quando era palavra composta.
- **Em verso, nunca se junta nada.** A quebra é o texto.
- **Número de página solto** (linha só com dígitos, típico de PDF) é removido, e o
  relatório conta quantas saíram.
- **O original é movido, nunca apagado**, para `entrada/_ja-importados/`.

### O que conferir depois de importar

⚠️ **A data.** Vem da data de modificação do arquivo, que raramente é a data em
que o texto foi escrito. O importador não tem como saber — ajuste o `data:`.
⚠️ **PDF escaneado não tem texto**, só imagem. O importador diz isso em vez de
gerar arquivo vazio; precisaria de OCR.

**Este importador não é dependência do site.** `gerar.py` continua sem nenhuma, e
o GitHub Actions só roda ele. `pdftotext`/`pypdf` são ferramenta de escrivaninha e
só precisam existir aqui no Mac.

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

## A primeira publicação (uma vez só)

1. **Chave SSH** — `~/.ssh/github_ed25519`, criada só para o GitHub e registrada na
   conta **`prosaseversos`** (github.com/settings/keys, logado como ela). A chave do
   ADM_PRO (`admpro_ed25519`) continua intacta; o `~/.ssh/config` diz qual usar para
   cada host, com `IdentitiesOnly yes` — sem isso o ssh oferece a chave errada
   primeiro e o GitHub recusa.
2. **Repositório** `prosaseversos.github.io`, na conta `prosaseversos`, **público**.
   O nome não é escolha estética: repositório com o nome exato do dono é o que dá a
   URL raiz `https://prosaseversos.github.io`. Qualquer outro nome empurra o site
   para `https://prosaseversos.github.io/nome-do-repo/`, e aí a `url` do `site.json`
   precisa acompanhar. Público é exigência do GitHub Pages no plano gratuito.
3. **Ligar o Pages** — no repositório: Settings → Pages → *Source:* **GitHub Actions**.
   Sem este passo o Actions roda, fica verde, e nada vai para o ar.
4. **Search Console** — search.google.com/search-console, adicionar o site e enviar
   `sitemap.xml`. É o passo que efetivamente liga o Google; sem ele o buscador acha
   o site sozinho, mas leva semanas.

## Publicar

**Do Mac:** duplo clique em **`publicar.command`**. Ele gera, pergunta uma
descrição e sobe. Nenhum comando de terminal.

Os três atalhos, na ordem em que se usam:

| duplo clique em | faz |
|-----------------|-----|
| `importar.command` | traz Word/PDF de `entrada/`, regera e abre para conferir |
| `run.command` | só regera e abre, para ver antes de publicar |
| `publicar.command` | manda para o site e **espera a confirmação do GitHub** |

`publicar.command` faz, nesta ordem e por um motivo cada:
1. **Gera antes de enviar** — se o gerador reclamar, nada sobe.
2. **`git pull --rebase` antes do push** — traz o que foi escrito pelo celular.
   Sem isso, HD e GitHub viram duas cópias que divergem.
3. **Espera o GitHub Actions terminar** — o push só entrega os arquivos; quem
   monta e publica é o Actions, e é ele que pode falhar. Dar o push por
   publicação é como dar o deploy por concluído sem conferir: foi assim que o
   ADM_PRO passou 5 dias fora do ar.

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
