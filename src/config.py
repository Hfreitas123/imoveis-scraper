"""Carregamento da configuração (config.yaml) e do tópico ntfy (ambiente)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Diretório raiz do projeto (um nível acima de src/).
ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    raw: dict
    ntfy_topic: str | None

    # ---- localização ----
    @property
    def morada_central(self) -> str:
        return self.raw["localizacao"]["morada_central"]

    @property
    def centro_latlon(self) -> tuple[float | None, float | None]:
        loc = self.raw["localizacao"]
        return loc.get("lat"), loc.get("lon")

    # ---- filtros ----
    @property
    def tipologias(self) -> list[str]:
        return [str(t).upper() for t in self.raw["filtros"]["tipologias"]]

    @property
    def preco_maximo(self) -> int:
        return int(self.raw["filtros"]["preco_maximo"])

    @property
    def raio_minutos(self) -> float:
        return float(self.raw["filtros"]["raio_minutos"])

    @property
    def velocidade_kmh(self) -> float:
        return float(self.raw["filtros"]["velocidade_kmh"])

    @property
    def fator_desvio(self) -> float:
        return float(self.raw["filtros"].get("fator_desvio", 1.0))

    # ---- geocoding ----
    @property
    def geo_user_agent(self) -> str:
        return self.raw["geocoding"]["user_agent"]

    @property
    def geo_intervalo(self) -> float:
        return float(self.raw["geocoding"].get("intervalo_seg", 1.1))

    @property
    def geo_cache_path(self) -> Path:
        return ROOT / self.raw["geocoding"].get("cache_ficheiro", "geocode_cache.json")

    # ---- scraping ----
    @property
    def sites(self) -> list[str]:
        return [str(s).lower() for s in self.raw["scraping"]["sites"]]

    @property
    def pausa_pedidos(self) -> float:
        return float(self.raw["scraping"].get("pausa_entre_pedidos_seg", 2.0))

    @property
    def paginas_max(self) -> int:
        return int(self.raw["scraping"].get("paginas_max", 1))

    @property
    def scrape_user_agent(self) -> str:
        return self.raw["scraping"]["user_agent"]

    # ---- dataset / dashboard ----
    @property
    def dataset_path(self) -> Path:
        return ROOT / self.raw["dataset"].get("ficheiro", "docs/listings.json")

    @property
    def dias_historico(self) -> int:
        return int(self.raw["dataset"].get("dias_historico", 30))


def load(path: str | Path | None = None) -> Config:
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    topic = os.environ.get("NTFY_TOPIC")
    return Config(raw=raw, ntfy_topic=topic)
