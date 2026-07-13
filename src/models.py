"""Modelo de dados partilhado por todos os scrapers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Listing:
    """Um anúncio normalizado, independente do site de origem."""

    site: str            # "imovirtual", "olx", ...
    site_id: str         # id único dentro do site
    titulo: str
    tipologia: str       # "T1", "T2", ...
    preco: int | None    # €/mês
    url: str

    # localização (o que o anúncio fornece)
    rua: str | None = None
    freguesia: str | None = None
    concelho: str | None = None
    area_m2: int | None = None
    imagem: str | None = None   # URL da 1ª foto (para o dashboard)

    # preenchido depois da geocodificação / cálculo de distância
    lat: float | None = None
    lon: float | None = None
    dist_km: float | None = None      # distância estimada por ruas
    tempo_min: float | None = None    # tempo a pé estimado
    geo_preciso: bool = False         # True se geocodificado ao nível da rua

    @property
    def uid(self) -> str:
        """Chave global de deduplicação."""
        return f"{self.site}:{self.site_id}"

    def zona(self) -> str:
        """Descrição legível da zona para a notificação."""
        partes = [p for p in (self.rua, self.freguesia, self.concelho) if p]
        return ", ".join(partes) if partes else "zona desconhecida"

    def geocode_queries(self) -> list[tuple[str, bool]]:
        """Cadeia de queries para o Nominatim, da mais específica para a menos.

        Cada item é (query, preciso), onde `preciso=True` indica geocodificação
        ao nível da rua. Tentar múltiplas variantes recupera muitos casos em que
        a freguesia é uma união de freguesias que o Nominatim não reconhece.
        """
        rua = (self.rua or "").split(",")[0].strip() or None  # limpa lixo após vírgula
        conc = self.concelho or "Porto"
        queries: list[tuple[str, bool]] = []
        if rua and self.freguesia:
            queries.append((f"{rua}, {self.freguesia}, {conc}, Portugal", True))
        if rua:
            queries.append((f"{rua}, {conc}, Portugal", True))
        if self.freguesia:
            queries.append((f"{self.freguesia}, {conc}, Portugal", False))
        queries.append((f"{conc}, Portugal", False))
        # remover duplicados preservando ordem
        vistos, out = set(), []
        for q, p in queries:
            if q not in vistos:
                vistos.add(q)
                out.append((q, p))
        return out
