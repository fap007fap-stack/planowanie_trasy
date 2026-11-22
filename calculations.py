from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil


@dataclass(frozen=True)
class Cargo:
    name: str
    mass_t: float
    length_m: float
    width_m: float
    height_m: float
    category: str = "Transformator / urządzenie energetyczne"
    divisible: bool = False
    adr: bool = False
    center_of_gravity: str = "Średni"
    fragile: bool = False


@dataclass(frozen=True)
class VehiclePlan:
    tractor: str
    trailer: str
    trailer_axles: int
    total_axles: int
    total_length_m: float
    total_width_m: float
    total_height_m: float
    gross_mass_t: float
    tractor_load_t: float
    trailer_load_t: float
    axle_loads_t: list[float]
    permit_category: str
    pilots: int
    notes: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def select_vehicle(cargo: Cargo) -> VehiclePlan:
    """Create a transparent preliminary vehicle configuration.

    The result is deliberately conservative and must be confirmed with the
    carrier, trailer manufacturer and road authorities before a real journey.
    """
    if cargo.mass_t <= 12:
        tractor, tractor_tare, trailer_tare, trailer_axles = (
            "Ciągnik siodłowy 4x2",
            8.0,
            8.0,
            3,
        )
        deck_height = 0.90
    elif cargo.mass_t <= 35:
        tractor, tractor_tare, trailer_tare, trailer_axles = (
            "Ciągnik balastowy 6x4",
            11.5,
            12.0,
            4,
        )
        deck_height = 0.85
    elif cargo.mass_t <= 60:
        tractor, tractor_tare, trailer_tare, trailer_axles = (
            "Ciągnik balastowy 8x4",
            14.0,
            18.0,
            6,
        )
        deck_height = 0.75
    else:
        tractor, tractor_tare, trailer_tare, trailer_axles = (
            "Ciągnik balastowy 8x4 z modułem napędowym",
            15.5,
            22.0,
            max(8, ceil(cargo.mass_t / 9.0)),
        )
        deck_height = 0.65

    if "8x4" in tractor:
        tractor_axles = 4
    elif "6x4" in tractor:
        tractor_axles = 3
    else:
        tractor_axles = 2

    category = cargo.category.lower()
    trailer_kind = "Naczepa niskopodwoziowa/modułowa"
    if "maszyna" in category:
        trailer_kind = "Naczepa niskopodwoziowa z najazdami i poszerzeniami"
        deck_height = max(deck_height, 0.75)
    elif "długi" in category or "łopata" in category:
        trailer_kind = "Naczepa teleskopowa z osiami skrętnymi"
        deck_height = max(deck_height, 0.90)
    elif "zbiornik" in category or "silos" in category:
        trailer_kind = "Naczepa zagłębiona/teleskopowa do ładunków cylindrycznych"
        deck_height = min(deck_height, 0.65)
    elif "łódź" in category or "przestrzenna" in category:
        trailer_kind = "Naczepa hydrauliczna z indywidualną kołyską transportową"
        deck_height = min(deck_height, 0.70)
    elif "transformator" in category or "energetyczne" in category:
        trailer_kind = "Naczepa modułowa niskopodwoziowa"
        if cargo.mass_t > 90:
            trailer_kind = "Moduły osiowe z mostem nośnym do transformatora"
    elif "drobnic" in category or "neutral" in category:
        trailer_kind = "Naczepa platformowa lub teleskopowa"
    gross = cargo.mass_t + tractor_tare + trailer_tare
    fifth_wheel_share = min(0.24, max(0.16, 0.20 + (cargo.length_m - 9.0) * 0.005))
    transferred = (cargo.mass_t + trailer_tare) * fifth_wheel_share
    tractor_load = tractor_tare + transferred
    trailer_load = gross - tractor_load

    if tractor_axles == 4:
        front = min(9.0, tractor_load * 0.30)
        tractor_remaining = tractor_load - front
        tractor_axle_loads = [front] + [tractor_remaining / 3] * 3
    else:
        front = min(8.5, tractor_load * 0.34)
        tractor_remaining = tractor_load - front
        tractor_axle_loads = [front] + [tractor_remaining / 2] * 2

    trailer_axle_load = trailer_load / trailer_axles
    axle_loads = [round(value, 2) for value in tractor_axle_loads]
    axle_loads += [round(trailer_axle_load, 2)] * trailer_axles

    length_allowance = 8.5 if "teleskopowa" in trailer_kind.lower() else 11.5
    total_length = max(16.5, cargo.length_m + length_allowance)
    total_width = max(2.55, cargo.width_m)
    total_height = deck_height + cargo.height_m

    # A configuration above the envelopes available in categories I-IV
    # requires an individually routed category V permit. This calculator is
    # an early screening, not an administrative decision.
    if gross > 60 or total_height > 4.30 or total_width > 4.00:
        permit = "V (ocena wstępna)"
    elif total_width > 3.40 or total_height > 4.00 or total_length > 23.0:
        permit = "IV lub V - zależnie od drogi i nacisków osi"
    else:
        permit = "II-IV - wymaga sprawdzenia tabeli kategorii"

    if (
        total_length > 30.0
        or total_width > 3.60
        or total_height > 4.70
        or gross > 80.0
    ):
        pilots = 2
    elif (
        total_length > 23.0
        or total_width > 3.20
        or total_height > 4.50
        or gross > 60.0
    ):
        pilots = 1
    else:
        pilots = 0

    notes = [
        f"Przyjęto masę własną ciągnika {tractor_tare:.1f} t i naczepy {trailer_tare:.1f} t.",
        f"Wysokość pokładu przyjęto jako {deck_height:.2f} m.",
        f"Na siodło przypisano {fifth_wheel_share * 100:.0f}% masy naczepy z ładunkiem.",
        "Rozkład osi jest szacunkiem statycznym; ostateczne wartości muszą pochodzić z dokumentacji zestawu i ważenia.",
    ]
    if cargo.center_of_gravity == "Wysoki":
        notes.append("Wysoki środek ciężkości: wymagane ograniczenie prędkości, analiza stateczności poprzecznej i trasy bez gwałtownych przechyłów.")
    if cargo.fragile:
        notes.append("Ładunek delikatny: wymagane limity przyspieszeń, rejestrator wstrząsów i kontrola drgań.")
    if cargo.adr:
        notes.append("Ładunek oznaczony jako ADR: dobór pojazdu, kierowcy, wyposażenia i trasy musi przejść osobną kontrolę zgodności ADR.")
    if cargo.divisible:
        notes.append("Ładunek oznaczony jako podzielny: przed wnioskiem trzeba wykazać podstawę przewozu w takiej postaci; zezwolenie nienormatywne co do zasady dotyczy ładunku niepodzielnego.")

    return VehiclePlan(
        tractor=tractor,
        trailer=f"{trailer_kind}, {trailer_axles} osi",
        trailer_axles=trailer_axles,
        total_axles=tractor_axles + trailer_axles,
        total_length_m=round(total_length, 2),
        total_width_m=round(total_width, 2),
        total_height_m=round(total_height, 2),
        gross_mass_t=round(gross, 2),
        tractor_load_t=round(tractor_load, 2),
        trailer_load_t=round(trailer_load, 2),
        axle_loads_t=axle_loads,
        permit_category=permit,
        pilots=pilots,
        notes=notes,
    )


def score_route(
    distance_km: float,
    duration_h: float,
    critical_points: int,
    live_incidents: int,
    motorway_share: float,
) -> float:
    """Lower score is better. The weights are visible in the UI."""
    return round(
        distance_km * 0.22
        + duration_h * 12.0
        + critical_points * 6.0
        + live_incidents * 8.0
        - motorway_share * 18.0,
        1,
    )


def securing_plan(cargo: Cargo) -> list[str]:
    minimum_force_kn = cargo.mass_t * 9.81 * 0.8
    plan = [
        f"Projekt mocowania na siłę wzdłużną co najmniej {minimum_force_kn:.0f} kN (wartość do obliczeń inżynierskich).",
        "Podparcie na belkach rozkładających nacisk, kliny i maty antypoślizgowe dobrane do podstawy transformatora.",
        "Łańcuchy napinające w układzie symetrycznym; liczba i LC z dokumentacji producenta, potwierdzone obliczeniem EN 12195-1.",
        "Kontrola napięcia po pierwszych 20-30 km oraz po każdym postoju i gwałtownym hamowaniu.",
        "Zabezpieczenie izolatorów i osprzętu przed drganiami, opadami oraz kontaktem z elementami mocującymi.",
    ]
    category = cargo.category.lower()
    if "maszyna" in category:
        plan[-1] = "Osprzęt maszyny opuścić i zablokować; przeguby, hamulec postojowy, koła lub gąsienice zabezpieczyć niezależnie."
    elif "długi" in category or "łopata" in category:
        plan[-1] = "Podpory dobrać w punktach producenta; kontrolować ugięcie, zwis tylny i pracę skrętnych osi naczepy."
    elif "zbiornik" in category or "silos" in category:
        plan[-1] = "Zastosować kołyski profilowane i zabezpieczenie przed obrotem; króćce nie mogą przenosić sił mocowania."
    elif "łódź" in category or "przestrzenna" in category:
        plan[-1] = "Kołyska transportowa musi przenosić obciążenia w punktach konstrukcyjnych wskazanych przez producenta."
    if cargo.center_of_gravity == "Wysoki":
        plan.append("Wykonać obliczenie stateczności poprzecznej oraz limitów prędkości na łukach i pochyleniach.")
    if cargo.adr:
        plan.append("Oddzielnie sprawdzić zgodność mocowania, oznakowania, dokumentów i wyposażenia z wymaganiami ADR dla wskazanego numeru UN.")
    return plan


def operational_plan(pilots: int, cargo: Cargo | None = None) -> dict[str, list[str] | str]:
    result = {
        "window": "22:00-05:00, po uzgodnieniu z organem i zarządcami dróg",
        "stops": [
            "Odprawa techniczna przed wyjazdem: dokumenty, światła, łączność i mocowanie.",
            "Postój kontrolny po 20-30 km, następnie co około 2 godziny w miejscu zatwierdzonym w planie.",
            "Zakaz spontanicznego postoju na pasie awaryjnym poza sytuacją zagrożenia.",
        ],
        "emergency": [
            "Pilot wstrzymuje przejazd przed przeszkodą i zabezpiecza miejsce.",
            "Dyspozytor kontaktuje zarządcę drogi i Policję; przejazd nie jest samodzielnie przekierowywany.",
            "Użycie objazdu wyłącznie po sprawdzeniu skrajni, nośności i zatwierdzeniu zmiany trasy zezwolenia.",
            "W razie awarii: zestaw w bezpieczne miejsce, oznakowanie, serwis ciężki i raport zdarzenia.",
        ],
        "pilots": f"Wstępnie {pilots} pojazd(y) pilotujący(e); wiążące są warunki zezwolenia.",
    }
    if cargo and cargo.adr:
        result["emergency"].append("Dla ADR uruchomić instrukcje pisemne, zachować wymagane odległości i powiadomić służby o numerze UN oraz rodzaju zagrożenia.")
    if cargo and cargo.fragile:
        result["stops"].append("Po każdym odcinku o gorszej nawierzchni sprawdzić rejestrator wstrząsów i punkty mocowania.")
    return result

