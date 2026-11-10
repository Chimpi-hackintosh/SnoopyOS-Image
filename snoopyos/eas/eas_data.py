"""Previsão do tempo e avisos oficiais para a cidade selecionada no EAS."""
from dataclasses import dataclass
from datetime import datetime
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class City:
    name: str
    state: str
    country: str
    latitude: float
    longitude: float

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str) or not isinstance(self.state, str):
            raise ValueError("Nome de cidade inválido")
        if self.country not in DEFAULT_COUNTRIES:
            raise ValueError("País não disponível")
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValueError("Coordenadas inválidas")

    @property
    def label(self):
        return f"{self.name}, {self.state}" if self.state else self.name


DEFAULT_COUNTRIES = {"BR": "Brasil", "US": "Estados Unidos"}
DEFAULT_CITIES = {
    "BR": City("Nova Iguaçu", "Rio de Janeiro", "BR", -22.75917, -43.45111),
    "US": City("Washington", "Distrito de Colúmbia", "US", 38.89511, -77.03637),
}
ALERT_SOURCES = {
    "BR": ("INMET", "https://avisos.inmet.gov.br/"),
    "US": ("National Weather Service", "https://www.weather.gov/alerts"),
}
CONDITIONS = {
    0: "Céu limpo", 1: "Predomínio de sol", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Neblina", 48: "Neblina congelante",
    51: "Garoa leve", 53: "Garoa", 55: "Garoa intensa",
    56: "Garoa congelante", 57: "Garoa congelante intensa",
    61: "Chuva fraca", 63: "Chuva moderada", 65: "Chuva forte",
    66: "Chuva congelante", 67: "Chuva congelante forte",
    71: "Neve fraca", 73: "Neve moderada", 75: "Neve forte", 77: "Grãos de neve",
    80: "Pancadas leves", 81: "Pancadas de chuva", 82: "Pancadas fortes",
    85: "Pancadas leves de neve", 86: "Pancadas fortes de neve",
    95: "Tempestade", 96: "Tempestade com granizo", 99: "Tempestade com granizo forte",
}
USER_AGENT = "SnoopyOS EAS/0.1 (https://github.com/Chimpi-hackintosh/SnoopyOS-Image)"


def request_json(url, **parameters):
    if parameters:
        url += "?" + urlencode(parameters)
    request = Request(url, headers={"User-Agent": USER_AGENT,
                                   "Accept": "application/json, application/geo+json"})
    limit = 8 * 1024 * 1024
    with urlopen(request, timeout=8) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Resposta grande demais")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Resposta do serviço inválida")
    return data


def search_cities(name, country):
    response = request_json("https://geocoding-api.open-meteo.com/v1/search",
                            name=name, countryCode=country, language="pt", count=8)
    cities = []
    for item in response.get("results", []):
        if item.get("country_code") == country and item.get("feature_code", "").startswith("PPL"):
            cities.append(City(item["name"], item.get("admin1", ""), country,
                               item["latitude"], item["longitude"]))
    return cities


def measurement(value, unit):
    return "—" if value is None else f"{value:.0f}{unit}"


def forecast(city):
    response = request_json(
        "https://api.open-meteo.com/v1/forecast", latitude=city.latitude, longitude=city.longitude,
        timezone="auto", forecast_days=3,
        current="temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
        daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    )
    current = response["current"]
    measured = datetime.fromisoformat(current["time"]).strftime("%d/%m às %H:%M")
    temperature = measurement(current["temperature_2m"], " °C")
    condition = CONDITIONS.get(current["weather_code"], "Condição indisponível")
    if current["weather_code"] == 1 and current["is_day"] == 0:
        condition = "Poucas nuvens"
    feels_like = measurement(current["apparent_temperature"], " °C")
    humidity = measurement(current["relative_humidity_2m"], "%")
    wind = measurement(current["wind_speed_10m"], " km/h")
    daily = response["daily"]
    days = []
    for index, day in enumerate(daily["time"][:3]):
        date = datetime.fromisoformat(day).strftime("%d/%m")
        outlook = CONDITIONS.get(daily["weather_code"][index], "Condição indisponível")
        low = measurement(daily["temperature_2m_min"][index], " °C")
        high = measurement(daily["temperature_2m_max"][index], " °C")
        rain = measurement(daily["precipitation_probability_max"][index], "%")
        days.append(f"{date} · {outlook}\nMín. {low}  ·  Máx. {high}  ·  Chuva {rain}")
    return (
        f"{temperature} · {condition}",
        f"Sensação {feels_like}  ·  Umidade {humidity}  ·  Vento {wind}",
        f"Modelo de {measured} no horário da cidade", days,
    )


def ring_contains(ring, longitude, latitude):
    """Teste de cruzamento de raios para um anel GeoJSON [longitude, latitude]."""
    if len(ring) < 4:
        raise ValueError("Polígono de aviso inválido")
    inside = False
    previous_x, previous_y = ring[-1]
    for x, y in ring:
        if min(x, previous_x) <= longitude <= max(x, previous_x) and min(y, previous_y) <= latitude <= max(y, previous_y):
            cross = (x - previous_x) * (latitude - previous_y) - (y - previous_y) * (longitude - previous_x)
            if abs(cross) < 1e-10:
                return True
        if (y > latitude) != (previous_y > latitude):
            crossing = x + (previous_x - x) * (latitude - y) / (previous_y - y)
            if longitude < crossing:
                inside = not inside
        previous_x, previous_y = x, y
    return inside


def covers_city(geometry, city):
    shape = geometry["type"]
    polygons = geometry["coordinates"]
    if shape == "Polygon":
        polygons = [polygons]
    elif shape != "MultiPolygon":
        raise ValueError("Geometria de aviso desconhecida")
    for outer, *holes in polygons:
        if ring_contains(outer, city.longitude, city.latitude) and not any(
                ring_contains(hole, city.longitude, city.latitude) for hole in holes):
            return True
    return False


def inmet_alerts(city):
    response = request_json("https://apiprevmet3.inmet.gov.br/avisos/ativos")
    now = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    alerts = []
    for item in response["hoje"]:
        if item["encerrado"]:
            continue
        start = datetime.fromisoformat(item["inicio"])
        end = datetime.fromisoformat(item["fim"])
        if start <= now < end and covers_city(json.loads(item["poligono"]), city):
            alerts.append(f"{item['descricao']} · {item['severidade']}\n"
                          f"Até {end:%d/%m às %H:%M} (horário de Brasília)")
    return alerts


def nws_alerts(city):
    response = request_json("https://api.weather.gov/alerts/active",
                            point=f"{city.latitude:.4f},{city.longitude:.4f}", status="actual")
    alerts = []
    for feature in response["features"]:
        item = feature["properties"]
        if item["status"] == "Actual":
            end = datetime.fromisoformat(item.get("ends") or item["expires"])
            alerts.append(f"{item['event']} · {item['severity']}\nVálido até {end:%d/%m %H:%M %z}")
    return alerts


def active_alerts(city):
    return inmet_alerts(city) if city.country == "BR" else nws_alerts(city)
