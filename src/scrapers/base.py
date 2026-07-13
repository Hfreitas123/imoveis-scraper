"""Classe base para todos os scrapers de sites."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from ..config import Config
from ..models import Listing

# Mapa tipologia (T0, T1, ...) <-> nº de "quartos" no modelo do Imovirtual/OLX,
# onde a contagem inclui a sala. Ex.: T1 = 1 quarto + sala = "TWO".
TIP_TO_ROOMS = {
    "T0": "ONE",
    "T1": "TWO",
    "T2": "THREE",
    "T3": "FOUR",
    "T4": "FIVE",
    "T5": "SIX",
}
ROOMS_TO_TIP = {v: k for k, v in TIP_TO_ROOMS.items()}


class BaseScraper(ABC):
    #: nome curto do site (usado no uid e na config)
    name: str = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": cfg.scrape_user_agent})

    def _get(self, url: str, **kwargs) -> requests.Response:
        """GET com pausa educada entre pedidos."""
        resp = self.session.get(url, timeout=30, **kwargs)
        time.sleep(self.cfg.pausa_pedidos)
        return resp

    @abstractmethod
    def fetch(self) -> list[Listing]:
        """Devolve a lista de anúncios (já filtrados por preço/tipologia no servidor
        quando possível). A filtragem por distância é feita a jusante."""
        raise NotImplementedError
