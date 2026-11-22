from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any
from urllib.parse import quote

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


def _tomtom_geocode(query: str, api_key: str) -> tuple[float, float, str] | None:
    encoded_query = quote(query, safe="")
    for country_set in ("PL", None):
        params = {"key": api_key, "limit": 1, "language": "pl-PL"}
        if country_set:
            params["countrySet"] = country_set
        try:
            response = requests.get(
                f"https://api.tomtom.com/search/2/geocode/{encoded_query}.json",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                result = results[0]
                position = result["position"]
                address = result.get("address", {})
                label = address.get("freeformAddress") or address.get("municipality") or query
                return float(position["lat"]), float(position["lon"]), label
        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue
    return None


def geocode(query: str, api_key: str = "") -> tuple[float, float, str]:
    if api_key:
        tomtom_result = _tomtom_geocode(query, api_key)
        if tomtom_result:
            return tomtom_result

    photon_queries = [f"{query}, Polska", query]
    for photon_query in photon_queries:
        try:
            response = requests.get(
                "https://photon.komoot.io/api/",
                params={"q": photon_query, "limit": 1, "lang": "pl"},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            features = response.json().get("features", [])
            if features:
                feature = features[0]
                lon, lat = feature["geometry"]["coordinates"][:2]
                props = feature.get("properties", {})
                label_parts = [
                    props.get("name"),
                    props.get("city"),
                    props.get("state"),
                    props.get("country"),
                ]
                label = ", ".join(dict.fromkeys(part for part in label_parts if part))
                return float(lat), float(lon), label or query
        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue

    searches = [
        {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "pl"},
        {"q": query, "format": "jsonv2", "limit": 1},
    ]
    for params in searches:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue
    raise ValueError(f"Nie znaleziono lokalizacji: {query}")


def _tomtom_route(
    points: list[tuple[float, float]], api_key: str, alternatives: bool
) -> list[dict[str, Any]]:
    locations = ":".join(f"{lat},{lon}" for lat, lon in points)
    response = requests.get(
        f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json",
        params={
            "key": api_key,
            "travelMode": "truck",
            "routeType": "fastest",
            "traffic": "true",
            "routeRepresentation": "polyline",
            "maxAlternatives": 1 if alternatives else 0,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    normalized: list[dict[str, Any]] = []
    for route in response.json().get("routes", []):
        summary = route.get("summary", {})
        coordinates: list[list[float]] = []
        for leg in route.get("legs", []):
            for point in leg.get("points", []):
                coordinate = [float(point["longitude"]), float(point["latitude"])]
                if not coordinates or coordinate != coordinates[-1]:
                    coordinates.append(coordinate)
        if len(coordinates) >= 2:
            normalized.append(
                {
                    "distance": float(summary.get("lengthInMeters", 0.0)),
                    "duration": float(summary.get("travelTimeInSeconds", 0.0)),
                    "geometry": {"coordinates": coordinates},
                    "legs": [],
                }
            )
    if not normalized:
        raise ValueError("TomTom Routing nie zwrócił trasy.")
    return normalized


def _osrm_route(
    points: list[tuple[float, float]], alternatives: bool = False, api_key: str = ""
) -> list[dict[str, Any]]:
    if api_key:
        try:
            return _tomtom_route(points, api_key, alternatives)
        except (requests.RequestException, ValueError, TypeError, KeyError):
            pass
    path = ";".join(f"{lon},{lat}" for lat, lon in points)
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "true" if alternatives else "false",
    }
    providers = [
        "https://router.project-osrm.org/route/v1/driving",
        "https://routing.openstreetmap.de/routed-car/route/v1/driving",
    ]
    for provider in providers:
        try:
            response = requests.get(
                f"{provider}/{path}",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes"):
                return data["routes"]
        except (requests.RequestException, ValueError, TypeError):
            continue
    raise ValueError("Publiczne serwery trasowania są chwilowo niedostępne. Spróbuj ponownie za moment.")


def _known_corridors(origin: str, destination: str) -> bool:
    text = f"{origin} {destination}".lower()
    return "gdań" in text and ("łód" in text or "lodz" in text)


def _route_labels(route: dict[str, Any], origin: str, destination: str) -> list[str]:
    labels: list[str] = [origin]
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            road = (step.get("ref") or step.get("name") or "").strip()
            if road and road not in labels and road.lower() not in {"unnamed road", "droga bez nazwy"}:
                labels.append(road)
            if len(labels) >= 6:
                break
        if len(labels) >= 6:
            break
    if destination not in labels:
        labels.append(destination)
    return labels


def _motorway_share(route: dict[str, Any]) -> float:
    total = max(float(route.get("distance", 0.0)), 1.0)
    preferred = 0.0
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            road_ref = str(step.get("ref") or "").upper()
            if any(part.strip().startswith(("A", "S")) for part in road_ref.split(";")):
                preferred += float(step.get("distance", 0.0))
    return min(1.0, preferred / total)


def _detour_candidates(
    start: tuple[float, float], end: tuple[float, float]
) -> list[tuple[float, float]]:
    start_lat, start_lon = start
    end_lat, end_lon = end
    middle_lat = (start_lat + end_lat) / 2
    middle_lon = (start_lon + end_lon) / 2
    dlat = end_lat - start_lat
    dlon = (end_lon - start_lon) * max(cos(radians(middle_lat)), 0.25)
    norm = sqrt(dlat * dlat + dlon * dlon) or 1.0
    straight_km = haversine_km([start_lon, start_lat], [end_lon, end_lat])
    offset_km = min(55.0, max(12.0, straight_km * 0.16))
    lat_offset = (-dlon / norm) * (offset_km / 111.0)
    lon_offset = (dlat / norm) * (offset_km / (111.0 * max(cos(radians(middle_lat)), 0.25)))
    return [
        (middle_lat + lat_offset, middle_lon + lon_offset),
        (middle_lat - lat_offset, middle_lon - lon_offset),
    ]


def _ensure_alternative(
    routes: list[dict[str, Any]],
    start: tuple[float, float],
    end: tuple[float, float],
    api_key: str = "",
) -> list[dict[str, Any]]:
    if len(routes) >= 2:
        return routes[:2]
    primary = routes[0]
    primary_distance = float(primary["distance"])
    candidates: list[dict[str, Any]] = []
    for waypoint in _detour_candidates(start, end):
        try:
            candidate = _osrm_route([start, waypoint, end], api_key=api_key)[0]
        except Exception:
            continue
        ratio = float(candidate["distance"]) / max(primary_distance, 1.0)
        if 1.03 <= ratio <= 1.85:
            candidates.append(candidate)
    if candidates:
        candidates.sort(key=lambda item: float(item["distance"]))
        return [primary, candidates[0]]
    duplicate = dict(primary)
    duplicate["_duplicate_fallback"] = True
    return [primary, duplicate]


def get_routes(origin: str, destination: str, api_key: str = "") -> tuple[list[RouteResult], list[str]]:
    notes: list[str] = []
    try:
        start_lat, start_lon, start_label = geocode(origin, api_key)
        end_lat, end_lon, end_label = geocode(destination, api_key)
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
                route = _osrm_route(
                    [(start_lat, start_lon), *vias, (end_lat, end_lon)], api_key=api_key
                )[0]
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

        start = (start_lat, start_lon)
        end = (end_lat, end_lon)
        raw = _osrm_route([start, end], alternatives=True, api_key=api_key)
        raw = _ensure_alternative(raw, start, end, api_key)
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
                    via=_route_labels(route, origin, destination),
                    motorway_share=_motorway_share(route),
                    source="OSRM / OpenStreetMap",
                    warning=(
                        "Silnik nie znalazł niezależnej alternatywy; pokazano przebieg bazowy do ręcznego wyznaczenia objazdu."
                        if route.get("_duplicate_fallback")
                        else "Routing dla samochodu osobowego - wymaga pełnego audytu dla pojazdu nienormatywnego."
                    ),
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


def _route_bbox_chunks(
    route: RouteResult, max_length_km: float = 58.0, padding_degrees: float = 0.08
) -> list[tuple[float, float, float, float]]:
    if not route.coordinates:
        return []
    chunks: list[list[list[float]]] = []
    current = [route.coordinates[0]]
    travelled = 0.0
    previous = route.coordinates[0]
    for point in route.coordinates[1:]:
        travelled += haversine_km(previous, point)
        current.append(point)
        previous = point
        if travelled >= max_length_km:
            chunks.append(current)
            current = [point]
            travelled = 0.0
    if len(current) > 1 or not chunks:
        chunks.append(current)

    boxes: list[tuple[float, float, float, float]] = []
    for chunk in chunks:
        lons = [point[0] for point in chunk]
        lats = [point[1] for point in chunk]
        boxes.append(
            (
                max(-180.0, min(lons) - padding_degrees),
                max(-90.0, min(lats) - padding_degrees),
                min(180.0, max(lons) + padding_degrees),
                min(90.0, max(lats) + padding_degrees),
            )
        )
    return boxes


def _tomtom_error(response: requests.Response) -> RuntimeError:
    message = "nieznany błąd zapytania"
    try:
        payload = response.json()
        detail = payload.get("detailedError", payload)
        message = detail.get("message", message)
    except (TypeError, ValueError, AttributeError):
        pass
    return RuntimeError(f"TomTom Traffic zwrócił HTTP {response.status_code}: {message}")


def get_tomtom_incidents(route: RouteResult, api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    attributes = (
        "incidents(type,geometry(type,coordinates),properties("
        "id,iconCategory,magnitudeOfDelay,events(description,code,iconCategory),"
        "startTime,endTime,from,to,lengthInMeters,delayInSeconds,roadNumbers))"
    )
    incidents: dict[str, dict[str, Any]] = {}
    errors: list[RuntimeError] = []
    for min_lon, min_lat, max_lon, max_lat in _route_bbox_chunks(route):
        response = requests.get(
            "https://api.tomtom.com/maps/orbis/traffic/incidents/details",
            params={
                "apiVersion": "2",
                "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
                "timeValidity": "present",
            },
            headers={
                "TomTom-Api-Key": api_key,
                "Accept-Language": "pl-PL",
                "Attributes": attributes,
                "User-Agent": USER_AGENT,
            },
            timeout=TIMEOUT,
        )
        if not response.ok:
            errors.append(_tomtom_error(response))
            continue
        for incident in response.json().get("incidents", []):
            properties = incident.get("properties", {})
            incident_id = str(properties.get("id") or repr(incident.get("geometry")))
            incidents[incident_id] = incident
    if errors and not incidents:
        raise errors[0]
    return list(incidents.values())


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
    if route.name == "Korytarz A1":
        return [
            {"place": "Wyjazd z Gdańska / węzeł Rusocin", "type": "węzeł", "check": "promienie skrętu, bramki i aktualna organizacja ruchu"},
            {"place": "A1 - most przez Wisłę koło Grudziądza", "type": "most", "check": "nośność obiektu i warunki przejazdu określone przez zarządcę"},
            {"place": "Węzeł Toruń Południe", "type": "węzeł", "check": "łącznice, szerokość użytkowa i zajęcie sąsiedniego pasa"},
            {"place": "A1 - rejon Włocławka", "type": "odcinek", "check": "roboty, zwężenia i ograniczenia nocne w dniu przejazdu"},
            {"place": "Węzeł Kutno", "type": "węzeł", "check": "geometria zjazdu i miejsce postoju kontrolnego"},
            {"place": "Wjazd do Łodzi", "type": "miejski", "check": "wiadukty, sieć trakcyjna, ronda i czasowe organizacje ruchu"},
        ]
    if route.name == "Korytarz DK91":
        return [
            {"place": "Gdańsk-Pruszcz Gdański", "type": "miejski", "check": "skrajnia, sygnalizacja i przejazd przez skrzyżowania"},
            {"place": "Tczew / DK91", "type": "miejski", "check": "ronda, azyle, promienie skrętu i zwężenia"},
            {"place": "Świecie", "type": "węzeł", "check": "geometria skrzyżowań i lokalne ograniczenia masy"},
            {"place": "Toruń - przeprawa przez Wisłę", "type": "most", "check": "wskazanie właściwej przeprawy, nośność i skrajnia"},
            {"place": "Włocławek", "type": "miejski", "check": "wiadukty, ronda, sygnalizacja i zamknięcia"},
            {"place": "Łęczyca / Ozorków", "type": "miejski", "check": "ciasne łuki, wyspy dzielące i parkowanie przy jezdni"},
            {"place": "Wjazd do Łodzi", "type": "miejski", "check": "sieć trakcyjna, wiadukty i plan czasowego wstrzymania ruchu"},
        ]

    checks = [
        ("miejski", "skrajnia, sygnalizacja, ronda i możliwość wyjazdu zestawu"),
        ("obiekt inżynierski", "mosty i wiadukty w pobliżu punktu: nośność, wysokość i szerokość"),
        ("odcinek", "roboty drogowe, zwężenia, nawierzchnia i dopuszczalne naciski osi"),
        ("węzeł", "promienie skrętu, wyspy dzielące i zajęcie sąsiedniego pasa"),
        ("obiekt inżynierski", "przeprawy, linie napowietrzne i ograniczenia skrajni"),
        ("miejski", "wjazd do celu, sieć trakcyjna, parkowanie i czasowa organizacja ruchu"),
    ]
    points: list[dict[str, str]] = []
    last_index = max(len(route.coordinates) - 1, 0)
    for index, (point_type, check) in enumerate(checks):
        coordinate = route.coordinates[round(last_index * index / (len(checks) - 1))]
        label_index = round((len(route.via) - 1) * index / (len(checks) - 1)) if route.via else 0
        label = route.via[label_index] if route.via else f"Punkt {index + 1}"
        points.append(
            {
                "place": f"{label} · {coordinate[1]:.4f}, {coordinate[0]:.4f}",
                "type": point_type,
                "check": check,
            }
        )
    return points
