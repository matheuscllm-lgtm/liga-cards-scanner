"""Coletor AO VIVO de ofertas da Liga Pokemon (cartas avulsas / singles).

Como funciona (em linguagem simples):

- A Liga bloqueia programas que tentam baixar paginas "por fora" (erro 403,
  via Cloudflare — o "porteiro" anti-robo do site). A unica rota que passa
  e usar um NAVEGADOR DE VERDADE: este coletor abre o Google Chrome na sua
  tela (modo "headful", janela visivel) controlado pela biblioteca
  ``patchright`` (uma variacao do Playwright que nao e detectada como robo).
- O Chrome usa um PERFIL PROPRIO e isolado (pasta ``.pw_profile_liga_singles``
  na sua pasta de usuario), entao nao briga com o seu Chrome do dia a dia
  nem com outros scanners headful (COMC, selados).
- Para cada SET pedido (ex.: PRE = Evolucoes Prismaticas), o coletor:
    1. Abre a pagina de busca do set e rola ate o fim (a Liga usa
       "infinite scroll": as cartas vao aparecendo conforme se rola).
    2. Le a faixa de preco de cada carta na propria listagem; se o preco
       MAXIMO entre todos os vendedores ja e menor que o piso (R$50),
       nem visita a pagina da carta (economia grande de tempo).
    3. Visita a pagina de cada carta restante, rola para carregar todos
       os vendedores, e escolhe a oferta mais barata que seja:
       INGLES + NM exato + sem extra (ex.: "Foil" reverso) + nao-leilao.
- NM e checado na CELULA DEDICADA de condicao (``div.quality`` com classe
  ``quality_nm`` E texto exatamente igual a "NM"). NUNCA por substring da
  linha — substring ja vazou SP no passado (invariante do operador).
- CHECKPOINT: o progresso fica em ``data/liga_live_state.json``. Se o scan
  cair no meio (queda de luz, crash do Chrome), rode de novo com
  ``--resume`` e ele continua de onde parou.
- RECICLAGEM: o Chrome e fechado e reaberto a cada ~40 cartas (licao do
  prototipo antigo: sessoes longas degradam e acabam travando).
- HONESTIDADE: se o Cloudflare nao liberar ou o site mudar, o coletor
  salva a pagina (HTML + screenshot) em ``data/debug/`` e levanta um erro
  claro. Ele NUNCA inventa preco.

Conhecimento de DOM (de onde vem cada dado — confirmado ao vivo 2026-06):

- Listagem do set:  /?view=cards/search&card=ed=<CODIGO>
    * cada carta = ``div.card-item``
    * link = ``a.main-link-card`` (href tem nome, numero e set)
    * faixa de preco = ``div.avgp-minprc`` / ``div.avgp-maxprc``
- Pagina da carta:  /?view=cards/card&card=...&ed=...&num=...
    * cada vendedor = ``div.store``
    * preco = ``div.new-price``. DOIS formatos coexistem:
        - linhas renderizadas no load inicial: TEXTO ("R$ 1.089,90")
        - linhas carregadas via AJAX (ex.: depois do filtro de idioma):
          ANTI-SCRAPING — cada digito e um <div> com classe ofuscada de
          5 letras cujo CSS aponta um sprite JPG (background-position);
          o separador decimal e um <div> com imagem v2.png. Decodificamos
          por template matching (templates fixos dos 10 digitos em
          data/liga_digit_templates/, herdados do scanner de selados —
          a fonte do sprite e estavel, correlacao ~1.0).
    * idioma = ``div.lang img`` atributo ``title`` (match exato "Ingles")
    * condicao = ``div.quality`` (classe ``quality_nm`` + texto "NM")
    * extras = ``div.extras`` (ex.: title="Extra: Foil")

ARMADILHA CRITICA (descoberta no smoke 2026-06-10): a pagina da carta SO
carrega ~16 vendedores no load inicial, ordenados por preco — em carta
dominada por PT, NENHUM vendedor EN aparece. E OBRIGATORIO clicar o
checkbox de filtro "Ingles" (``input#field_5_1``) para o site carregar
as ofertas EN via AJAX (que chegam com o preco anti-scraping acima).
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.collectors.liga_pokemon import LigaOffer

logger = logging.getLogger(__name__)

LIGA_BASE = "https://www.ligapokemon.com.br"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_STATE_PATH = DATA_DIR / "liga_live_state.json"
DEFAULT_CSV_PATH = DATA_DIR / "liga_offers.csv"
DEBUG_DIR = DATA_DIR / "debug"
DEFAULT_PROFILE_DIR = Path.home() / ".pw_profile_liga_singles"
DIGIT_TEMPLATES_DIR = DATA_DIR / "liga_digit_templates"

# Checkbox do filtro de idioma "Ingles" na pagina da carta (DOM da Liga).
EN_FILTER_SELECTOR = "input#field_5_1"

# Quantas paginas de carta antes de reciclar (fechar e reabrir) o Chrome.
RECYCLE_EVERY = 40
# Scroll do infinite-scroll: pausa entre rolagens e rodadas estaveis p/ parar.
SCROLL_PAUSE_S = 1.5
SCROLL_STABLE_ROUNDS = 3
SCROLL_MAX_ROUNDS = 60
# Espera maxima pelo Cloudflare liberar a pagina.
CF_MAX_WAIT_S = 90

# Codigo de set da Liga (?ed=XXX) -> nome canonico do set no pokemontcg.io.
# O coletor emite o nome em INGLES para o matcher casar direto (sem fuzzy).
# Para um set fora desta lista, use --sets "CODIGO=Nome Em Ingles".
ED_SETS: dict[str, str] = {
    # Scarlet & Violet era
    "SVI": "Scarlet & Violet",
    "PAL": "Paldea Evolved",
    "OBF": "Obsidian Flames",
    "MEW": "151",
    "PAR": "Paradox Rift",
    "PAF": "Paldean Fates",
    "TEF": "Temporal Forces",
    "TWM": "Twilight Masquerade",
    "SFA": "Shrouded Fable",
    "SCR": "Stellar Crown",
    "SSP": "Surging Sparks",
    "PRE": "Prismatic Evolutions",
    "JTG": "Journey Together",
    "DRI": "Destined Rivals",
    # Sword & Shield era (mais procurados)
    "CRZ": "Crown Zenith",
    "SIT": "Silver Tempest",
    "LOR": "Lost Origin",
    "PGO": "Pokémon GO",
    "ASR": "Astral Radiance",
    "BRS": "Brilliant Stars",
    "FST": "Fusion Strike",
    "CEL": "Celebrations",
    "EVS": "Evolving Skies",
    "CRE": "Chilling Reign",
    "BST": "Battle Styles",
    "SHF": "Shining Fates",
    "VIV": "Vivid Voltage",
}

# Titulos de bandeira que contam como "Ingles" (match EXATO, nao substring:
# "Portugues / Ingles" e combo e NAO conta como oferta EN).
EN_TITLES = {"Inglês", "Ingles", "Inglés"}

_AUCTION_RE = re.compile(r"leil[aã]o|\blance\b", re.IGNORECASE)


class LigaBlockedError(RuntimeError):
    """Cloudflare nao liberou / site bloqueou. Evidencia salva em data/debug/."""


class LigaDomChangedError(RuntimeError):
    """A pagina carregou mas o DOM esperado nao esta la (site mudou?)."""


# ──────────────────────────────────────────────────────────────────────────
# Parsers puros (testaveis sem navegador)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class ListingCard:
    """Uma carta como aparece na listagem do set (antes de abrir a pagina)."""
    name: str
    number: str          # "156" (so o numero da carta)
    ed_code: str         # "PRE"
    url: str             # URL absoluta da pagina da carta
    min_brl: float | None = None   # menor preco entre TODOS vendedores/idiomas
    max_brl: float | None = None   # maior preco — se < piso, da pra pular


@dataclass
class SellerOffer:
    """Uma oferta de UM vendedor na pagina da carta."""
    price_brl: float | None
    languages: list[str] = field(default_factory=list)
    condition: str = ""            # texto da celula dedicada (ex. "NM", "SP")
    extras: list[str] = field(default_factory=list)
    seller: str = ""
    auction: bool = False

    @property
    def is_en(self) -> bool:
        return any(t in EN_TITLES for t in self.languages)

    @property
    def is_nm(self) -> bool:
        # Invariante dura: match EXATO no texto da celula dedicada.
        return self.condition == "NM"


def parse_brl(text: str | None) -> float | None:
    """'R$ 1.089,90' -> 1089.90. Devolve None se nao parsear."""
    if not text:
        return None
    cleaned = re.sub(r"[R$\s\xa0]", "", text.strip())
    if not cleaned:
        return None
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def _soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


# ──────────────────────────────────────────────────────────────────────────
# Decoder do preco anti-scraping (sprite de digitos)
#
# As linhas de vendedor carregadas via AJAX nao tem o preco como texto:
# cada digito e um <div> com classe ofuscada de 5 letras; uma regra CSS
# inline da pagina mapeia a classe para um background-position dentro de
# um sprite JPG (pasta /imgnum/ no CDN). Classe e URL do sprite mudam a
# cada render, mas a FONTE dos glifos e estavel — entao 10 templates
# fixos (data/liga_digit_templates/{0..9}.png, 7x15 px) decodificam
# qualquer render por correlacao normalizada (mesma tecnica validada em
# producao no scanner de selados; score ~1.0 quando casa).
# ──────────────────────────────────────────────────────────────────────────

_SPRITE_URL_RE = re.compile(r"background-image:url\(([^)]+/imgnum/[^)]+)\)")
_DIGIT_CLASS_RE = re.compile(
    r"\.([A-Za-z]{5})\s*\{\s*background-position\s*:\s*(-?\d+)px\s+(-?\d+)px"
)
_SEPARATOR_IMG_RE = re.compile(r"/v\d+\.png")
DIGIT_MATCH_THRESHOLD = 0.85


def _load_digit_templates() -> dict[str, list]:
    """Carrega os templates {digito: [arrays 15x7]} (variantes opcionais
    {d}b.png..{d}e.png cobrem pequenas diferencas de anti-aliasing)."""
    import numpy as np
    from PIL import Image

    out: dict[str, list] = {}
    for d in "0123456789":
        arrs = []
        for suffix in ("", "b", "c", "d", "e"):
            p = DIGIT_TEMPLATES_DIR / f"{d}{suffix}.png"
            if p.exists():
                arrs.append(np.asarray(Image.open(p).convert("L"), dtype=float))
        if not arrs:
            raise RuntimeError(
                f"Template de digito ausente: {DIGIT_TEMPLATES_DIR / (d + '.png')}"
            )
        out[d] = arrs
    return out


def _normalized_correlation(a, b) -> float:
    """Equivalente ao cv2.TM_CCOEFF_NORMED para imagens do MESMO tamanho."""
    import numpy as np

    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    if denom == 0:
        return -1.0
    return float((a * b).sum() / denom)


def _decode_sprite_cell(sprite, x: int, y: int, templates) -> str:
    cell = sprite[y:y + 15, x:x + 7]
    if cell.shape != (15, 7):
        return "?"
    best_digit, best_score = "?", -1.0
    for digit, tpl_list in templates.items():
        for tpl in tpl_list:
            score = _normalized_correlation(cell, tpl)
            if score > best_score:
                best_score, best_digit = score, digit
    return best_digit if best_score >= DIGIT_MATCH_THRESHOLD else "?"


def build_class_digit_map(html: str, fetch_binary) -> dict[str, str]:
    """Le as regras CSS inline da pagina e devolve {classe_ofuscada: digito}.

    ``fetch_binary(url) -> bytes`` baixa o sprite (na sessao Chrome, para
    herdar cookies do Cloudflare). Devolve {} se a pagina nao usa sprite.
    """
    import io

    import numpy as np
    from PIL import Image

    m = _SPRITE_URL_RE.search(html)
    if not m:
        return {}
    sprite_url = m.group(1).strip()
    if sprite_url.startswith("//"):
        sprite_url = "https:" + sprite_url
    sprite = np.asarray(
        Image.open(io.BytesIO(fetch_binary(sprite_url))).convert("L"), dtype=float
    )
    templates = _load_digit_templates()
    out: dict[str, str] = {}
    for cm in _DIGIT_CLASS_RE.finditer(html):
        cls = cm.group(1)
        x, y = -int(cm.group(2)), -int(cm.group(3))
        out[cls] = _decode_sprite_cell(sprite, x, y, templates)
    return out


def decode_price_div(price_div, class_digit_map: dict[str, str]) -> float | None:
    """Reconstroi o preco de um ``div.new-price`` em formato sprite.

    Caminha pelos <div> filhos: classe ofuscada -> digito; imagem v*.png
    -> separador. O ULTIMO separador e o decimal; anteriores sao de
    milhar (robusto para "1.299,90" independente da imagem usada)."""
    tokens: list[str] = []
    for child in price_div.find_all("div", recursive=False):
        classes = child.get("class") or []
        if "imgnum-monet" in classes:  # label "R$"
            continue
        style = child.get("style") or ""
        if _SEPARATOR_IMG_RE.search(style):
            tokens.append(",")
            continue
        for c in classes:
            if c in class_digit_map:
                tokens.append(class_digit_map[c])
                break
    if not tokens or "?" in tokens:
        return None
    # ultimo separador = decimal; demais = milhar (descartados)
    if "," in tokens:
        last = len(tokens) - 1 - tokens[::-1].index(",")
        digits_int = [t for t in tokens[:last] if t != ","]
        digits_dec = tokens[last + 1:]
        if not digits_int or not digits_dec:
            return None
        text = "".join(digits_int) + "." + "".join(digits_dec)
    else:
        text = "".join(tokens)
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_listing_cards(html: str, ed_code: str, base: str = LIGA_BASE) -> list[ListingCard]:
    """Extrai as cartas de uma pagina de listagem de set (apos o scroll)."""
    soup = _soup(html)
    out: list[ListingCard] = []
    seen: set[str] = set()
    for item in soup.select("div.card-item"):
        link = item.select_one("a.main-link-card") or item.select_one(
            'a[href*="view=cards/card"]'
        )
        if link is None:
            continue
        href = link.get("href") or ""
        if not href or href in seen:
            continue
        seen.add(href)
        href_dec = urllib.parse.unquote(href)
        num_m = re.search(r"[?&]num=(\w+)", href_dec)
        number = num_m.group(1) if num_m else ""
        # Nome: do parametro card=Nome (156/131) — remove o sufixo (n/total).
        card_m = re.search(r"[?&]card=([^&]+)", href_dec)
        raw_name = card_m.group(1) if card_m else ""
        name = re.sub(r"\s*\(\w+\s*/\s*\w+\)\s*$", "", raw_name).strip()
        if not name:
            label = item.select_one("span.invisible-label b")
            name = label.get_text(strip=True) if label else ""
        if not name:
            continue
        min_el = item.select_one("div.avgp-minprc")
        max_el = item.select_one("div.avgp-maxprc")
        out.append(
            ListingCard(
                name=name,
                number=number,
                ed_code=ed_code,
                url=base + href if href.startswith("/") else href,
                min_brl=parse_brl(min_el.get_text() if min_el else None),
                max_brl=parse_brl(max_el.get_text() if max_el else None),
            )
        )
    return out


def parse_seller_offers(
    html: str, class_digit_map: dict[str, str] | None = None
) -> list[SellerOffer]:
    """Extrai as ofertas de vendedores (``div.store``) da pagina da carta.

    Cada ``div.store`` tem blocos duplicados (mobile/desktop) com os MESMOS
    valores — usamos ``select_one``/sets para nao duplicar dados.

    ``class_digit_map`` (de ``build_class_digit_map``) decodifica precos em
    formato sprite (linhas AJAX). Sem o mapa, essas linhas ficam com
    ``price_brl=None`` — nunca um preco inventado.
    """
    soup = _soup(html)
    offers: list[SellerOffer] = []
    for store in soup.select("div.store"):
        price_el = store.select_one("div.new-price")
        price = parse_brl(price_el.get_text() if price_el else None)
        if price is None and price_el is not None and class_digit_map:
            price = decode_price_div(price_el, class_digit_map)

        languages: list[str] = []
        for img in store.select("div.lang img"):
            title = (img.get("title") or "").strip()
            if title and title not in languages:
                languages.append(title)

        condition = ""
        for q in store.select("div.quality"):
            classes = q.get("class") or []
            # So a celula de condicao do vendedor (quality_nm, quality_sp...),
            # nunca o controle de filtro da pagina (quality-list).
            if any(c.startswith("quality_") for c in classes):
                condition = q.get_text(strip=True)
                break

        extras: list[str] = []
        for ex in store.select("div.extras"):
            label = (ex.get("title") or ex.get_text(strip=True) or "").strip()
            label = re.sub(r"^Extra:\s*", "", label)
            if label and label not in extras:
                extras.append(label)

        seller = ""
        seller_link = store.select_one('a[href*="mp/showcase"]')
        if seller_link:
            m = re.search(r"[?&]id=(\d+)", seller_link.get("href") or "")
            if m:
                seller = f"loja#{m.group(1)}"

        store_classes = " ".join(store.get("class") or [])
        auction = bool(
            _AUCTION_RE.search(store_classes)
            or _AUCTION_RE.search(store.get_text(" ", strip=True))
        )

        offers.append(
            SellerOffer(
                price_brl=price,
                languages=languages,
                condition=condition,
                extras=extras,
                seller=seller,
                auction=auction,
            )
        )
    return offers


def pick_buy_offer(offers: list[SellerOffer]) -> SellerOffer | None:
    """Escolhe a oferta de COMPRA: a mais barata que seja EN + NM exato e
    nao-leilao.

    Sobre "Extra: Foil": NAO e criterio de exclusao. Em cartas chase
    (SIR/secret), TODOS os vendedores marcam Foil porque a carta so existe
    em foil — excluir mataria exatamente as cartas que interessam. O lado
    do preco de referencia ja casa a versao certa (busca por numero +
    prioridade holofoil no pokemontcg.io)."""
    eligible = [
        o for o in offers
        if o.price_brl is not None
        and o.is_en
        and o.is_nm
        and not o.auction
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda o: o.price_brl)


# ──────────────────────────────────────────────────────────────────────────
# Sessao Chrome (patchright) com reciclagem
# ──────────────────────────────────────────────────────────────────────────

class _ChromeSession:
    """Chrome real via patchright, perfil persistente proprio e isolado."""

    def __init__(self, profile_dir: Path | None = None, headless: bool = False):
        self.profile_dir = Path(profile_dir or DEFAULT_PROFILE_DIR)
        self.headless = headless
        self._pw = None
        self._ctx = None
        self._page = None

    def _ensure(self):
        if self._ctx is not None:
            return
        try:
            from patchright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError(
                "patchright nao instalado. Rode: pip install patchright "
                "(e tenha o Google Chrome instalado)."
            ) from exc
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",
            headless=self.headless,
            no_viewport=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-quic",  # evita ERR_QUIC_PROTOCOL_ERROR com Cloudflare
            ],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    @property
    def page(self):
        self._ensure()
        return self._page

    def close(self):
        for closer in (lambda: self._ctx.close(), lambda: self._pw.stop()):
            try:
                closer()
            except Exception:
                pass
        self._ctx = self._page = self._pw = None

    def fetch_binary(self, url: str, timeout_s: float = 60) -> bytes:
        """Baixa um arquivo (ex.: sprite de digitos) DENTRO da sessao
        Chrome — herda os cookies do Cloudflare automaticamente."""
        self._ensure()
        resp = self._ctx.request.get(url, timeout=timeout_s * 1000)
        return resp.body()

    def apply_en_filter(self) -> bool:
        """Clica o checkbox de filtro 'Ingles' na pagina da carta.

        OBRIGATORIO: sem ele a pagina so mostra os ~16 vendedores mais
        baratos (quase sempre PT) e as ofertas EN nem sao carregadas.
        Devolve False (com warning) se o checkbox sumiu do DOM."""
        result = self.page.evaluate(
            """(sel) => {
                const cb = document.querySelector(sel);
                if (!cb) return 'no-checkbox';
                if (!cb.checked) cb.click();
                return 'ok';
            }""",
            EN_FILTER_SELECTOR,
        )
        if result == "no-checkbox":
            logger.warning(
                "Checkbox do filtro Ingles (%s) nao encontrado — DOM mudou? "
                "Ofertas EN podem ficar de fora.", EN_FILTER_SELECTOR,
            )
            return False
        time.sleep(3)  # AJAX das linhas EN
        try:
            self.page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        return True

    def recycle(self):
        logger.info("Reciclando o Chrome (fecha e reabre — anti-degradacao)...")
        self.close()
        self._ensure()

    # -- navegacao -------------------------------------------------------

    def _wait_cloudflare(self, max_wait: float = CF_MAX_WAIT_S) -> bool:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                title = (self._page.title() or "").lower()
            except Exception:
                title = ""
            if not any(s in title for s in ("momento", "just a moment", "access denied", "attention required")):
                return True
            time.sleep(1.5)
        return False

    def _save_debug(self, tag: str) -> Path:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = DEBUG_DIR / f"{tag}_{stamp}.html"
        try:
            html_path.write_text(self._page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            self._page.screenshot(path=str(DEBUG_DIR / f"{tag}_{stamp}.png"))
        except Exception:
            pass
        return html_path

    def fetch(
        self,
        url: str,
        wait_selector: str,
        scroll_count_selector: str | None = None,
        goto_timeout_s: float = 120,
    ) -> str:
        """Abre a URL, espera o Cloudflare, espera o seletor e (opcional)
        rola ate o numero de elementos estabilizar. Devolve o HTML final."""
        page = self.page
        page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_s * 1000)
        if not self._wait_cloudflare():
            evidence = self._save_debug("cf_block")
            raise LigaBlockedError(
                f"Cloudflare nao liberou {url} em {CF_MAX_WAIT_S}s. "
                f"Evidencia salva em {evidence}. Tente de novo mais tarde; "
                "se persistir, o IP pode estar bloqueado."
            )
        selector_ok = True
        try:
            page.wait_for_selector(wait_selector, state="attached", timeout=30_000)
        except Exception:
            selector_ok = False
        if scroll_count_selector:
            self._scroll_until_stable(scroll_count_selector)
        if not selector_ok:
            # Pode ser legitimo (carta sem vendedor) — quem chamou decide.
            logger.debug("Seletor %r nao apareceu em %s", wait_selector, url)
        return page.content()

    def _scroll_until_stable(self, count_selector: str):
        """Rola ate o fim repetidamente ate a contagem de elementos parar de
        crescer por SCROLL_STABLE_ROUNDS rodadas (padrao do infinite-scroll)."""
        page = self.page
        prev = -1
        stable = 0
        for _ in range(SCROLL_MAX_ROUNDS):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                break
            time.sleep(SCROLL_PAUSE_S)
            try:
                cur = page.locator(count_selector).count()
            except Exception:
                break
            if cur == prev:
                stable += 1
                if stable >= SCROLL_STABLE_ROUNDS:
                    break
            else:
                stable = 0
            prev = cur


# ──────────────────────────────────────────────────────────────────────────
# Checkpoint (retomar scan interrompido)
# ──────────────────────────────────────────────────────────────────────────

class ScanState:
    """Estado do scan em data/liga_live_state.json.

    Estrutura: {"sets": {"PRE": {"cards": {url: {"status": ..., "offer": {...}}}}}}
    status: "ok" | "sem_oferta_en_nm" | "abaixo_piso" | "falha"
    """

    def __init__(self, path: Path = DEFAULT_STATE_PATH, resume: bool = False):
        self.path = Path(path)
        self.data: dict = {"version": 1, "created": datetime.now().isoformat(), "sets": {}}
        if resume and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                logger.info("Checkpoint carregado de %s (resume).", self.path)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Checkpoint ilegivel (%s); comecando do zero.", exc)

    def cards(self, ed_code: str) -> dict:
        return self.data["sets"].setdefault(ed_code, {"cards": {}})["cards"]

    def is_done(self, ed_code: str, url: str) -> bool:
        return url in self.cards(ed_code)

    def mark(self, ed_code: str, url: str, status: str, offer: LigaOffer | None = None):
        entry: dict = {"status": status, "ts": datetime.now().isoformat()}
        if offer is not None:
            entry["offer"] = {
                "card_name": offer.card_name,
                "set_name": offer.set_name,
                "price_brl": offer.price_brl,
                "url": offer.url,
                "condition": offer.condition,
                "seller": offer.seller,
                "card_number": offer.card_number,
            }
        self.cards(ed_code)[url] = entry
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def offers(self) -> list[LigaOffer]:
        out: list[LigaOffer] = []
        for set_entry in self.data["sets"].values():
            for entry in set_entry["cards"].values():
                o = entry.get("offer")
                if o:
                    out.append(LigaOffer(**o))
        return out


# ──────────────────────────────────────────────────────────────────────────
# Orquestracao
# ──────────────────────────────────────────────────────────────────────────

def resolve_sets(specs: list[str]) -> dict[str, str]:
    """['PRE', 'XYZ=Custom Set'] -> {'PRE': 'Prismatic Evolutions', 'XYZ': 'Custom Set'}."""
    out: dict[str, str] = {}
    for spec in specs:
        spec = spec.strip()
        if not spec:
            continue
        if "=" in spec:
            code, _, name = spec.partition("=")
            out[code.strip().upper()] = name.strip()
            continue
        code = spec.upper()
        if code not in ED_SETS:
            known = ", ".join(sorted(ED_SETS))
            raise ValueError(
                f"Set {code!r} desconhecido. Conhecidos: {known}. "
                f"Para outro set use o formato CODIGO=Nome Em Ingles "
                f"(ex.: --sets \"{code}=Nome Do Set\")."
            )
        out[code] = ED_SETS[code]
    return out


def _listing_url(ed_code: str) -> str:
    return f"{LIGA_BASE}/?view=cards/search&card=ed={ed_code}"


def collect_live(
    sets: dict[str, str],
    min_price: float = 50.0,
    max_cards_per_set: int | None = None,
    headless: bool = False,
    resume: bool = False,
    state_path: Path = DEFAULT_STATE_PATH,
    profile_dir: Path | None = None,
    recycle_every: int = RECYCLE_EVERY,
    delay_between_cards_s: float = 1.0,
) -> list[LigaOffer]:
    """Coleta ao vivo: para cada set, lista as cartas e extrai a melhor
    oferta EN+NM de cada uma. Devolve a lista de LigaOffer (1 por carta).

    ``sets`` e um dict codigo->nome EN (ver ``resolve_sets``).
    """
    state = ScanState(state_path, resume=resume)
    session = _ChromeSession(profile_dir=profile_dir, headless=headless)
    pages_fetched = 0

    try:
        for ed_code, set_name in sets.items():
            logger.info("=== Set %s (%s) — listando cartas (infinite scroll)...", ed_code, set_name)
            listing_html = session.fetch(
                _listing_url(ed_code),
                wait_selector='a[href*="view=cards/card"]',
                scroll_count_selector="div.card-item",
            )
            pages_fetched += 1
            cards = parse_listing_cards(listing_html, ed_code)
            if not cards:
                evidence = session._save_debug(f"listing_vazia_{ed_code}")
                raise LigaDomChangedError(
                    f"Listagem do set {ed_code} carregou mas nenhuma carta foi "
                    f"encontrada (DOM mudou?). Evidencia: {evidence}"
                )
            if max_cards_per_set:
                cards = cards[:max_cards_per_set]
            logger.info("Set %s: %d cartas na listagem.", ed_code, len(cards))

            skipped_floor = 0
            for i, card in enumerate(cards, 1):
                if state.is_done(ed_code, card.url):
                    continue
                # Pre-filtro do piso: se NEM o vendedor mais caro chega a
                # R$50, nenhuma oferta pode passar — pula sem visitar.
                if card.max_brl is not None and card.max_brl < min_price:
                    state.mark(ed_code, card.url, "abaixo_piso")
                    skipped_floor += 1
                    continue

                offer = None
                status = "falha"
                for attempt in (1, 2):
                    try:
                        if pages_fetched and pages_fetched % recycle_every == 0:
                            session.recycle()
                        session.fetch(
                            card.url,
                            wait_selector="div.store",
                            scroll_count_selector="div.store",
                        )
                        pages_fetched += 1
                        # Filtro 'Ingles' OBRIGATORIO: surfa as ofertas EN
                        # (AJAX) que o load inicial nao traz.
                        session.apply_en_filter()
                        session._scroll_until_stable("div.store")
                        card_html = session.page.content()
                        # Linhas AJAX usam preco anti-scraping → decoder.
                        class_map: dict[str, str] = {}
                        if "price-with-image" in card_html:
                            class_map = build_class_digit_map(
                                card_html, session.fetch_binary
                            )
                        seller_offers = parse_seller_offers(card_html, class_map)
                        best = pick_buy_offer(seller_offers)
                        if best is None:
                            undecoded = [
                                o for o in seller_offers
                                if o.is_en and o.is_nm and o.price_brl is None
                            ]
                            if undecoded:
                                status = "preco_nao_decodificado"
                                logger.warning(
                                    "[%d/%d] %s (#%s): %d oferta(s) EN+NM com preco "
                                    "NAO decodificado (sprite) — carta pulada, preco "
                                    "nao inventado.",
                                    i, len(cards), card.name, card.number, len(undecoded),
                                )
                            else:
                                status = "sem_oferta_en_nm"
                                logger.info(
                                    "[%d/%d] %s (#%s): %d vendedores, nenhum EN+NM elegivel.",
                                    i, len(cards), card.name, card.number, len(seller_offers),
                                )
                        else:
                            offer = LigaOffer(
                                card_name=card.name,
                                set_name=set_name,
                                price_brl=best.price_brl,
                                url=card.url,
                                condition="NM",
                                seller=best.seller,
                                card_number=card.number,
                            )
                            status = "ok"
                            logger.info(
                                "[%d/%d] %s (#%s): EN+NM R$ %.2f (%s)",
                                i, len(cards), card.name, card.number,
                                best.price_brl, best.seller or "loja?",
                            )
                        break
                    except LigaBlockedError:
                        raise  # bloqueio e fatal e honesto — nao mascarar
                    except Exception as exc:
                        logger.warning(
                            "[%d/%d] %s: tentativa %d falhou (%s: %s)%s",
                            i, len(cards), card.name, attempt,
                            type(exc).__name__, exc,
                            " — reciclando e tentando de novo" if attempt == 1 else "",
                        )
                        if attempt == 1:
                            session.recycle()
                state.mark(ed_code, card.url, status, offer)
                if delay_between_cards_s:
                    time.sleep(delay_between_cards_s)

            if skipped_floor:
                logger.info(
                    "Set %s: %d cartas puladas pelo pre-filtro do piso "
                    "(maior vendedor < R$ %.0f).", ed_code, skipped_floor, min_price,
                )
    finally:
        session.close()

    offers = state.offers()
    logger.info("Coleta concluida: %d ofertas EN+NM no total.", len(offers))
    return offers


def write_offers_csv(offers: list[LigaOffer], path: Path = DEFAULT_CSV_PATH) -> Path:
    """Escreve o CSV no formato que o pipeline (e o scanner integrado) le."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            ["card_name", "set_name", "price_brl", "url", "condition", "seller", "card_number"]
        )
        for o in offers:
            writer.writerow(
                [o.card_name, o.set_name, f"{o.price_brl:.2f}", o.url,
                 o.condition, o.seller, o.card_number]
            )
    return path
