"""Registo de scrapers disponíveis, selecionáveis via config `scraping.sites`."""
from __future__ import annotations

from ..config import Config
from .base import BaseScraper
from .casasapo import CasaSapoScraper
from .idealista import IdealistaScraper
from .imovirtual import ImovirtualScraper
from .olx import OlxScraper

_REGISTRY: dict[str, type[BaseScraper]] = {
    ImovirtualScraper.name: ImovirtualScraper,
    CasaSapoScraper.name: CasaSapoScraper,
    OlxScraper.name: OlxScraper,
    IdealistaScraper.name: IdealistaScraper,
}


def build_scrapers(cfg: Config) -> list[BaseScraper]:
    scrapers: list[BaseScraper] = []
    for site in cfg.sites:
        cls = _REGISTRY.get(site)
        if cls is None:
            print(f"  ! site desconhecido na config: {site!r} (ignorado)")
            continue
        scrapers.append(cls(cfg))
    return scrapers
