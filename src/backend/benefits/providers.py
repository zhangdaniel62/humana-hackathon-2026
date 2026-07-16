"""Provider suggestions. Pure; no ADK, no network, no distance.

Two data facts drive this file:

* Gastroenterology and Oncology have ZERO in-network providers accepting new
  patients, so a colonoscopy question -- a flagship demo path -- returns nothing
  under naive filtering. The fallback is the member's PCP, which is also the
  clinically correct answer: a colonoscopy needs a PCP referral anyway.

* lat/lon do not agree with city/state and the median nearest eligible provider
  is 217 miles away. Ranking or quoting mileage off that signal is false
  precision, so this module computes no distances at all.
"""

from .aliases import CPT_SPECIALTY
from .kb import CsvBenefitsKB
from .loader import load_members, load_providers
from .models import (
    Member,
    Provider,
    ProviderMatch,
    ProviderResult,
    Resolution,
    display_name,
)

_LIMIT = 3


def _match(p: Provider, *, is_pcp: bool = False) -> ProviderMatch:
    return ProviderMatch(
        provider_id=p.provider_id,
        name=p.name,
        specialty=p.specialty,
        city=p.city,
        state=p.state,
        phone=p.phone,
        is_pcp=is_pcp,
    )


def _rank(providers: list[Provider], member: Member) -> list[Provider]:
    """Same state, then same city, then provider_id. Deterministic, no geo math."""
    return sorted(
        providers,
        key=lambda p: (
            p.state != member.state,
            p.city != member.city,
            p.provider_id,
        ),
    )


def _eligible(specialty: str) -> list[Provider]:
    return [
        p
        for p in load_providers().values()
        if p.specialty == specialty and p.in_network and p.accepting_new_patients
    ]


def _in_network(specialty: str) -> list[Provider]:
    return [p for p in load_providers().values() if p.specialty == specialty and p.in_network]


def _availability(specialty: str) -> str:
    if _eligible(specialty):
        return "available"
    if _in_network(specialty):
        return "none_accepting_new_patients"
    return "not_in_network_directory"


def _pcp_result(
    member: Member,
    specialty_requested: str | None,
    availability: str,
) -> ProviderResult:
    """Terminal fallback. Cannot be empty: all 200 members have an in-network PCP."""
    pcp = load_providers()[member.pcp_id]
    pcp_name = display_name(pcp.name)

    if specialty_requested is None:
        note = f"Your PCP, {pcp_name}, orders this for you - no specialist referral needed."
    elif availability == "none_accepting_new_patients":
        note = (
            f"No in-network {specialty_requested} providers are currently accepting "
            f"new patients. Your PCP, {pcp_name}, can refer you - which is the "
            f"required first step for this service regardless."
        )
    else:
        note = (
            f"There are no in-network {specialty_requested} providers in the "
            f"directory. Start with your PCP, {pcp_name}, for a referral."
        )

    return ProviderResult(
        providers=[_match(pcp, is_pcp=True)],
        basis="pcp_referral",
        specialty_requested=specialty_requested,
        specialty_availability=availability,
        note=note,
    )


def find_provider(service_or_specialty: str, member_id: str, limit: int = _LIMIT) -> ProviderResult:
    """Suggest providers for a service. Never returns an empty list.

    Walks the CPT's ordered specialty preference: same-state eligible, then
    any-state eligible, then the next specialty, then the member's PCP.
    """
    member = load_members()[member_id]

    specialties = _specialties_for(service_or_specialty)
    if not specialties:
        return _pcp_result(member, None, "available")

    primary = specialties[0]
    for index, specialty in enumerate(specialties):
        pool = _eligible(specialty)
        if not pool:
            continue

        ranked = _rank(pool, member)[:limit]
        in_state = [p for p in ranked if p.state == member.state]
        if index > 0:
            basis = "secondary_specialty"
        elif in_state:
            basis = "specialty_in_state"
        else:
            basis = "specialty_any"

        note = f"In-network {specialty} providers accepting new patients."
        if index > 0:
            note = (
                f"No in-network {primary} providers are accepting new patients; "
                f"these {specialty} providers can help."
            )

        return ProviderResult(
            providers=[_match(p) for p in ranked],
            basis=basis,
            specialty_requested=primary,
            specialty_availability="available",
            note=note,
        )

    return _pcp_result(member, primary, _availability(primary))


def _specialties_for(service_or_specialty: str) -> tuple[str, ...]:
    """Accept a CPT code, a free-text service, or a specialty name."""
    known = {p.specialty for p in load_providers().values()}
    for s in known:
        if s.lower() == service_or_specialty.strip().lower():
            return (s,)

    resolved = CsvBenefitsKB().resolve(service_or_specialty)
    if resolved.resolution is Resolution.RESOLVED:
        return CPT_SPECIALTY[resolved.candidates[0]]
    if resolved.resolution is Resolution.AMBIGUOUS:
        # Union the candidates' specialties, preserving preference order.
        ordered: list[str] = []
        for code in resolved.candidates:
            for s in CPT_SPECIALTY[code]:
                if s not in ordered:
                    ordered.append(s)
        return tuple(ordered)
    return ()
