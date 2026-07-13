"""Scraper do Idealista — via API OFICIAL (não faz scraping do site).

O site idealista.pt está protegido por DataDome e devolve HTTP 403 a qualquer
pedido automatizado. NÃO contornamos anti-bot. Em alternativa, usamos a
Search API oficial do Idealista (https://developers.idealista.com), que:

  - é gratuita mediante aprovação (formulário em developers.idealista.com/access-request);
  - usa OAuth2 client-credentials (apikey + secret -> token);
  - suporta pesquisa por raio a partir de um ponto central (center + distance),
    exatamente o nosso modelo — e devolve coordenadas de cada anúncio.

Credenciais: variáveis de ambiente IDEALISTA_APIKEY e IDEALISTA_SECRET
(no GitHub: Settings -> Secrets -> Actions). Sem credenciais, o scraper
salta de forma limpa e explica como as obter.

QUOTA: o plano gratuito é limitado (na ordem de ~100 pedidos/mês). Correr de
hora a hora (720+/mês) estouraria a quota, por isso este scraper tem cadência
própria: só chama a API se a última chamada tiver sido há mais de
`idealista_horas_entre` horas (config; por omissão 8h ≈ 90 pesquisas/mês).
O timestamp persiste em `idealista_state.json` (commit automático no Actions).
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

from ..config import ROOT
from ..models import Listing
from .base import BaseScraper

OAUTH_URL = "https://api.idealista.com/oauth/token"
SEARCH_URL = "https://api.idealista.com/3.5/pt/search"
STATE_PATH = ROOT / "idealista_state.json"

AJUDA = (
    "credenciais em falta — pede acesso gratuito em "
    "https://developers.idealista.com/access-request e define os secrets "
    "IDEALISTA_APIKEY / IDEALISTA_SECRET (ver README, secção Idealista)."
)


class IdealistaScraper(BaseScraper):
    name = "idealista"

    # ---- cadência (gestão de quota) ----
    def _horas_entre(self) -> float:
        return float(self.cfg.raw["scraping"].get("idealista_horas_entre", 8))

    def _pode_correr(self) -> bool:
        if not STATE_PATH.exists():
            return True
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            ultima = datetime.fromisoformat(state["ultima_chamada"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return True
        return datetime.now(timezone.utc) - ultima >= timedelta(hours=self._horas_entre())

    def _registar_chamada(self) -> None:
        STATE_PATH.write_text(
            json.dumps(
                {"ultima_chamada": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                indent=1,
            ),
            encoding="utf-8",
        )

    # ---- OAuth ----
    def _token(self, apikey: str, secret: str) -> str | None:
        cred = base64.b64encode(f"{apikey}:{secret}".encode()).decode()
        resp = self.session.post(
            OAUTH_URL,
            headers={"Authorization": f"Basic {cred}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "read"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ! idealista: OAuth falhou (HTTP {resp.status_code}) — "
                  "verifica IDEALISTA_APIKEY/IDEALISTA_SECRET")
            return None
        return resp.json().get("access_token")

    # ---- pesquisa ----
    def _raio_metros(self) -> int:
        # raio em linha reta equivalente ao tempo a pé configurado
        km = self.cfg.velocidade_kmh * (self.cfg.raio_minutos / 60.0) / max(self.cfg.fator_desvio, 0.01)
        return int(km * 1000)

    def _search(self, token: str) -> list[dict]:
        lat, lon = self.cfg.centro_latlon
        if lat is None or lon is None:
            print("  ! idealista: config sem lat/lon do centro — define-os no config.yaml")
            return []
        # nº de quartos (no Idealista, rooms = nº do T): T1 -> 1, T2 -> 2
        rooms = sorted(int(t[1:]) for t in self.cfg.tipologias if t[1:].isdigit())
        params = {
            "operation": "rent",
            "propertyType": "homes",
            "center": f"{lat},{lon}",
            "distance": str(self._raio_metros()),
            "maxPrice": str(self.cfg.preco_maximo),
            "maxItems": "50",
            "numPage": "1",
            "order": "publicationDate",
            "sort": "desc",
        }
        if rooms:
            params["minRooms"] = str(rooms[0])
            params["maxRooms"] = str(rooms[-1])
        resp = self.session.post(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data=params,
            timeout=30,
        )
        self._registar_chamada()  # a pesquisa consome quota — registar sempre
        if resp.status_code == 429:
            print("  ! idealista: quota da API excedida (HTTP 429) — "
                  "aumenta idealista_horas_entre no config.yaml")
            return []
        if resp.status_code != 200:
            print(f"  ! idealista: pesquisa falhou (HTTP {resp.status_code}): "
                  f"{resp.text[:150]}")
            return []
        return resp.json().get("elementList", [])

    def _to_listing(self, it: dict) -> Listing | None:
        rooms = it.get("rooms")
        tip = f"T{rooms}" if rooms is not None else None
        if tip not in self.cfg.tipologias:
            return None
        preco = it.get("price")
        show_addr = bool(it.get("showAddress"))
        lst = Listing(
            site=self.name,
            site_id=str(it.get("propertyCode")),
            titulo=it.get("suggestedTexts", {}).get("title")
                   or f"{tip} — {it.get('address', '')}".strip(" —"),
            tipologia=tip,
            preco=int(preco) if preco is not None else None,
            url=it.get("url") or f"https://www.idealista.pt/imovel/{it.get('propertyCode')}/",
            rua=it.get("address") if show_addr else None,
            freguesia=it.get("district") or it.get("neighborhood"),
            concelho=it.get("municipality") or "Porto",
            area_m2=int(it["size"]) if it.get("size") else None,
            imagem=it.get("thumbnail"),
        )
        # a API devolve sempre coordenadas; exatas quando showAddress=True
        if it.get("latitude") is not None and it.get("longitude") is not None:
            lst.lat = float(it["latitude"])
            lst.lon = float(it["longitude"])
            lst.geo_preciso = show_addr
        return lst

    def fetch(self) -> list[Listing]:
        apikey = os.environ.get("IDEALISTA_APIKEY")
        secret = os.environ.get("IDEALISTA_SECRET")
        if not apikey or not secret:
            print(f"  (ignorado) idealista: {AJUDA}")
            return []
        if not self._pode_correr():
            print(f"  idealista: última chamada há menos de {self._horas_entre():g}h — "
                  "a saltar esta execução (gestão de quota da API)")
            return []
        token = self._token(apikey, secret)
        if not token:
            return []
        items = self._search(token)
        listings = []
        for it in items:
            lst = self._to_listing(it)
            if lst is not None:
                listings.append(lst)
        return listings
