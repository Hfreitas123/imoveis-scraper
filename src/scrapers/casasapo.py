"""Scraper do Casa Sapo.

Ao contrário do Imovirtual/OLX, o Casa Sapo não expõe um JSON global limpo, por
isso fazemos parsing do HTML com BeautifulSoup. Os SELETORES estão todos
reunidos no topo (`SEL`) para serem fáceis de atualizar se o site mudar — ver
README, secção "Se um site mudar de estrutura".

Filtragem no servidor:
- caminho `mais-recentes` -> ordena por mais recente
- parâmetro `gp` -> preço máximo
A tipologia (T1/T2) é filtrada do lado do cliente a partir do `data-title` do
card (o Casa Sapo codifica a tipologia num bitmask pouco prático de usar no URL).
A localização é geocodificada via Nominatim (o Casa Sapo não fornece coordenadas).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

BASE = "https://casa.sapo.pt"
# {gp} = preço máximo, {pn} = página
SEARCH_URL = BASE + "/alugar-apartamentos/mais-recentes/porto/?gp={gp}&pn={pn}"

# ---- SELETORES (ajustar aqui se o site mudar) ----
SEL = {
    "card": "div.property",
    "data_title": "[data-title]",     # atributo data-title = "Apartamento T2"
    "price": ".property-price-value",  # "1.200 €"
    "location": ".property-location",  # "Rua X, Freguesia, Porto, Distrito do Porto"
    "features": ".property-features-text",  # "Usado · 65m²"
    "image": "picture.property-photos img",
}
# O link de detalhe pode ser relativo (/alugar-...html) ou absoluto, e por vezes
# vem embrulhado num redirect de contagem (...&l=<url real>).
DETALHE_RE = re.compile(r"(?:https://casa\.sapo\.pt)?/(?:alugar|arrendar)[^\"'&\s]+\.html")


def _extrair_link(card) -> str | None:
    for a in card.find_all("a", href=True):
        m = DETALHE_RE.search(a["href"])
        if m:
            url = m.group(0)
            return url if url.startswith("http") else BASE + url
    return None


class CasaSapoScraper(BaseScraper):
    name = "casasapo"

    def _build_url(self, page: int) -> str:
        return SEARCH_URL.format(gp=self.cfg.preco_maximo, pn=page)

    def _to_listing(self, card) -> Listing | None:
        # tipologia a partir do data-title ("Apartamento T2")
        el = card.select_one(SEL["data_title"])
        dtitle = el.get("data-title") if el else ""
        m = re.search(r"T\d+", dtitle or "")
        tip = m.group(0) if m else None
        if tip not in self.cfg.tipologias:
            return None

        preco = _parse_preco(_txt(card.select_one(SEL["price"])))
        location = _txt(card.select_one(SEL["location"]))
        rua, freguesia, concelho = _split_local(location)

        url = _extrair_link(card) or BASE
        uid = (card.get("id") or "").replace("property_", "") or url

        img_el = card.select_one(SEL["image"])
        img = img_el.get("src") if img_el else None

        return Listing(
            site=self.name,
            site_id=uid,
            titulo=(dtitle or "Apartamento") + (f" · {location}" if location else ""),
            tipologia=tip,
            preco=preco,
            url=url,
            rua=rua,
            freguesia=freguesia,
            concelho=concelho,
            area_m2=_parse_area(_txt(card.select_one(SEL["features"]))),
            imagem=img,
        )

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        for page in range(1, self.cfg.paginas_max + 1):
            resp = self._get(self._build_url(page))
            if resp.status_code != 200:
                print(f"  ! casasapo: HTTP {resp.status_code} na página {page}")
                break
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(SEL["card"])
            if not cards:
                print("  ! casasapo: nenhum card encontrado (seletor mudou?)")
                break
            antes = len(listings)
            for card in cards:
                lst = self._to_listing(card)
                if lst is not None:
                    listings.append(lst)
            if len(listings) == antes and page > 1:
                break  # página sem novos T1/T2 -> parar
        return listings


def _txt(el) -> str | None:
    return el.get_text(strip=True) if el else None


def _parse_preco(s: str | None) -> int | None:
    if not s:
        return None
    d = re.sub(r"[^\d]", "", s.split("€")[0])
    return int(d) if d else None


def _parse_area(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"(\d+)\s*m", s)
    return int(m.group(1)) if m else None


def _split_local(location: str | None) -> tuple[str | None, str | None, str | None]:
    """Divide "Rua X, Freguesia, Porto, Distrito do Porto" em (rua, freguesia, concelho)."""
    if not location:
        return None, None, None
    partes = [p.strip() for p in location.split(",") if "Distrito" not in p]
    if not partes:
        return None, None, None
    concelho = partes[-1] if len(partes) >= 2 else "Porto"
    if len(partes) >= 3:
        return partes[0], partes[-2], concelho
    if len(partes) == 2:
        return None, partes[0], concelho
    return None, partes[0], "Porto"
