"""Testes do coletor ao vivo da Liga (parsers puros, sem navegador).

As fixtures em tests/fixtures/ vem de paginas REAIS da Liga (salvas em
sessoes de diagnostico ao vivo), com algumas copias modificadas para
cobrir casos que nao estavam na pagina original (EN+SP, combo de idioma,
leilao, carta bulk abaixo do piso).
"""
from pathlib import Path

import pytest

from src.collectors.liga_live import (
    CF_COOLDOWN_BASE_S,
    ED_SETS,
    ListingCard,
    ScanState,
    SellerOffer,
    _cf_cooldown_seconds,
    _listing_url,
    parse_brl,
    parse_editions,
    parse_listing_cards,
    parse_seller_offers,
    pick_buy_offer,
    resolve_sets,
    write_offers_csv,
)
from src.collectors.liga_pokemon import LigaOffer, fetch_offers

FIXTURES = Path(__file__).parent / "fixtures"
CARD_PAGE = (FIXTURES / "liga_card_page.html").read_text(encoding="utf-8")
LISTING = (FIXTURES / "liga_listing.html").read_text(encoding="utf-8")


class TestParseBrl:
    def test_preco_com_milhar(self):
        assert parse_brl("R$ 1.089,90") == pytest.approx(1089.90)

    def test_preco_simples(self):
        assert parse_brl("R$ 52,00") == pytest.approx(52.0)

    def test_nbsp_e_espacos(self):
        assert parse_brl("R$\xa0 3.999,90 ") == pytest.approx(3999.90)

    def test_invalido_vira_none(self):
        assert parse_brl("a combinar") is None
        assert parse_brl("") is None
        assert parse_brl(None) is None

    def test_zero_e_negativo_viram_none(self):
        assert parse_brl("R$ 0,00") is None


class TestParseEditions:
    # A pagina de edicoes lista, por edicao, um link com o edid numerico +
    # o codigo ed (ex.: card=edid=391%20ed=PAL). A Liga passou a EXIGIR o
    # edid na URL de listagem (2026-06) — sem ele, cai na home sem cartas.
    EDICOES = (
        '<a href="https://www.ligapokemon.com.br/?view=cards/search&amp;card=edid=391%20ed=PAL">Paldea Evolved</a>'
        '<a href="/?view=cards/search&card=edid=649%20ed=PRE">Prismatic Evolutions</a>'
        '<a href="/?view=cards/search&card=edid=773%20ed=CRI">Chaos Rising</a>'
        '<a href="/?view=cards/search&card=edid=102 ed=GRI">Guardians Rising</a>'
    )

    def test_extrai_code_para_edid(self):
        m = parse_editions(self.EDICOES)
        assert m["PAL"] == "391"
        assert m["PRE"] == "649"
        assert m["CRI"] == "773"

    def test_tolera_espaco_literal(self):
        # href com espaco literal em vez de %20 tambem resolve.
        assert parse_editions(self.EDICOES)["GRI"] == "102"

    def test_chave_case_insensitive_normalizada_para_upper(self):
        m = parse_editions('<a href="/?view=cards/search&card=edid=6%20ed=flf">Flashfire</a>')
        assert m["FLF"] == "6"

    def test_html_sem_edicoes(self):
        assert parse_editions("<html><body>nada</body></html>") == {}


class TestListingUrl:
    def test_url_inclui_edid(self):
        url = _listing_url("391", "PAL")
        assert "edid=391" in url
        assert "ed=PAL" in url
        assert url.startswith("https://www.ligapokemon.com.br/?view=cards/search")

    def test_edid_e_ed_separados_por_espaco_encodado(self):
        # A Liga espera edid e ed no MESMO parametro card=, separados por espaco.
        assert "edid=391%20ed=PAL" in _listing_url("391", "PAL")


class TestCfCooldown:
    # Bloqueio de CF em sessao longa NAO aborta o scan: recicla + cooldown
    # escalonado e re-tenta a carta; so aborta apos muitas cartas seguidas.
    def test_escalona_linearmente(self):
        base = CF_COOLDOWN_BASE_S
        assert _cf_cooldown_seconds(1) == base
        assert _cf_cooldown_seconds(2) == 2 * base
        assert _cf_cooldown_seconds(3) == 3 * base

    def test_piso_minimo_uma_base(self):
        # cf_hits 0/negativo nunca zera o cooldown.
        assert _cf_cooldown_seconds(0) == CF_COOLDOWN_BASE_S
        assert _cf_cooldown_seconds(-5) == CF_COOLDOWN_BASE_S

    def test_base_customizada(self):
        assert _cf_cooldown_seconds(2, base=10) == 20


class TestParseListing:
    def test_extrai_cartas_da_listagem_real(self):
        cards = parse_listing_cards(LISTING, "PRE")
        assert len(cards) == 3
        names = [c.name for c in cards]
        assert "Umbreon ex" in names
        assert "Sylveon ex" in names

    def test_numero_e_url(self):
        cards = parse_listing_cards(LISTING, "PRE")
        sylveon = next(c for c in cards if c.name == "Sylveon ex")
        assert sylveon.number == "156"
        assert sylveon.url.startswith("https://www.ligapokemon.com.br/")
        assert "num=156" in sylveon.url
        assert sylveon.ed_code == "PRE"

    def test_faixa_de_preco(self):
        cards = parse_listing_cards(LISTING, "PRE")
        sylveon = next(c for c in cards if c.name == "Sylveon ex")
        assert sylveon.min_brl == pytest.approx(1099.90)
        assert sylveon.max_brl == pytest.approx(3999.90)

    def test_pre_filtro_do_piso_detectavel(self):
        # A carta bulk (max R$12,50) deve ser identificavel p/ pular.
        cards = parse_listing_cards(LISTING, "PRE")
        bulk = next(c for c in cards if c.name == "Leafeon ex")
        assert bulk.max_brl == pytest.approx(12.50)
        assert bulk.max_brl < 50.0

    def test_html_vazio(self):
        assert parse_listing_cards("<html></html>", "PRE") == []


class TestParseSellerOffers:
    def test_total_de_vendedores(self):
        offers = parse_seller_offers(CARD_PAGE)
        assert len(offers) == 8

    def test_nm_match_exato_na_celula_dedicada(self):
        """Invariante dura: NM via celula dedicada, match EXATO.
        SP NUNCA pode passar como NM (nem por substring)."""
        offers = parse_seller_offers(CARD_PAGE)
        sp = [o for o in offers if o.condition == "SP"]
        nm = [o for o in offers if o.is_nm]
        assert len(sp) == 2          # PT+SP real e EN+SP sintetica
        assert all(not o.is_nm for o in sp)
        assert all(o.condition == "NM" for o in nm)

    def test_idioma_estrito(self):
        offers = parse_seller_offers(CARD_PAGE)
        en = [o for o in offers if o.is_en]
        # combo "Portugues / Ingles" NAO conta como EN
        combos = [o for o in offers
                  if any("/" in t for t in o.languages)]
        assert combos and all(not o.is_en for o in combos)
        # as 4 EN: EN+SP e leilao-EN sinteticas, EN+NM real, EN+NM mais barata
        assert len(en) == 4

    def test_precos_parseados(self):
        offers = parse_seller_offers(CARD_PAGE)
        precos = sorted(o.price_brl for o in offers if o.price_brl)
        assert precos[0] == pytest.approx(900.00)     # leilao sintetico
        assert precos[-1] == pytest.approx(3149.90)   # EN+NM real

    def test_extras_capturados_mas_nao_excluem(self):
        # Em carta chase (SIR) TODOS os vendedores marcam Foil — e normal.
        offers = parse_seller_offers(CARD_PAGE)
        assert all("Foil" in o.extras for o in offers)

    def test_leilao_flagado(self):
        offers = parse_seller_offers(CARD_PAGE)
        auctions = [o for o in offers if o.auction]
        assert len(auctions) == 1
        assert auctions[0].price_brl == pytest.approx(900.00)

    def test_seller_id(self):
        offers = parse_seller_offers(CARD_PAGE)
        assert any(o.seller.startswith("loja#") for o in offers)


class TestPickBuyOffer:
    def test_escolhe_en_nm_mais_barata(self):
        offers = parse_seller_offers(CARD_PAGE)
        best = pick_buy_offer(offers)
        assert best is not None
        # PT R$1.170 e mais barata, mas nao e EN; EN+SP R$1.500 nao e NM;
        # leilao R$900 e leilao; combo R$1.000 nao e EN estrito.
        # Sobram EN+NM R$3.149,90 e R$2.999,90 -> a mais barata vence.
        assert best.price_brl == pytest.approx(2999.90)
        assert best.is_en and best.is_nm and not best.auction

    def test_sem_elegiveis(self):
        offers = [
            SellerOffer(price_brl=100.0, languages=["Português"], condition="NM"),
            SellerOffer(price_brl=90.0, languages=["Inglês"], condition="SP"),
            SellerOffer(price_brl=80.0, languages=["Inglês"], condition="NM",
                        auction=True),
            SellerOffer(price_brl=None, languages=["Inglês"], condition="NM"),
        ]
        assert pick_buy_offer(offers) is None


class TestResolveSets:
    def test_codigo_conhecido(self):
        assert resolve_sets(["PRE"]) == {"PRE": "Prismatic Evolutions"}

    def test_case_insensitive(self):
        assert resolve_sets(["pre"]) == {"PRE": "Prismatic Evolutions"}

    def test_codigo_desconhecido_erra_com_dica(self):
        with pytest.raises(ValueError, match="desconhecido"):
            resolve_sets(["ZZZ"])

    def test_override_manual(self):
        assert resolve_sets(["ZZZ=Meu Set"]) == {"ZZZ": "Meu Set"}

    def test_todos_os_codigos_tem_nome(self):
        assert all(name for name in ED_SETS.values())


class TestScanState:
    def test_roundtrip_checkpoint(self, tmp_path):
        path = tmp_path / "state.json"
        state = ScanState(path)
        offer = LigaOffer(
            card_name="Sylveon ex", set_name="Prismatic Evolutions",
            price_brl=2999.90, url="https://example/x", condition="NM",
            seller="loja#1", card_number="156",
        )
        state.mark("PRE", "https://example/x", "ok", offer)
        state.mark("PRE", "https://example/y", "abaixo_piso")

        resumed = ScanState(path, resume=True)
        assert resumed.is_done("PRE", "https://example/x")
        assert resumed.is_done("PRE", "https://example/y")
        assert not resumed.is_done("PRE", "https://example/z")
        offers = resumed.offers()
        assert len(offers) == 1
        assert offers[0].card_number == "156"
        assert offers[0].price_brl == pytest.approx(2999.90)

    def test_sem_resume_comeca_do_zero(self, tmp_path):
        path = tmp_path / "state.json"
        ScanState(path).mark("PRE", "u", "ok")
        fresh = ScanState(path)  # resume=False
        assert not fresh.is_done("PRE", "u")


class TestCsvRoundtrip:
    def test_csv_compativel_com_pipeline(self, tmp_path):
        """O CSV do coletor deve ser lido pelo fetch_offers(source='csv')
        — e o que o scanner integrado consome."""
        csv_path = tmp_path / "liga_offers.csv"
        offers = [
            LigaOffer("Sylveon ex", "Prismatic Evolutions", 2999.90,
                      "https://example/x", "NM", "loja#1", "156"),
            LigaOffer("Umbreon ex", "Prismatic Evolutions", 4500.00,
                      "https://example/y", "NM", "", "161"),
        ]
        write_offers_csv(offers, csv_path)
        loaded = fetch_offers(source="csv", csv_path=csv_path)
        assert len(loaded) == 2
        assert loaded[0].card_name == "Sylveon ex"
        assert loaded[0].card_number == "156"
        assert loaded[0].condition == "NM"
        assert loaded[1].price_brl == pytest.approx(4500.00)


class TestLiveModeViaEnv:
    def test_live_sem_sets_erra_claro(self, monkeypatch):
        monkeypatch.delenv("LIGA_SETS", raising=False)
        with pytest.raises(ValueError, match="LIGA_SETS"):
            fetch_offers(source="live")

    def test_http_stub_aponta_para_live(self):
        with pytest.raises(NotImplementedError, match="live"):
            fetch_offers(source="http")


class TestSpriteDecoder:
    """Preco anti-scraping (linhas AJAX): fixture REAL da Ceruledge ex
    (147/131) PRE + sprite JPG real. Ground truth conferido visualmente
    em screenshot ao vivo (2026-06-10): R$ 469,75."""

    @pytest.fixture()
    def sprite_page(self):
        return (FIXTURES / "liga_card_page_sprite.html").read_text(encoding="utf-8")

    @pytest.fixture()
    def sprite_bytes(self):
        return (FIXTURES / "liga_digit_sprite.jpg").read_bytes()

    def test_build_class_digit_map(self, sprite_page, sprite_bytes):
        from src.collectors.liga_live import build_class_digit_map
        cmap = build_class_digit_map(sprite_page, lambda url: sprite_bytes)
        digits = set(cmap.values()) - {"?"}
        # o sprite real cobre os 10 digitos
        assert digits == set("0123456789")

    def test_decodifica_preco_real(self, sprite_page, sprite_bytes):
        from src.collectors.liga_live import build_class_digit_map
        cmap = build_class_digit_map(sprite_page, lambda url: sprite_bytes)
        offers = parse_seller_offers(sprite_page, cmap)
        en_nm = [o for o in offers if o.is_en and o.is_nm]
        assert len(en_nm) == 1
        assert en_nm[0].price_brl == pytest.approx(469.75)

    def test_sem_mapa_vira_none_nunca_inventa(self, sprite_page):
        offers = parse_seller_offers(sprite_page)  # sem class_digit_map
        en_nm = [o for o in offers if o.is_en and o.is_nm]
        assert len(en_nm) == 1
        assert en_nm[0].price_brl is None

    def test_pagina_sem_sprite_devolve_mapa_vazio(self):
        from src.collectors.liga_live import build_class_digit_map
        called = []
        cmap = build_class_digit_map("<html></html>", lambda url: called.append(url))
        assert cmap == {}
        assert called == []


class TestDecodePriceDiv:
    """Logica de reconstrucao do preco a partir dos tokens (sem imagem)."""

    def _div(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser").select_one("div.new-price")

    SEP = ('<div style="background-image:url(\'//x/v2.png\');"> </div>')

    def test_preco_simples(self):
        from src.collectors.liga_live import decode_price_div
        div = self._div(
            '<div class="new-price"><div class="imgnum-monet">R$</div>'
            '<div class="aaaaa"> </div><div class="bbbbb"> </div>'
            f'{self.SEP}'
            '<div class="ccccc"> </div><div class="ddddd"> </div></div>'
        )
        cmap = {"aaaaa": "4", "bbbbb": "2", "ccccc": "5", "ddddd": "0"}
        assert decode_price_div(div, cmap) == pytest.approx(42.50)

    def test_preco_com_milhar(self):
        from src.collectors.liga_live import decode_price_div
        # 1.299,90 — separador de milhar E decimal com a mesma imagem
        div = self._div(
            '<div class="new-price"><div class="imgnum-monet">R$</div>'
            '<div class="aaaaa"> </div>'
            f'{self.SEP}'
            '<div class="bbbbb"> </div><div class="ccccc"> </div><div class="ddddd"> </div>'
            f'{self.SEP}'
            '<div class="eeeee"> </div><div class="fffff"> </div></div>'
        )
        cmap = {"aaaaa": "1", "bbbbb": "2", "ccccc": "9", "ddddd": "9",
                "eeeee": "9", "fffff": "0"}
        assert decode_price_div(div, cmap) == pytest.approx(1299.90)

    def test_digito_nao_decodificado_vira_none(self):
        from src.collectors.liga_live import decode_price_div
        div = self._div(
            '<div class="new-price"><div class="aaaaa"> </div>'
            '<div class="zzzzz"> </div></div>'
        )
        cmap = {"aaaaa": "4", "zzzzz": "?"}
        assert decode_price_div(div, cmap) is None
