"""Envio de notificações via ntfy.sh."""
from __future__ import annotations

import requests

from .models import Listing

NTFY_BASE = "https://ntfy.sh"


def _emoji_tipologia(tip: str) -> str:
    return {"T0": "🏠", "T1": "🏠", "T2": "🏡", "T3": "🏘️"}.get(tip.upper(), "🏠")


def send(topic: str, listing: Listing) -> bool:
    """Envia uma notificação para o tópico ntfy. Devolve True em sucesso."""
    preco = f"{listing.preco}€/mês" if listing.preco is not None else "preço n/d"
    dist = (
        f"{listing.dist_km:.1f} km · ~{round(listing.tempo_min)} min a pé"
        if listing.dist_km is not None
        else "distância n/d"
    )
    precisao = "" if listing.geo_preciso else " (aprox.)"

    titulo = f"{_emoji_tipologia(listing.tipologia)} {listing.tipologia} · {preco} · {listing.site}"
    corpo = (
        f"{listing.titulo}\n"
        f"📍 {listing.zona()}\n"
        f"🚶 {dist}{precisao}\n"
        f"🔗 {listing.url}"
    )

    headers = {
        "Title": titulo.encode("utf-8"),
        "Tags": "house",
        "Priority": "high",
        "Click": listing.url,          # tocar na notificação abre o anúncio
    }
    try:
        resp = requests.post(
            f"{NTFY_BASE}/{topic}",
            data=corpo.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        return resp.status_code < 300
    except requests.RequestException as e:
        print(f"  ! falha ao notificar via ntfy: {e}")
        return False
