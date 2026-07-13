"""Scraper do OLX Portugal.

Como o Imovirtual, o OLX embute os dados numa variável JavaScript
(`window.__PRERENDERED_STATE__`, uma cache Apollo/GraphQL) em vez de os expor só
em HTML. Lemos essa variável — robusto a mudanças de layout.

Vantagem do OLX: cada anúncio já traz **coordenadas** (`map.lat/lon`), pelo que
NÃO é preciso geocodificar. O campo `map.show_detailed` indica se a localização
é exata (o vendedor marcou o ponto) ou apenas aproximada (zona).

Filtragem no servidor via caminho de categoria + parâmetros de URL:
  /imoveis/apartamento-casa-a-venda/apartamentos-arrenda/porto/
  ?search[filter_enum_tipologia][N]=t1|t2
  &search[filter_float_price:to]=<preco_max>
  &search[order]=created_at:desc
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from ..models import Listing
from .base import BaseScraper

BASE = "https://www.olx.pt"
# Caminho da categoria "Apartamentos → Arrenda-se", no distrito do Porto.
SEARCH_PATH = "/imoveis/apartamento-casa-a-venda/apartamentos-arrenda/porto/"

# ---- ÂNCORA DE PARSING (ajustar aqui se o site mudar) ----
STATE_RE = re.compile(
    r'window\.__PRERENDERED_STATE__\s*=\s*("(?:[^"\\]|\\.)*");', re.S
)


class OlxScraper(BaseScraper):
    name = "olx"

    def _build_url(self, page: int) -> str:
        # tipologias: T1 -> t1, T2 -> t2 (o OLX usa minúsculas)
        params = []
        for i, tip in enumerate(self.cfg.tipologias):
            params.append(f"search[filter_enum_tipologia][{i}]={tip.lower()}")
        params.append(f"search[filter_float_price:to]={self.cfg.preco_maximo}")
        params.append("search[order]=created_at:desc")
        if page > 1:
            params.append(f"page={page}")
        qs = "&".join(quote(p, safe="=") for p in params)
        return f"{BASE}{SEARCH_PATH}?{qs}"

    def _parse_state(self, html: str) -> list[dict]:
        m = STATE_RE.search(html)
        if not m:
            print("  ! olx: __PRERENDERED_STATE__ não encontrado (site mudou?)")
            return []
        try:
            data = json.loads(json.loads(m.group(1)))  # string escapada -> string -> objeto
            return data["listing"]["listing"]["ads"]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ! olx: estrutura JSON inesperada ({e})")
            return []

    def _to_listing(self, it: dict) -> Listing | None:
        if not it.get("isActive", True):
            return None
        params = {p.get("key"): p.get("value") for p in it.get("params", [])}
        tip = (params.get("tipologia") or "").upper()  # já vem "T1"/"T2"
        if tip not in self.cfg.tipologias:
            return None

        preco = None
        reg = ((it.get("price") or {}).get("regularPrice") or {})
        if reg.get("value") is not None:
            preco = int(reg["value"])

        loc = it.get("location") or {}
        mp = it.get("map") or {}
        photos = it.get("photos") or []
        img = photos[0] if photos and isinstance(photos[0], str) else None

        lst = Listing(
            site=self.name,
            site_id=str(it["id"]),
            titulo=(it.get("title") or "").strip(),
            tipologia=tip,
            preco=preco,
            url=it.get("url") or "",
            rua=None,
            freguesia=loc.get("cityName"),
            concelho=loc.get("regionName"),
            area_m2=_area(params),
            imagem=img,
        )
        # coordenadas já fornecidas -> dispensa geocodificação
        if mp.get("lat") is not None and mp.get("lon") is not None:
            lst.lat = float(mp["lat"])
            lst.lon = float(mp["lon"])
            lst.geo_preciso = bool(mp.get("show_detailed"))
        return lst

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        for page in range(1, self.cfg.paginas_max + 1):
            resp = self._get(self._build_url(page))
            if resp.status_code != 200:
                print(f"  ! olx: HTTP {resp.status_code} na página {page}")
                break
            ads = self._parse_state(resp.text)
            if not ads:
                break
            for it in ads:
                lst = self._to_listing(it)
                if lst is not None:
                    listings.append(lst)
        return listings


def _area(params: dict) -> int | None:
    for k in ("area_util_m2", "area_util", "area_m2", "area_bruta"):
        v = params.get(k)
        if v:
            m = re.search(r"\d+", str(v))
            if m:
                return int(m.group())
    return None
