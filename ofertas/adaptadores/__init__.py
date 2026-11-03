from .base import Adaptador, Bloqueado
from .clubes import CityClub, SamsMX
from .soriana import Soriana
from .vtex import HEB, Chedraui
from .walmart import BodegaAurrera, WalmartMX

TIENDAS: dict[str, type[Adaptador]] = {
    c.clave: c for c in (WalmartMX, BodegaAurrera, HEB, Chedraui, Soriana, SamsMX, CityClub)
}

__all__ = ["TIENDAS", "Adaptador", "Bloqueado"]
