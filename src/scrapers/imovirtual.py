"""Scraper do Imovirtual.

Estratégia: o Imovirtual é um site Next.js que embute TODOS os dados dos
anúncios num bloco JSON `<script id="__NEXT_DATA__">`. Lemos esse JSON em vez
de fazer parsing de HTML — é muito mais robusto e não quebra quando mudam o
layout visual. Ver README, secção "Se um site mudar de estrutura".

A filtragem por preço e tipologia é feita no próprio servidor via parâmetros do
URL (`priceMax`, `roomsNumber`), ordenando por mais recente (`by=LATEST`).
"""
from __future__ import annotations

import json
import re

from ..models import Listing
from .base import ROOMS_TO_TIP, TIP_TO_ROOMS, BaseScraper

BASE = "https://www.imovirtual.com"
# Resultados de arrendamento de apartamentos no concelho do Porto.
SEARCH_PATH = "/pt/resultados/arrendar/apartamento/porto/porto"

# ---- ÂNCORAS DE PARSING (ajustar aqui se o site mudar) ----
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)


class ImovirtualScraper(BaseScraper):
    name = "imovirtual"

    def _build_url(self, page: int) -> str:
        rooms = [TIP_TO_ROOMS[t] for t in self.cfg.tipologias if t in TIP_TO_ROOMS]
        rooms_param = "[" + ",".join(rooms) + "]"
        params = [
            "limit=36",
            f"priceMax={self.cfg.preco_maximo}",
            f"roomsNumber={rooms_param}",
            "by=LATEST",
            "direction=DESC",
            f"page={page}",
        ]
        return f"{BASE}{SEARCH_PATH}?" + "&".join(params)

    def _parse_next_data(self, html: str) -> list[dict]:
        m = NEXT_DATA_RE.search(html)
        if not m:
            print("  ! imovirtual: bloco __NEXT_DATA__ não encontrado (site mudou?)")
            return []
        try:
            data = json.loads(m.group(1))
            return data["props"]["pageProps"]["data"]["searchAds"]["items"]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ! imovirtual: estrutura JSON inesperada ({e})")
            return []

    def _to_listing(self, it: dict) -> Listing | None:
        rooms = it.get("roomsNumber")
        tip = ROOMS_TO_TIP.get(rooms)
        if tip is None or tip not in self.cfg.tipologias:
            return None

        preco = None
        tp = it.get("totalPrice") or {}
        if isinstance(tp, dict) and tp.get("value") is not None:
            preco = int(tp["value"])

        addr = (it.get("location") or {}).get("address") or {}
        rua = addr.get("street")
        rua = rua.get("name") if isinstance(rua, dict) else rua
        freguesia = (addr.get("city") or {}).get("name")
        concelho = (addr.get("province") or {}).get("name")

        # href vem como "[lang]/ad/...-IDxxxx"; normalizar para URL absoluto.
        href = it.get("href") or ""
        href = href.replace("[lang]", "pt").lstrip("/")
        url = f"{BASE}/{href}"

        area = it.get("areaInSquareMeters")

        img = None
        imgs = it.get("images") or []
        if imgs and isinstance(imgs[0], dict):
            img = imgs[0].get("medium") or imgs[0].get("large")

        return Listing(
            site=self.name,
            site_id=str(it["id"]),
            titulo=it.get("title", "").strip(),
            tipologia=tip,
            preco=preco,
            url=url,
            rua=rua,
            freguesia=freguesia,
            concelho=concelho,
            area_m2=int(area) if area else None,
            imagem=img,
        )

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        for page in range(1, self.cfg.paginas_max + 1):
            url = self._build_url(page)
            resp = self._get(url)
            if resp.status_code != 200:
                print(f"  ! imovirtual: HTTP {resp.status_code} na página {page}")
                break
            items = self._parse_next_data(resp.text)
            if not items:
                break
            for it in items:
                lst = self._to_listing(it)
                if lst is not None:
                    listings.append(lst)
        return listings
