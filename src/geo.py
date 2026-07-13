"""Geocodificação (Nominatim/OpenStreetMap) e cálculo de distância a pé.

- Respeita o limite de 1 pedido/segundo do Nominatim.
- Mantém uma cache em disco para não repetir pedidos entre execuções.
- Distância em linha reta via haversine, convertida em distância "real" por
  ruas através de um fator de desvio configurável.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class Geocoder:
    def __init__(self, user_agent: str, intervalo_seg: float, cache_path: Path):
        self.user_agent = user_agent
        self.intervalo = intervalo_seg
        self.cache_path = cache_path
        self.cache: dict[str, list[float] | None] = self._load_cache()
        self._ultimo_pedido = 0.0

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save_cache(self) -> None:
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def geocode(self, query: str) -> tuple[float, float] | None:
        """Devolve (lat, lon) para uma query, ou None se não encontrar."""
        if query in self.cache:
            v = self.cache[query]
            return (v[0], v[1]) if v else None

        # respeitar 1 pedido/segundo
        espera = self.intervalo - (time.monotonic() - self._ultimo_pedido)
        if espera > 0:
            time.sleep(espera)

        params = {
            "format": "json",
            "limit": 1,
            "countrycodes": "pt",
            "q": query,
        }
        result = None
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params=params,
                headers={"User-Agent": self.user_agent},
                timeout=20,
            )
            self._ultimo_pedido = time.monotonic()
            if resp.status_code == 200 and resp.json():
                d = resp.json()[0]
                result = (float(d["lat"]), float(d["lon"]))
        except (requests.RequestException, ValueError, KeyError):
            result = None

        self.cache[query] = list(result) if result else None
        return result


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta (grande círculo) entre dois pontos, em km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tempo_caminhada_min(dist_km: float, velocidade_kmh: float) -> float:
    """Tempo a pé em minutos para uma dada distância."""
    if velocidade_kmh <= 0:
        return float("inf")
    return dist_km / velocidade_kmh * 60.0
