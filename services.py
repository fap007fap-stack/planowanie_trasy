from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any

import requests


USER_AGENT = "oversize-route-studio/1.0 (educational route planning)"
TIMEOUT = 18


@dataclass
class RouteResult:
    name: str
    color: str
    coordinates: list[list[float]]  # [lon, lat]
    distance_km: float
    duration_h: float
    via: list[str]
    motorway_share: float
    source: str
    warning: str | None = None


KNOWN_POINTS: dict[str, tuple[float, float]] = {
    "Gdańsk": (54.3520, 18.6466),
    "Pruszcz Gdański": (54.2622, 18.6363),
    "Tczew": (54.0924, 18.7779),
    "Grudziądz": (53.4837, 18.7536),
    "Świecie": (53.4094, 18.4474),
    "Toruń": (53.0138, 18.5984),
    "Włocławek": (52.6483, 19.0678),
    "Kutno": (52.2306, 19.3641),
    "Łęczyca": (52.0597, 19.1997),
    "Łódź": (51.7592, 19.4560),
}


def geocode(query: str) -> tuple[float, float, str]:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "pl"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"Nie znaleziono lokalizacji: {query}")
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]


def _osrm_route(points: list[tuple[float, float]], alternatives: bool = False) -> list[dict[str, Any]]:
    path = ";".join(f"{lon},{lat}" for lat, lon in points)
    response = requests.get(
        f"https://router.project-osrm.org/route/v1/driving/{path}",
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
            "alternatives": "true" if alternatives else "false",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Silnik trasowania nie zwrócił trasy.")
    return data["routes"]


def _known_corridors(origin: str, destination: str) -> bool:
    text = f"{origin} {destination}".lower()
    return "gdań" in text and ("łód" in text or "lodz" in text)


def get_routes(origin: str, destination: str) -> tuple[list[RouteResult], list[str]]:
    notes: list[str] = []
    try:
        start_lat, start_lon, start_label = geocode(origin)
        end_lat, end_lon, end_label = geocode(destination)
        notes.extend([f"Start: {start_label}", f"Cel: {end_label}"])

        if _known_corridors(origin, destination):
            north_to_south = "gdań" in origin.lower()
            a1_names = ["Grudziądz", "Toruń", "Kutno"]
            dk_names = ["Tczew", "Świecie", "Toruń", "Włocławek", "Łęczyca"]
            if not north_to_south:
                a1_names.reverse()
                dk_names.reverse()
            a1_via = [KNOWN_POINTS[x] for x in a1_names]
            dk_via = [KNOWN_POINTS[x] for x in dk_names]
            specs = [
                ("Korytarz A1", "#18c89b", a1_via, a1_names, 0.78),
                ("Korytarz DK91", "#ff9f43", dk_via, dk_names, 0.08),
            ]
            results: list[RouteResult] = []
            for name, color, vias, labels, motorway_share in specs:
                route = _osrm_route([(start_lat, start_lon), *vias, (end_lat, end_lon)])[0]
                results.append(
                    RouteResult(
                        name=name,
                        color=color,
                        coordinates=route["geometry"]["coordinates"],
                        distance_km=route["distance"] / 1000,
                        duration_h=route["duration"] / 3600,
                        via=labels,
                        motorway_share=motorway_share,
                        source="OSRM / OpenStreetMap, przebieg wymuszony punktami korytarza",
                        warning="Routing dla samochodu osobowego - nie uwzględnia skrajni ani nośności zestawu.",
                    )
                )
            return results, notes

        raw = _osrm_route([(start_lat, start_lon), (end_lat, end_lon)], alternatives=True)
        if len(raw) < 2:
            raw.append(raw[0])
        colors = ["#18c89b", "#ff9f43"]
        results = []
        for index, route in enumerate(raw[:2]):
            results.append(
                RouteResult(
                    name="Trasa rekomendowana" if index == 0 else "Trasa alternatywna",
                    color=colors[index],
                    coordinates=route["geometry"]["coordinates"],
                    distance_km=route["distance"] / 1000,
                    duration_h=route["duration"] / 3600,
                    via=[origin, destination],
                    motorway_share=0.45 if index == 0 else 0.25,
                    source="OSRM / OpenStreetMap",
                    warning="Routing dla samochodu osobowego - wymaga pełnego audytu dla pojazdu nienormatywnego.",
                )
            )
        return results, notes
    except Exception as exc:
        if not _known_corridors(origin, destination):
            raise
        notes.append(f"Tryb awaryjny danych: {exc}")
        return fallback_gdansk_lodz(), notes


def fallback_gdansk_lodz() -> list[RouteResult]:
    def coords(names: list[str]) -> list[list[float]]:
        return [[KNOWN_POINTS[name][1], KNOWN_POINTS[name][0]] for name in names]

    return [
        RouteResult(
            name="Korytarz A1",
            color="#18c89b",
            coordinates=coords(["Gdańsk", "Pruszcz Gdański", "Grudziądz", "Toruń", "Kutno", "Łódź"]),
            distance_km=338.0,
            duration_h=6.8,
            via=["Pruszcz Gdański", "Grudziądz", "Toruń", "Kutno", "Łódź"],
            motorway_share=0.78,
            source="Wbudowany scenariusz dydaktyczny",
            warning="Brak połączenia z routingiem. Linia i metryki są orientacyjne.",
        ),
        RouteResult(
            name="Korytarz DK91",
            color="#ff9f43",
            coordinates=coords(["Gdańsk", "Tczew", "Świecie", "Toruń", "Włocławek", "Łęczyca", "Łódź"]),
            distance_km=352.0,
            duration_h=8.2,
            via=["Tczew", "Świecie", "Toruń", "Włocławek", "Łęczyca", "Łódź"],
            motorway_share=0.08,
            source="Wbudowany scenariusz dydaktyczny",
            warning="Brak połączenia z routingiem. Linia i metryki są orientacyjne.",
        ),
    ]


def _route_bbox(route: RouteResult) -> tuple[float, float, float, float]:
    lons = [point[0] for point in route.coordinates]
    lats = [point[1] for point in route.coordinates]
    return min(lons), min(lats), max(lons), max(lats)


def get_tomtom_incidents(route: RouteResult, api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    min_lon, min_lat, max_lon, max_lat = _route_bbox(route)
    fields = "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description,code},startTime,endTime,from,to,length,delay,roadNumbers}}}"
    response = requests.get(
        "https://api.tomtom.com/traffic/services/5/incidentDetails",
        params={
            "key": api_key,
            "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "fields": fields,
            "language": "pl-PL",
            "timeValidityFilter": "present",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("incidents", [])


def get_weather(route: RouteResult) -> dict[str, Any]:
    middle = route.coordinates[len(route.coordinates) // 2]
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": middle[1],
            "longitude": middle[0],
            "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
            "timezone": "Europe/Warsaw",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    current = response.json().get("current", {})
    current["checked_at"] = datetime.now(timezone.utc).isoformat()
    return current


def haversine_km(a: list[float], b: list[float]) -> float:
    lon1, lat1 = map(radians, a)
    lon2, lat2 = map(radians, b)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(value), sqrt(1 - value))


def critical_points(route: RouteResult) -> list[dict[str, str]]:
    if "A1" in route.name:
        return [
            {"place": "Wyjazd z Gdańska / węzeł Rusocin", "type": "węzeł", "check": "promienie skrętu, bramki i aktualna organizacja ruchu"},
            {"place": "A1 - most przez Wisłę koło Grudziądza", "type": "most", "check": "nośność obiektu i warunki przejazdu określone przez zarządcę"},
            {"place": "Węzeł Toruń Południe", "type": "węzeł", "check": "łącznice, szerokość użytkowa i zajęcie sąsiedniego pasa"},
            {"place": "A1 - rejon Włocławka", "type": "odcinek", "check": "roboty, zwężenia i ograniczenia nocne w dniu przejazdu"},
            {"place": "Węzeł Kutno", "type": "węzeł", "check": "geometria zjazdu i miejsce postoju kontrolnego"},
            {"place": "Wjazd do Łodzi", "type": "miejski", "check": "wiadukty, sieć trakcyjna, ronda i czasowe organizacje ruchu"},
        ]
    return [
        {"place": "Gdańsk-Pruszcz Gdański", "type": "miejski", "check": "skrajnia, sygnalizacja i przejazd przez skrzyżowania"},
        {"place": "Tczew / DK91", "type": "miejski", "check": "ronda, azyle, promienie skrętu i zwężenia"},
        {"place": "Świecie", "type": "węzeł", "check": "geometria skrzyżowań i lokalne ograniczenia masy"},
        {"place": "Toruń - przeprawa przez Wisłę", "type": "most", "check": "wskazanie właściwej przeprawy, nośność i skrajnia"},
        {"place": "Włocławek", "type": "miejski", "check": "wiadukty, ronda, sygnalizacja i zamknięcia"},
        {"place": "Łęczyca / Ozorków", "type": "miejski", "check": "ciasne łuki, wyspy dzielące i parkowanie przy jezdni"},
        {"place": "Wjazd do Łodzi", "type": "miejski", "check": "sieć trakcyjna, wiadukty i plan czasowego wstrzymania ruchu"},
    ]

