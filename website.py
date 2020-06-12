from flask import Flask, request, jsonify, render_template
import api_scraper
import csv
import config as conf

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_sensors_with_obs_type")
def get_sensors_with_obs_type_wrapper():
    return jsonify(api_scraper.get_sensors_with_obs_type())


@app.route("/get_obs_for_link")
def get_obs_for_link_wrapper():
    args = request.args
    return jsonify(api_scraper.get_obs_for_link(link=args["link"], sensor_name=args["sensor_name"], start_date=args["start_date"]))


@app.route("/daily_output")
def get_daily_csv():
    with open(conf.CSV_OUTFILE, "r") as f:
        reader = csv.DictReader(f)
        return jsonify(list(reader))


@app.route("/irma")
def get_irma():
    with open("./irma.csv", "r") as f:
        reader = csv.DictReader(f)
        return jsonify(list(reader))


@app.route("/matthew")
def get_matthew():
    with open("./matthew.csv", "r") as f:
        reader = csv.DictReader(f)
        return jsonify(list(reader))


@app.route("/sensor_groupings")
def get_sensor_groupings():
    return jsonify(conf.SENSOR_GROUPINGS)


@app.route("/hurricane_info")
def hurricane_info():
    return render_template("hurricane.html")


if __name__ == "__main__":
    app.run(debug=True)
