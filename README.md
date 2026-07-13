# 🏠 Scraper de imóveis + dashboard, com alertas ntfy

Monitoriza portais de arrendamento de hora a hora (via GitHub Actions) e
notifica-te no telemóvel (via [ntfy.sh](https://ntfy.sh), grátis e sem conta)
**assim que aparece um anúncio novo** dentro dos teus critérios — para seres o
primeiro a contactar o anunciante. Inclui um **dashboard web** (GitHub Pages)
para veres tudo num mapa, com filtros e favoritos.

Cada anúncio é geocodificado (ou usa as coordenadas fornecidas pelo site) e só
conta se estiver dentro do **tempo a pé** que definires a partir de um ponto
central.

## Sites monitorizados

| Site        | Estado          | Notas |
|-------------|-----------------|-------|
| Imovirtual  | ✅ Funcional    | Lê o JSON embutido (`__NEXT_DATA__`); geocodifica a morada. |
| OLX         | ✅ Funcional    | Lê o JSON embutido (`__PRERENDERED_STATE__`); **traz coordenadas** (dispensa geocodificação). |
| Casa Sapo   | ✅ Funcional    | Parsing de HTML (BeautifulSoup); geocodifica a morada. |
| Idealista   | ✅ Via API oficial | O site bloqueia scraping (DataDome), mas a **Search API oficial** é gratuita mediante registo. Precisa de 2 secrets extra. Ver [secção Idealista](#idealista). |

> Nota: Imovirtual e OLX pertencem ao mesmo grupo e cruzam inventário, por isso é
> normal veres o **mesmo apartamento em ambos**. Não os fundimos de propósito
> (para não arriscar esconder um anúncio) — cada card mostra a etiqueta do portal.

---

## O dashboard

Cada execução escreve `docs/listings.json`, que o dashboard (`docs/index.html`)
lê. Publicado no **GitHub Pages**, tens uma página sempre atualizada com:

- **Cartões com foto**, preço, tipologia, zona, tempo a pé e área
- **Mapa** (Leaflet/OpenStreetMap) com um pino por anúncio (cor por portal), o
  ponto central e o círculo do raio
- **Filtros** por portal, tipologia, preço e tempo a pé máximo, + pesquisa por zona
- **Ordenação**: mais recentes, preço, ou mais perto
- **Favoritos** (★) e **ocultar** anúncios (guardados no teu browser)
- **Duplicados** (⧉): botão que colapsa o mesmo anúncio publicado em vários
  portais (Imovirtual/OLX cruzam inventário) num só card, com um link "também
  em: …" para cada portal. Usa a semelhança do título (+ mesmo preço/tipologia),
  conservador para nunca esconder anúncios distintos; **não apaga dados** e está
  desligado por defeito
- Badge **NOVO** para anúncios das últimas 24 h; **modo claro/escuro**
- Estatísticas: total, novos nas últimas 24 h, preço médio e mais barato

### Ativar o GitHub Pages

1. **Settings → Pages** no repositório.
2. Em *Build and deployment* → *Source*: **Deploy from a branch**.
3. *Branch*: `main` e pasta **`/docs`** → **Save**.
4. Passado 1 min, o dashboard fica em `https://SEU_UTILIZADOR.github.io/imoveis-scraper/`.

> Vê localmente: `python -m http.server -d docs` e abre `http://localhost:8000`.
> (Abrir o `index.html` diretamente com `file://` não funciona — o browser
> bloqueia o carregamento do `listings.json`.)

---

## Como funciona

1. Para cada portal ativo, pede a lista **já filtrada no servidor** por preço e
   tipologia, ordenada por mais recente.
2. Obtém as coordenadas de cada anúncio: usa as que o site fornece (OLX) ou
   geocodifica a morada/freguesia via **Nominatim** (1 pedido/seg, com cache).
3. Calcula a distância **haversine** ao ponto central, converte-a em distância
   real por ruas (fator de desvio) e daí num **tempo a pé** (~5 km/h).
4. Guarda no dataset (`docs/listings.json`) os anúncios dentro do raio. Aos que
   ainda não tinham sido notificados, envia notificação **ntfy** com preço,
   tipologia, zona, tempo a pé e link direto.
5. Grava dataset + cache de geocodificação, que **persistem entre execuções**
   através de um commit automático de volta ao repositório.

---

## Configuração rápida

### 1. Pôr o código no GitHub

Cria um repositório (pode ser **privado**, mas o GitHub Pages de repos privados
exige plano pago — para o dashboard público, usa um repo **público**) e envia:

```bash
cd imoveis-scraper
git init && git add . && git commit -m "scraper de imóveis inicial"
git branch -M main
git remote add origin git@github.com:SEU_UTILIZADOR/imoveis-scraper.git
git push -u origin main
```

### 2. Escolher um tópico ntfy e instalar a app

1. Instala a app **ntfy** ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/us/app/ntfy/id1625396347)).
2. Escolhe um **tópico** único e difícil de adivinhar (funciona como palavra-passe:
   quem souber o nome recebe e pode publicar). Ex.: `imoveis-porto-hugo-7h3k9x`.
3. Na app, subscreve esse tópico (**+** → escrever o nome → *Subscribe*).

### 3. Criar o secret no GitHub

**Settings → Secrets and variables → Actions → New repository secret**:
- **Name:** `NTFY_TOPIC`
- **Value:** o nome do teu tópico

> O tópico **nunca** fica no código nem no `config.yaml` — só no secret.

### 4. Ativar o GitHub Actions

1. Separador **Actions** → *enable workflows*.
2. Workflow **"Scraper de imóveis"** → **Run workflow** (corre já uma vez).
3. A partir daí corre sozinho **de hora a hora**.

> **Primeira execução:** o dataset começa vazio, por isso a primeira corrida
> notifica-te de **todos** os anúncios atuais dentro dos critérios (podem ser
> dezenas). É normal — depois só recebes os **novos**.

> **Agendamento:** o `cron` do GitHub Actions é *best-effort* (pode atrasar em
> horas de pico) e é desativado se o repo ficar **60 dias sem atividade** (um
> commit reativa). Para arrendamento à hora, é suficiente.

### 5. Correr localmente (opcional)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export NTFY_TOPIC="o-teu-topico"
python -m src.main            # execução normal (envia notificações + grava dataset)
python -m src.main --dry-run  # grava o dataset mas NÃO envia notificações (ideal para testar)
```

---

## Ajustar os filtros — `config.yaml`

Tudo o que precisas de mexer está em [`config.yaml`](config.yaml).

```yaml
localizacao:
  morada_central: "Rua Dr. Eduardo Santos Silva, 261, 4200-283 Porto"
  lat: 41.1755129     # null -> geocodifica a morada acima no arranque
  lon: -8.5882096
filtros:
  tipologias: [T1, T2]
  preco_maximo: 1150     # €/mês
  raio_minutos: 30       # tempo MÁXIMO a pé
  velocidade_kmh: 5.0
  fator_desvio: 1.3      # linha reta -> distância real por ruas (1.0 = reta pura)
scraping:
  sites: [imovirtual, olx, casasapo]   # remove/adiciona portais
  paginas_max: 2
dataset:
  ficheiro: "docs/listings.json"
  dias_historico: 30     # remove anúncios não vistos há mais de N dias
```

**Distância:** o haversine dá a distância em **linha reta**; multiplicamos pelo
`fator_desvio` (1.3 ≈ realista em cidade) para estimar o percurso a pé real.

**Precisão da localização:** o OLX fornece coordenadas (exatas ou aproximadas,
conforme o vendedor). Imovirtual e Casa Sapo são geocodificados a partir da
rua/freguesia — quando só há freguesia, usa-se o centroide e a distância é
marcada como *(aprox.)*.

---

## Idealista

O site idealista.pt usa **DataDome**, um anti-bot agressivo (testámos: HTTP 403
logo à entrada). **Não contornamos anti-bot** — em vez disso usamos a
**Search API oficial** do Idealista, gratuita mediante aprovação. Bónus: a API
suporta pesquisa por **raio a partir de um ponto central** e devolve
**coordenadas** de cada anúncio (dispensa geocodificação, como o OLX).

### Obter credenciais (uma vez)

1. Vai a <https://developers.idealista.com/access-request>.
2. Preenche o formulário (nome, email, descrição do projeto — ex.: "alertas
   pessoais de arrendamento no Porto"). A aprovação chega por email com uma
   **apikey** e um **secret** (pode demorar alguns dias).
3. No GitHub: **Settings → Secrets and variables → Actions**, cria:
   - `IDEALISTA_APIKEY` — a apikey
   - `IDEALISTA_SECRET` — o secret

Sem estes secrets, o Idealista é simplesmente **saltado** (os outros portais
continuam a funcionar normalmente).

### Quota da API (importante)

O plano gratuito tem uma quota mensal baixa (na ordem de **~100 pedidos/mês** —
o email de aprovação diz o valor exato). Correr de hora a hora estouraria a
quota, por isso o Idealista tem **cadência própria**: só consulta a API se a
última chamada tiver sido há mais de `idealista_horas_entre` horas
(config.yaml; por omissão **8h** ≈ 90 pesquisas/mês). O timestamp persiste em
`idealista_state.json` (commit automático). Se receberes HTTP 429 (quota
excedida), aumenta esse valor.

### Alternativa sem API: alerta por email nativo

Se não quiseres esperar pela aprovação: conta grátis em idealista.pt → pesquisa
com os teus filtros → **"Guardar pesquisa"** → ativa o **alerta por email**.

---

## Se um site mudar de estrutura

Todos os scrapers falham de forma limpa (imprimem um aviso e não partem os
outros). Onde ajustar:

- **Imovirtual** (`src/scrapers/imovirtual.py`): lemos o `<script id="__NEXT_DATA__">`.
  Verifica `NEXT_DATA_RE`, o caminho `...["searchAds"]["items"]` e os campos em
  `_to_listing`. O mapa tipologia↔quartos está em `src/scrapers/base.py`
  (`TIP_TO_ROOMS`): a contagem inclui a sala (T1 = `TWO`, T2 = `THREE`).
- **OLX** (`src/scrapers/olx.py`): lemos `window.__PRERENDERED_STATE__`
  (`STATE_RE`) e `...["listing"]["listing"]["ads"]`. A categoria de arrendamento
  é o caminho `SEARCH_PATH`; a tipologia vem já como "T1"/"T2" no `params`.
- **Casa Sapo** (`src/scrapers/casasapo.py`): é HTML. Os **seletores CSS estão
  todos no dicionário `SEL`** no topo do ficheiro — o sítio a atualizar se o
  layout mudar. A tipologia sai do atributo `data-title` e é filtrada no cliente.
- **Idealista** (`src/scrapers/idealista.py`): usa a API oficial — não há
  seletores para partir. Os endpoints (`OAUTH_URL`, `SEARCH_URL`, versão `3.5`)
  estão no topo do ficheiro; se a API mudar de versão, ajusta aí.

Para inspecionar o JSON de um site:
```python
import json, re, requests
html = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}).text
m = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html, re.S)  # ou __PRERENDERED_STATE__
print(list(json.loads(m.group(1))["props"].keys()))
```

## Adicionar mais sites

1. Cria `src/scrapers/<site>.py` com uma classe que herda de `BaseScraper` e
   implementa `fetch() -> list[Listing]`.
2. Regista-a em `src/scrapers/registry.py`.
3. Ativa-a em `scraping.sites` no `config.yaml`.

O resto (coordenadas/geocodificação, filtro de distância, dedup, notificações,
dashboard) é partilhado e funciona para qualquer `Listing`.

---

## Estrutura do projeto

```
imoveis-scraper/
├── config.yaml                  # <- os teus filtros
├── requirements.txt
├── geocode_cache.json           # cache de geocodificação (commit automático)
├── idealista_state.json         # cadência da API do Idealista (commit automático)
├── .github/workflows/scraper.yml
├── docs/                        # GitHub Pages
│   ├── index.html               # dashboard
│   └── listings.json            # dataset (commit automático)
└── src/
    ├── main.py                  # orquestrador
    ├── config.py                # config.yaml + NTFY_TOPIC
    ├── models.py                # Listing (anúncio normalizado)
    ├── geo.py                   # Nominatim + haversine + tempo a pé
    ├── notifier.py              # envio ntfy
    ├── store.py                 # dataset + deduplicação
    └── scrapers/
        ├── base.py              # BaseScraper + mapa tipologia<->quartos
        ├── registry.py          # portais disponíveis
        ├── imovirtual.py  ✅
        ├── olx.py         ✅
        ├── casasapo.py    ✅
        └── idealista.py   ✅ (API oficial — ver secção Idealista)
```

## Boas práticas

- **Educado:** pausas entre pedidos, User-Agent normal de browser, sem paralelismo.
- **Nominatim:** 1 pedido/seg com cache; põe um contacto/URL em
  `geocoding.user_agent` (política de uso do OSM).
- **Sem contornar anti-bot:** se um site bloquear, o scraper falha limpo e os
  restantes continuam.
