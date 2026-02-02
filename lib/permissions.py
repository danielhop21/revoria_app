from __future__ import annotations
from dataclasses import dataclass

ROLE_ADMIN = "admin"
ROLE_COTIZADOR = "cotizador"
ROLE_VENDEDOR = "vendedor"

ALL_ROLES = {ROLE_ADMIN, ROLE_COTIZADOR, ROLE_VENDEDOR}


@dataclass(frozen=True)
class Permissions:
    # Lectura de info sensible
    can_view_costs: bool          # costos base, costo papel, costo click, etc.
    can_view_margin: bool         # margen %, utilidad $ (si lo manejas)
    can_view_breakdown: bool      # desglose técnico (aunque no sea $)

    # Exportaciones
    can_export_tech: bool         # Excel técnico / PDF técnico
    can_export_client: bool       # PDF cliente (normalmente sí para todos)

    # Administración
    can_access_settings: bool     # página Configuración
    can_manage_users: bool        # si luego haces UI de usuarios


def normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    # compat: si antes usabas "sales"
    if r == "sales":
        r = ROLE_VENDEDOR
    if r not in ALL_ROLES:
        # default seguro
        r = ROLE_VENDEDOR
    return r


def permissions_for(role: str) -> Permissions:
    r = normalize_role(role)

    if r == ROLE_ADMIN:
        return Permissions(
            can_view_costs=True,
            can_view_margin=True,
            can_view_breakdown=True,
            can_export_tech=True,
            can_export_client=True,
            can_access_settings=True,
            can_manage_users=True,
        )

    if r == ROLE_COTIZADOR:
        return Permissions(
            can_view_costs=True,
            can_view_margin=True,
            can_view_breakdown=True,
            can_export_tech=True,
            can_export_client=True,
            can_access_settings=False,   # Config solo admin (por ahora)
            can_manage_users=False,
        )

    # vendedor (default)
    return Permissions(
        can_view_costs=False,
        can_view_margin=False,
        can_view_breakdown=False,   # si quieres que vea desglose NO-$, lo cambiamos luego
        can_export_tech=False,
        can_export_client=True,
        can_access_settings=False,
        can_manage_users=False,
    )
