# Oversize Route Studio

Interaktywna aplikacja Streamlit do wstępnego planowania przewozu ładunków ponadgabarytowych. Użytkownik podaje relację i parametry ładunku, a aplikacja:

- wyznacza i porównuje dwa warianty trasy na mapie,
- dobiera wstępną konfigurację ciągnika i naczepy,
- dopasowuje rekomendację do profilu ładunku, masy, środka ciężkości, ADR, delikatności i podzielności,
- oblicza gabaryty całego zestawu i szacuje obciążenia osi,
- wskazuje punkty wymagające audytu infrastruktury,
- wstępnie kwalifikuje zezwolenie i wymagania pilotowania,
- tworzy plan postojów, zabezpieczenia i działania awaryjnego,
- pobiera pogodę online i opcjonalnie bieżące incydenty TomTom Traffic,
- rozdziela dane potwierdzone od założeń planistycznych.

## Uruchomienie lokalne

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Na macOS/Linux aktywuj środowisko poleceniem `source .venv/bin/activate`.

## Dane o ruchu na żywo

Routing i pogoda nie wymagają klucza. Do incydentów drogowych utwórz klucz w TomTom Developer Portal i dodaj plik `.streamlit/secrets.toml`:

```toml
TOMTOM_API_KEY = "twoj-klucz"
```

W Streamlit Community Cloud dodaj tę samą wartość w **App settings → Secrets**. Klucza nie zapisuj w repozytorium.

## Wdrożenie w Streamlit Community Cloud

1. Zaloguj się przez GitHub na [share.streamlit.io](https://share.streamlit.io/).
2. Wybierz **Create app** i to repozytorium.
3. Ustaw plik startowy `app.py`.
4. Opcjonalnie dodaj sekret `TOMTOM_API_KEY`.
5. Kliknij **Deploy**.

## Ważne ograniczenie

Aplikacja jest narzędziem planistycznym i dydaktycznym. Routing publiczny nie uwzględnia automatycznie nośności wszystkich obiektów, skrajni, promieni skrętu ani treści indywidualnego zezwolenia. Przed realnym przejazdem wymagane są objazd techniczny, uzgodnienia z zarządcami dróg, aktualna weryfikacja robót i ograniczeń oraz — zależnie od trasy — ekspertyzy obiektów inżynierskich.

