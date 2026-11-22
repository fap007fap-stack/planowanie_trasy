from __future__ import annotations

import html
import json
from datetime import date, time
from typing import Any

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen, MeasureControl
from streamlit_folium import st_folium

from calculations import Cargo, operational_plan, score_route, securing_plan, select_vehicle
from services import RouteResult, critical_points, get_routes, get_tomtom_incidents, get_weather


st.set_page_config(
    page_title="Oversize Route Studio",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
    :root { --ink:#eaf4f1; --muted:#9bb0aa; --panel:#12231f; --line:#28433c; --mint:#18c89b; --amber:#ff9f43; }
    .stApp { background: radial-gradient(circle at 80% -10%, #174e40 0, #0b1714 34%, #08110f 78%); color:var(--ink); }
    html, body, [class*="css"] { font-family:'Manrope',sans-serif; }
    .block-container { max-width:1380px; padding-top:1.5rem; padding-bottom:4rem; }
    #MainMenu, footer, header { visibility:hidden; }
    .hero { border:1px solid var(--line); border-radius:26px; padding:28px 32px; margin-bottom:18px;
      background:linear-gradient(120deg,rgba(24,200,155,.14),rgba(18,35,31,.78)); box-shadow:0 24px 70px rgba(0,0,0,.24); }
    .eyebrow { color:#70e7c7; letter-spacing:.16em; text-transform:uppercase; font-size:.74rem; font-weight:800; }
    .hero h1 { font-size:clamp(2rem,5vw,4.2rem); line-height:.98; letter-spacing:-.06em; margin:.5rem 0 .7rem; color:#f4fffc; }
    .hero p { color:#b6c9c4; max-width:850px; margin:0; font-size:1.02rem; }
    .status { display:inline-flex; gap:.45rem; align-items:center; padding:.45rem .72rem; background:#0d1a17; border:1px solid #2e5148; border-radius:999px; color:#b8cbc6; font-size:.78rem; margin-top:1rem; }
    .dot { width:8px;height:8px;border-radius:50%;background:var(--mint);box-shadow:0 0 12px var(--mint); }
    div[data-testid="stForm"] { background:rgba(14,29,25,.9); border:1px solid var(--line); border-radius:22px; padding:18px 20px 8px; }
    div[data-testid="stMetric"] { background:rgba(18,35,31,.92); border:1px solid var(--line); border-radius:18px; padding:16px; }
    div[data-testid="stMetric"] label { color:#9fb5af !important; }
    div[data-testid="stMetricValue"] { color:#f0fff9; letter-spacing:-.04em; }
    .section-title { margin:2.2rem 0 .9rem; }
    .section-title h2 { margin:0; color:#effffb; letter-spacing:-.035em; }
    .section-title p { color:var(--muted); margin:.25rem 0 0; }
    .route-card { padding:18px; border:1px solid var(--line); border-radius:18px; background:rgba(18,35,31,.9); min-height:156px; }
    .route-card .route-name { font-weight:800;font-size:1.05rem; }
    .route-card .big { font-size:2rem;font-weight:800;letter-spacing:-.05em;margin:.35rem 0; }
    .route-card .small { color:var(--muted);font-size:.82rem;line-height:1.5; }
    .tag { display:inline-block;border:1px solid #35534b;border-radius:999px;padding:.25rem .55rem;margin:.2rem .18rem .2rem 0;color:#bcd2cc;font-size:.75rem; }
    .fact { border-left:3px solid var(--mint); background:rgba(24,200,155,.07); padding:13px 15px; border-radius:0 12px 12px 0; color:#cce6df; }
    .assumption { border-left:3px solid var(--amber); background:rgba(255,159,67,.07); padding:13px 15px; border-radius:0 12px 12px 0; color:#e6d6c6; }
    .warning { border:1px solid #6b583b; background:#241e14; padding:13px 15px; border-radius:12px; color:#efd2a7; }
    .source-link a { color:#72e9c9!important; text-decoration:none; }
    .stButton>button, .stFormSubmitButton>button { border:0; border-radius:14px; background:linear-gradient(90deg,#18c89b,#32d8ad); color:#04100d; font-weight:800; min-height:46px; }
    .stDownloadButton>button { border-radius:13px;border:1px solid #315349;background:#12231f;color:#dff8f1; }
    [data-testid="stDataFrame"] { border:1px solid var(--line);border-radius:16px;overflow:hidden; }
    .leaflet-container { border-radius:20px; border:1px solid #2a4a42; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner=False)
def cached_routes(origin: str, destination: str):
    return get_routes(origin, destination)


def cached_incidents(route: RouteResult, key: str):
    return get_tomtom_incidents(route, key)


def cached_weather(route: RouteResult):
    return get_weather(route)


def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def section(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="section-title"><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def route_card(route: RouteResult, planned_h: float, points: int, incidents: int, score: float) -> str:
    tags = "".join(f'<span class="tag">{html.escape(place)}</span>' for place in route.via)
    return f"""
    <div class="route-card" style="border-top:3px solid {route.color}">
      <div class="route-name">{html.escape(route.name)}</div>
      <div class="big">{route.distance_km:.0f} km</div>
      <div class="small">Plan przejazdu: <b>{planned_h:.1f} h</b> · punkty audytu: <b>{points}</b> · utrudnienia live: <b>{incidents}</b> · wynik: <b>{score:.1f}</b></div>
      <div style="margin-top:.6rem">{tags}</div>
    </div>
    """


def incident_position(incident: dict[str, Any]) -> tuple[float, float] | None:
    geometry = incident.get("geometry", {})
    coordinates = geometry.get("coordinates")
    while isinstance(coordinates, list) and coordinates and isinstance(coordinates[0], list):
        coordinates = coordinates[0]
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        return float(coordinates[1]), float(coordinates[0])
    return None


def build_map(routes: list[RouteResult], incidents_by_route: list[list[dict[str, Any]]]) -> folium.Map:
    all_points = [point for route in routes for point in route.coordinates]
    center = [
        sum(point[1] for point in all_points) / len(all_points),
        sum(point[0] for point in all_points) / len(all_points),
    ]
    route_map = folium.Map(location=center, zoom_start=7, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="© OpenStreetMap contributors © CARTO",
        name="Ciemna mapa",
    ).add_to(route_map)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(route_map)
    Fullscreen(position="topright").add_to(route_map)
    MeasureControl(position="bottomleft", primary_length_unit="kilometers").add_to(route_map)

    for route, incidents in zip(routes, incidents_by_route):
        lat_lon = [[point[1], point[0]] for point in route.coordinates]
        group = folium.FeatureGroup(name=route.name, show=True)
        folium.PolyLine(lat_lon, color="#07100e", weight=9, opacity=0.8).add_to(group)
        folium.PolyLine(lat_lon, color=route.color, weight=5, opacity=0.96, tooltip=route.name).add_to(group)
        folium.CircleMarker(lat_lon[0], radius=7, color=route.color, fill=True, tooltip="Start").add_to(group)
        folium.CircleMarker(lat_lon[-1], radius=7, color=route.color, fill=True, tooltip="Cel").add_to(group)
        for incident in incidents:
            position = incident_position(incident)
            if not position:
                continue
            props = incident.get("properties", {})
            events = props.get("events") or []
            description = events[0].get("description", "Utrudnienie") if events else "Utrudnienie"
            folium.Marker(
                position,
                tooltip=description,
                popup=folium.Popup(html.escape(description), max_width=280),
                icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
            ).add_to(group)
        group.add_to(route_map)

    bounds = [[min(p[1] for p in all_points), min(p[0] for p in all_points)], [max(p[1] for p in all_points), max(p[0] for p in all_points)]]
    route_map.fit_bounds(bounds, padding=(30, 30))
    folium.LayerControl(collapsed=False).add_to(route_map)
    return route_map


def report_html(
    origin: str,
    destination: str,
    cargo: Cargo,
    vehicle: Any,
    rows: list[dict[str, Any]],
    recommendation: str,
) -> str:
    route_rows = "".join(
        f"<tr><td>{html.escape(str(row['Wariant']))}</td><td>{row['Dystans [km]']}</td><td>{row['Plan [h]']}</td><td>{row['Punkty kontroli']}</td><td>{row['Utrudnienia live']}</td><td>{row['Wynik']}</td></tr>"
        for row in rows
    )
    return f"""<!doctype html><html lang='pl'><meta charset='utf-8'><title>Raport trasy ponadgabarytowej</title>
    <style>body{{font:15px Arial;max-width:980px;margin:45px auto;color:#18312b;line-height:1.5}}h1{{font-size:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd8d4;padding:9px;text-align:left}}.box{{background:#eff8f5;padding:16px;border-left:5px solid #18a67f}}</style>
    <h1>Wstępny plan transportu ponadgabarytowego</h1><p><b>Relacja:</b> {html.escape(origin)} → {html.escape(destination)}</p>
    <p><b>Ładunek:</b> {html.escape(cargo.name)} ({html.escape(cargo.category)}), {cargo.mass_t:.1f} t, {cargo.length_m:.1f} × {cargo.width_m:.1f} × {cargo.height_m:.1f} m</p>
    <p><b>Zestaw:</b> {html.escape(vehicle.tractor)} + {html.escape(vehicle.trailer)}; {vehicle.gross_mass_t:.1f} t; {vehicle.total_length_m:.1f} × {vehicle.total_width_m:.1f} × {vehicle.total_height_m:.1f} m.</p>
    <table><thead><tr><th>Wariant</th><th>km</th><th>h</th><th>Punkty</th><th>Live</th><th>Wynik</th></tr></thead><tbody>{route_rows}</tbody></table>
    <div class='box'><b>Rekomendacja:</b> {html.escape(recommendation)}</div>
    <p><small>Dokument ma charakter planistyczny. Nie zastępuje zezwolenia, objazdu technicznego, ekspertyzy mostowej ani uzgodnień z zarządcami dróg.</small></p></html>"""


st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Decision support · transport ponadgabarytowy</div>
      <h1>Oversize Route<br>Studio</h1>
      <p>Od parametrów ładunku do porównania korytarzy, zestawu, pilotażu i listy miejsc do audytu — w jednym czytelnym planie operacyjnym.</p>
      <div class="status"><span class="dot"></span> Routing i pogoda online · ruch live po podaniu klucza TomTom</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("route_form"):
    a, b, c, d = st.columns([1.25, 1.25, 1, 1])
    with a:
        origin = st.text_input("Skąd", "Gdańsk, Polska")
    with b:
        destination = st.text_input("Dokąd", "Łódź, Polska")
    with c:
        trip_date = st.date_input("Data przejazdu", value=date.today())
    with d:
        trip_time = st.time_input("Planowany start", value=time(22, 0))

    st.markdown("##### Ładunek")
    e, f, g, h, i = st.columns([1.45, 1, 1, 1, 1])
    with e:
        cargo_name = st.text_input("Rodzaj", "Transformator energetyczny")
    with f:
        mass = st.number_input("Masa [t]", min_value=0.1, max_value=500.0, value=48.0, step=1.0)
    with g:
        length = st.number_input("Długość [m]", min_value=0.1, max_value=100.0, value=9.0, step=0.1)
    with h:
        width = st.number_input("Szerokość [m]", min_value=0.1, max_value=20.0, value=3.8, step=0.1)
    with i:
        height = st.number_input("Wysokość [m]", min_value=0.1, max_value=20.0, value=3.6, step=0.1)

    j, k, l, m, n = st.columns([1.65, 1, 1, 1, 1])
    with j:
        cargo_category = st.selectbox(
            "Profil ładunku",
            [
                "Transformator / urządzenie energetyczne",
                "Maszyna budowlana lub przemysłowa",
                "Długi element konstrukcyjny / łopata",
                "Zbiornik / silos",
                "Łódź / konstrukcja przestrzenna",
                "Ładunek neutralny / drobnica",
                "Inny ładunek",
            ],
        )
    with k:
        center_of_gravity = st.selectbox("Środek ciężkości", ["Niski", "Średni", "Wysoki"], index=1)
    with l:
        fragile = st.toggle("Delikatny", value=True)
    with m:
        adr = st.toggle("ADR", value=False, help="Włącza dodatkowe kontrole. Podaj właściwą klasę i numer UN w dokumentacji zlecenia.")
    with n:
        divisible = st.toggle("Podzielny", value=False)

    with st.expander("Dane live — opcjonalne"):
        api_key_input = st.text_input(
            "TomTom Traffic API key",
            value="",
            type="password",
            help="Możesz też ustawić TOMTOM_API_KEY w sekretach Streamlit Cloud.",
        )
    submitted = st.form_submit_button("Oblicz i porównaj trasy", width="stretch")

if submitted or "analysis" not in st.session_state:
    cargo = Cargo(
        cargo_name,
        mass,
        length,
        width,
        height,
        category=cargo_category,
        divisible=divisible,
        adr=adr,
        center_of_gravity=center_of_gravity,
        fragile=fragile,
    )
    vehicle = select_vehicle(cargo)
    with st.spinner("Wyznaczam korytarze i pobieram dane operacyjne…"):
        try:
            routes, location_notes = cached_routes(origin.strip(), destination.strip())
        except Exception as exc:
            st.error(f"Nie udało się wyznaczyć trasy: {exc}")
            st.stop()
        api_key = api_key_input or secret("TOMTOM_API_KEY")
        incidents_by_route: list[list[dict[str, Any]]] = []
        live_errors: list[str] = []
        for route in routes:
            try:
                incidents_by_route.append(cached_incidents(route, api_key) if api_key else [])
            except Exception as exc:
                incidents_by_route.append([])
                live_errors.append(f"{route.name}: {exc}")
        try:
            weather = cached_weather(routes[0])
        except Exception:
            weather = {}
        st.session_state.analysis = {
            "cargo": cargo,
            "vehicle": vehicle,
            "routes": routes,
            "location_notes": location_notes,
            "incidents": incidents_by_route,
            "weather": weather,
            "live_errors": live_errors,
            "api_key_present": bool(api_key),
            "origin": origin,
            "destination": destination,
            "trip_date": trip_date,
            "trip_time": trip_time,
        }

analysis = st.session_state.analysis
cargo = analysis["cargo"]
vehicle = analysis["vehicle"]
routes = analysis["routes"]
incidents_by_route = analysis["incidents"]

section("Szybka ocena zestawu", "Najpierw gabaryty całego zespołu — nie tylko samego ładunku.")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Masa całkowita", f"{vehicle.gross_mass_t:.1f} t", f"ładunek {cargo.mass_t:.1f} t", delta_color="off")
m2.metric("Wymiary zestawu", f"{vehicle.total_length_m:.1f} m", f"szer. {vehicle.total_width_m:.1f} · wys. {vehicle.total_height_m:.1f}", delta_color="off")
m3.metric("Konfiguracja", f"{vehicle.total_axles} osi", f"naczepa {vehicle.trailer_axles}-osiowa", delta_color="off")
m4.metric("Zezwolenie", vehicle.permit_category, "weryfikacja urzędowa", delta_color="off")
m5.metric("Pilotowanie", f"{vehicle.pilots} pojazd(y)", "próg ustawowy — wstępnie", delta_color="off")

route_rows: list[dict[str, Any]] = []
route_scores: list[float] = []
planned_times: list[float] = []
for route, incidents in zip(routes, incidents_by_route):
    points = critical_points(route)
    planned_h = max(route.duration_h * 1.35, route.distance_km / 55.0) + 0.6
    score = score_route(route.distance_km, planned_h, len(points), len(incidents), route.motorway_share)
    route_scores.append(score)
    planned_times.append(planned_h)
    route_rows.append(
        {
            "Wariant": route.name,
            "Dystans [km]": round(route.distance_km, 1),
            "Plan [h]": round(planned_h, 1),
            "Punkty kontroli": len(points),
            "Utrudnienia live": len(incidents),
            "Udział autostrady": f"{route.motorway_share * 100:.0f}%",
            "Wynik": score,
        }
    )

best_index = min(range(len(routes)), key=lambda idx: route_scores[idx])
recommendation = (
    f"Rekomendowany jest wariant „{routes[best_index].name}” (wynik {route_scores[best_index]:.1f}). "
    "Przewaga wynika z łącznej oceny dystansu, czasu, liczby punktów audytu, utrudnień i udziału dróg wyższej klasy."
)

section("Dwa warianty przejazdu", "Wynik niższy oznacza wariant korzystniejszy. Wagi: 22% dystans, czas ×12, punkt audytu ×6, incydent live ×8, premia za autostradę.")
route_columns = st.columns(len(routes))
for index, (column, route, incidents) in enumerate(zip(route_columns, routes, incidents_by_route)):
    with column:
        st.markdown(route_card(route, planned_times[index], len(critical_points(route)), len(incidents), route_scores[index]), unsafe_allow_html=True)

if not analysis["api_key_present"]:
    st.markdown(
        '<div class="warning">Warstwa utrudnień live jest gotowa, ale nieaktywna. Dodaj klucz TomTom w formularzu albo sekret <b>TOMTOM_API_KEY</b> w Streamlit Cloud. Routing i pogoda nadal działają online.</div>',
        unsafe_allow_html=True,
    )
elif analysis["live_errors"]:
    st.warning("Nie udało się odświeżyć części danych live: " + "; ".join(analysis["live_errors"]))

st_folium(build_map(routes, incidents_by_route), height=570, use_container_width=True, returned_objects=[])

st.success(recommendation)

tab_route, tab_vehicle, tab_risk, tab_ops, tab_formal = st.tabs(
    ["Porównanie", "Pojazd i osie", "Punkty krytyczne", "Organizacja", "Formalności i źródła"]
)

with tab_route:
    st.dataframe(pd.DataFrame(route_rows), width="stretch", hide_index=True)
    st.markdown("#### Fakty potwierdzone")
    fact_text = " · ".join(analysis["location_notes"]) or "Lokalizacje potwierdzone przez usługę geokodowania."
    st.markdown(f'<div class="fact">{html.escape(fact_text)} Dane tras pochodzą ze źródła wskazanego pod każdym wariantem.</div>', unsafe_allow_html=True)
    for route in routes:
        st.caption(f"{route.name}: {route.source}. {route.warning or ''}")
    st.markdown("#### Założenia planistyczne")
    st.markdown(
        f'<div class="assumption">Start {analysis["trip_date"]} o {analysis["trip_time"].strftime("%H:%M")}. Czas zestawu zwiększono względem routingu drogowego i dodano 0,6 h na kontrole. Wynik nie uwzględnia decyzji zarządców dróg ani indywidualnych warunków zezwolenia.</div>',
        unsafe_allow_html=True,
    )
    weather = analysis["weather"]
    if weather:
        st.info(
            f"Pogoda na środkowym odcinku (aktualizacja online): {weather.get('temperature_2m', '—')}°C, "
            f"wiatr {weather.get('wind_speed_10m', '—')} km/h, opad {weather.get('precipitation', '—')} mm."
        )

with tab_vehicle:
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown(f"### {vehicle.tractor}")
        st.write(vehicle.trailer)
        vehicle_table = pd.DataFrame(
            [
                ["Długość całkowita", f"{vehicle.total_length_m:.2f} m"],
                ["Szerokość całkowita", f"{vehicle.total_width_m:.2f} m"],
                ["Wysokość całkowita", f"{vehicle.total_height_m:.2f} m"],
                ["Rzeczywista masa całkowita", f"{vehicle.gross_mass_t:.2f} t"],
                ["Obciążenie części ciągnika", f"{vehicle.tractor_load_t:.2f} t"],
                ["Obciążenie części naczepy", f"{vehicle.trailer_load_t:.2f} t"],
            ],
            columns=["Parametr", "Wartość"],
        )
        st.dataframe(vehicle_table, width="stretch", hide_index=True)
    with right:
        axle_frame = pd.DataFrame(
            {"Oś": [f"Oś {index + 1}" for index in range(len(vehicle.axle_loads_t))], "Obciążenie [t]": vehicle.axle_loads_t}
        )
        st.bar_chart(axle_frame.set_index("Oś"), color="#18c89b", height=320)
        st.caption("Wykres pokazuje model statyczny, a nie wynik ważenia osi.")
    st.markdown("#### Przyjęte założenia")
    for note in vehicle.notes:
        st.markdown(f"- {note}")

with tab_risk:
    for route in routes:
        st.markdown(f"### {route.name}")
        point_frame = pd.DataFrame(critical_points(route))
        point_frame.columns = ["Miejsce / odcinek", "Rodzaj", "Co trzeba zweryfikować"]
        st.dataframe(point_frame, width="stretch", hide_index=True)
    if any(incidents_by_route):
        st.markdown("### Utrudnienia wykryte na żywo")
        for route, incidents in zip(routes, incidents_by_route):
            for incident in incidents[:20]:
                props = incident.get("properties", {})
                events = props.get("events") or []
                description = events[0].get("description", "Utrudnienie") if events else "Utrudnienie"
                st.write(f"- **{route.name}:** {description} ({props.get('from', '—')} → {props.get('to', '—')})")

with tab_ops:
    ops = operational_plan(vehicle.pilots, cargo)
    o1, o2 = st.columns(2)
    with o1:
        st.markdown("### Okno i postoje")
        st.write(f"**Rekomendowane okno:** {ops['window']}")
        st.write(ops["pilots"])
        for item in ops["stops"]:
            st.markdown(f"- {item}")
        st.markdown("### Mocowanie ładunku")
        for item in securing_plan(cargo):
            st.markdown(f"- {item}")
    with o2:
        st.markdown("### Plan na zamknięcie drogi")
        for number, item in enumerate(ops["emergency"], 1):
            st.markdown(f"**{number}.** {item}")

with tab_formal:
    st.markdown("### Wstępna kwalifikacja")
    st.markdown(
        f'<div class="assumption"><b>{html.escape(vehicle.permit_category)}</b> · pilotowanie: {vehicle.pilots}. To screening na podstawie obliczonych gabarytów. Kategorię, trasę i sposób pilotowania określa właściwy organ w decyzji.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Dane potrzebne do wniosku i uzgodnień")
    formal_items = [
        "pełne dane przewoźnika i wnioskodawcy oraz termin i liczba przejazdów",
        "marka, typ, numery rejestracyjne i dokumentacja ciągnika oraz naczepy",
        "rzeczywista masa całkowita, wymiary zestawu, rozstaw osi i naciski każdej osi",
        "rysunek zestawu z rozmieszczeniem ładunku, promieniami skrętu i prześwitem",
        "proponowana trasa z miejscami postoju oraz wykazem obiektów inżynierskich",
        "oświadczenie o niepodzielności ładunku i plan jego mocowania",
        "wyniki objazdu technicznego, pomiary skrajni i wymagane ekspertyzy nośności",
        "projekt czasowej organizacji ruchu, jeśli przejazd wymaga zajęcia pasów lub demontażu infrastruktury",
    ]
    for item in formal_items:
        st.markdown(f"- {item}")
    st.markdown("### Oficjalne źródła")
    st.markdown(
        """
        <div class="source-link">
        • <a href="https://www.gov.pl/web/gddkia/przejazdy-nienormatywne3" target="_blank">GDDKiA — przejazdy nienormatywne, wnioski i wykaz obiektów</a><br>
        • <a href="https://eli.gov.pl/eli/DU/2023/2487/ogl/pol" target="_blank">Rozporządzenie w sprawie pilotowania pojazdów nienormatywnych</a><br>
        • <a href="https://eli.gov.pl/api/acts/DU/2024/1251/text.html" target="_blank">Prawo o ruchu drogowym — tekst jednolity</a><br>
        • <a href="https://drogi.gddkia.gov.pl/" target="_blank">GDDKiA — serwis informacji drogowej</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

section("Eksport planu", "Zapisz tabelę porównawczą lub czytelny raport do dalszej weryfikacji.")
download_a, download_b, disclaimer = st.columns([1, 1, 2])
with download_a:
    st.download_button(
        "Pobierz porównanie CSV",
        pd.DataFrame(route_rows).to_csv(index=False).encode("utf-8-sig"),
        file_name="porownanie_tras.csv",
        mime="text/csv",
        width="stretch",
    )
with download_b:
    st.download_button(
        "Pobierz raport HTML",
        report_html(analysis["origin"], analysis["destination"], cargo, vehicle, route_rows, recommendation),
        file_name="raport_transportu.html",
        mime="text/html",
        width="stretch",
    )
with disclaimer:
    st.caption("Narzędzie wspiera planowanie. Nie zastępuje zezwolenia, objazdu technicznego, sprawdzenia aktualnych robót ani ekspertyzy obiektów mostowych.")

with st.expander("Dane techniczne analizy"):
    st.code(json.dumps({"vehicle": vehicle.as_dict(), "routes": route_rows}, ensure_ascii=False, indent=2), language="json")

