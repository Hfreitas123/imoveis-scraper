"""Orquestrador: corre os scrapers, filtra por distância, deduplica e notifica.

Fluxo por execução:
  1. Cada scraper devolve anúncios (já filtrados por preço/tipologia no servidor).
  2. Geocodifica os que não trazem coordenadas (Nominatim, com cache) e calcula
     o tempo a pé até ao ponto central.
  3. Guarda no dataset (docs/listings.json) os que estão dentro do raio e, se
     ainda não tinham sido notificados, envia notificação ntfy.
  4. Grava dataset + cache de geocodificação (persistem entre execuções).
"""
from __future__ import annotations

import argparse
import sys

from . import config, notifier
from .geo import Geocoder, haversine_km, tempo_caminhada_min
from .models import Listing
from .scrapers.registry import build_scrapers
from .store import Dataset


def _resolver_centro(cfg: config.Config, geocoder: Geocoder) -> tuple[float, float]:
    lat, lon = cfg.centro_latlon
    if lat is not None and lon is not None:
        return lat, lon
    print(f"A geocodificar o ponto central: {cfg.morada_central}")
    res = geocoder.geocode(cfg.morada_central)
    if res is None:
        sys.exit("ERRO: não foi possível geocodificar a morada central. "
                 "Define lat/lon no config.yaml.")
    return res


def _avaliar_distancia(lst: Listing, centro, geocoder, cfg) -> bool:
    """Garante coordenadas (usa as do anúncio ou geocodifica) e calcula
    distância/tempo a pé. Devolve True se estiver dentro do raio."""
    if lst.lat is None or lst.lon is None:
        for query, preciso in lst.geocode_queries():
            res = geocoder.geocode(query)
            if res is not None:
                lst.lat, lst.lon = res
                lst.geo_preciso = preciso
                break
    if lst.lat is None or lst.lon is None:
        print(f"    · sem geocodificação para «{lst.zona()}» — ignorado por segurança")
        return False
    reta = haversine_km(centro[0], centro[1], lst.lat, lst.lon)
    lst.dist_km = reta * cfg.fator_desvio
    lst.tempo_min = tempo_caminhada_min(lst.dist_km, cfg.velocidade_kmh)
    return lst.tempo_min <= cfg.raio_minutos


def run(dry_run: bool = False) -> int:
    cfg = config.load()
    if not cfg.ntfy_topic and not dry_run:
        sys.exit("ERRO: variável de ambiente NTFY_TOPIC não definida.")
    if dry_run:
        print("== MODO DRY-RUN: não envia notificações nem grava estado ==")

    geocoder = Geocoder(cfg.geo_user_agent, cfg.geo_intervalo, cfg.geo_cache_path)
    centro = _resolver_centro(cfg, geocoder)
    # raio equivalente em linha reta (para desenhar o círculo no mapa)
    raio_reta_km = cfg.velocidade_kmh * (cfg.raio_minutos / 60.0) / max(cfg.fator_desvio, 0.01)
    meta = {
        "morada_central": cfg.morada_central,
        "centro": {"lat": centro[0], "lon": centro[1]},
        "raio_minutos": cfg.raio_minutos,
        "velocidade_kmh": cfg.velocidade_kmh,
        "fator_desvio": cfg.fator_desvio,
        "raio_reta_km": round(raio_reta_km, 3),
        "tipologias": cfg.tipologias,
        "preco_maximo": cfg.preco_maximo,
    }
    dataset = Dataset(cfg.dataset_path, meta, cfg.dias_historico)
    print(f"Ponto central: {centro[0]:.5f}, {centro[1]:.5f} | "
          f"raio: {cfg.raio_minutos} min a pé (~{cfg.velocidade_kmh} km/h)")

    novos_notificados = 0
    total_anuncios = 0

    for scraper in build_scrapers(cfg):
        print(f"\n=== {scraper.name} ===")
        try:
            anuncios = scraper.fetch()
        except NotImplementedError as e:
            print(f"  (ignorado) {e}")
            continue
        except Exception as e:  # um site a falhar não deve parar os outros
            print(f"  ! erro no scraper {scraper.name}: {e}")
            continue

        print(f"  {len(anuncios)} anúncios dentro dos filtros de preço/tipologia")
        total_anuncios += len(anuncios)

        vistos_nesta_run: set[str] = set()
        for lst in anuncios:
            if lst.uid in vistos_nesta_run:
                continue
            vistos_nesta_run.add(lst.uid)

            if not _avaliar_distancia(lst, centro, geocoder, cfg):
                continue  # fora do raio: não guarda nem notifica

            ja_notificado = dataset.contains(lst.uid)
            enviado = False
            if not ja_notificado:
                print(f"  ✅ NOVO: {lst.tipologia} {lst.preco}€ · {lst.zona()} · "
                      f"~{round(lst.tempo_min)} min a pé · {lst.url}")
                if not dry_run:
                    enviado = notifier.send(cfg.ntfy_topic, lst)
                    if enviado:
                        novos_notificados += 1
                else:
                    novos_notificados += 1  # conta mas não marca como notificado
            dataset.upsert(lst, notified=enviado or ja_notificado)

    geocoder.save_cache()
    dataset.save()  # o dataset é sempre gravado (é a fonte do dashboard)
    print(f"\nConcluído: {novos_notificados} novo(s) notificado(s) · "
          f"{len(dataset.records)} no dataset · de {total_anuncios} avaliados.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scraper de imóveis com alertas ntfy.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Corre e grava o dataset, mas não envia notificações ntfy.")
    args = ap.parse_args()
    raise SystemExit(run(dry_run=args.dry_run))
