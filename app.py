from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, make_response,
    jsonify
)
from flask_sqlalchemy import SQLAlchemy
import requests

app = Flask(__name__)
app.secret_key = "absolutely"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///weather.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# чтобы template-zip работал
app.jinja_env.globals.update(zip=zip)

db = SQLAlchemy(app)


# Модель для истории поисков
class Search(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String, unique=True, nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)

    @classmethod
    def record(cls, city_name):
        row = cls.query.filter_by(city=city_name).first()
        if row is None:
            row = cls(city=city_name, count=1)
            db.session.add(row)
        else:
            row.count += 1
        db.session.commit()


# API геокодинга и погоды
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@app.route("/", methods=["GET", "POST"])
def index():
    last_city = request.cookies.get("last_city", "")
    if request.method == "POST":
        city = request.form.get("city", "").strip()
        if not city:
            flash("Введите название города", "warning")
            return redirect(url_for("index"))
        return redirect(url_for("forecast", city=city))
    return render_template("index.html", last_city=last_city)


@app.route("/api/suggest")
def suggest():
    q = request.args.get("city", "").strip()
    if len(q) < 2:
        return jsonify([])
    r = requests.get(GEOCODING_URL, params={
        "name": q, "count": 5, "language": "ru"
    })
    results = r.json().get("results", [])
    seen = set()
    cities = []
    for loc in results:
        name = loc.get("name")
        if name and name not in seen:
            seen.add(name)
            cities.append(name)
    return jsonify(cities)


@app.route("/forecast")
def forecast():
    city = request.args.get("city", "").strip()
    # 1) Геокодируем
    geo = requests.get(GEOCODING_URL, params={
        "name": city, "count": 1, "language": "ru"
    }).json()
    if "results" not in geo or not geo["results"]:
        flash("Город не найден", "danger")
        return redirect(url_for("index"))

    loc = geo["results"][0]
    lat, lon = loc["latitude"], loc["longitude"]
    name = loc["name"]

    # 2) Запись в историю
    Search.record(name)

    # 3) Запрос погоды
    w = requests.get(WEATHER_URL, params={
        "latitude":         lat,
        "longitude":        lon,
        "current_weather":  True,  # ← правильный параметр
        "hourly":           "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone":         "auto",
        "forecast_days":    1
    }).json()

    # 4) Проверяем ответ
    if "current_weather" not in w or "hourly" not in w:
        flash("Не удалось получить прогноз. Попробуйте позже.", "danger")
        return redirect(url_for("index"))

    # 5) Достаём текущие данные
    current = w["current_weather"]
    current_temp = current.get("temperature")   # <-- поле называется temperature
    current_wind = current.get("windspeed")     # <-- и windspeed
    current_time = current.get("time")

    # 6) Почасовые массивы
    hours = w["hourly"].get("time", [])[:12]
    temps = w["hourly"].get("temperature_2m", [])[:12]
    hum = w["hourly"].get("relative_humidity_2m", [])[:12]
    wind = w["hourly"].get("wind_speed_10m", [])[:12]

    if not hours or not temps:
        flash("Прогноз временно недоступен.", "danger")
        return redirect(url_for("index"))

    # 7) Рендер и cookie
    resp = make_response(render_template(
        "forecast.html",
        city=name,
        current_temp=current_temp,
        current_wind=current_wind,
        current_time=current_time,
        hours=hours,
        temps=temps,
        hum=hum,
        wind=wind
    ))
    resp.set_cookie("last_city", name, max_age=30*24*3600)
    return resp


@app.route("/api/history")
def api_history():
    data = Search.query.order_by(Search.count.desc()).all()
    return jsonify([{"city": s.city, "count": s.count} for s in data])


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
