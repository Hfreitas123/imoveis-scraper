"""Dataset persistente dos anúncios que correspondem aos critérios.

Faz três coisas de uma vez:
  1. Deduplicação de notificações (não notificar o mesmo anúncio duas vezes).
  2. Histórico de tudo o que já apareceu dentro do raio, com `first_seen` /
     `last_seen` — para poderes ver o que saiu de mercado.
  3. Fonte de dados do dashboard web (`docs/listings.json`).

Persiste entre execuções via commit automático no GitHub Actions.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Listing

# Campos do Listing a guardar em cada registo (ordem estável no JSON).
_FIELDS = (
    "site", "site_id", "titulo", "tipologia", "preco", "url",
    "rua", "freguesia", "concelho", "area_m2", "imagem",
    "lat", "lon", "dist_km", "tempo_min", "geo_preciso",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Dataset:
    def __init__(self, path: Path, meta: dict, dias_historico: int = 30):
        self.path = path
        self.meta = meta
        self.dias_historico = dias_historico
        self.records: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {r["uid"]: r for r in data.get("listings", [])}
        except (json.JSONDecodeError, OSError, KeyError):
            return {}

    def contains(self, uid: str) -> bool:
        """True se já foi notificado (para não repetir a notificação)."""
        return self.records.get(uid, {}).get("notified", False)

    def upsert(self, lst: Listing, notified: bool) -> None:
        """Cria ou atualiza o registo de um anúncio dentro do raio."""
        d = asdict(lst)
        rec = {k: d.get(k) for k in _FIELDS}
        rec["uid"] = lst.uid
        existing = self.records.get(lst.uid)
        if existing:
            rec["first_seen"] = existing.get("first_seen", _now())
            rec["notified"] = existing.get("notified", False) or notified
        else:
            rec["first_seen"] = _now()
            rec["notified"] = notified
        rec["last_seen"] = _now()
        self.records[lst.uid] = rec

    def _prune(self) -> None:
        limite = datetime.now(timezone.utc) - timedelta(days=self.dias_historico)
        for uid in list(self.records):
            ls = self.records[uid].get("last_seen", "")
            try:
                if datetime.fromisoformat(ls) < limite:
                    del self.records[uid]
            except ValueError:
                pass

    def save(self) -> None:
        self._prune()
        self.meta["generated_at"] = _now()
        self.meta["total"] = len(self.records)
        # mais recentes primeiro (por first_seen)
        listings = sorted(
            self.records.values(),
            key=lambda r: r.get("first_seen", ""),
            reverse=True,
        )
        payload = {"meta": self.meta, "listings": listings}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
