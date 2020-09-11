"""
Helper functions to scrape data from the sea level sensors project.

see https://dev.sealevelsensors.org/
"""
import requests as req
import numpy as np
import dateutil.parser as date_parser
from pprint import pprint as print
import json
import os
import datetime
import binary_search as bs
import re
from dateutil.tz import tzutc
import pytz
import pymongo
import private_config
from utils import db_connector
from utils import utils


# utc = pytz.utc
# DB connection
db = db_connector.mongodb_connection()


base_url_sls       = 'https://api.sealevelsensors.org/v1.0/Things'
base_url_noaa      = 'https://tidesandcurrents.noaa.gov/api/datagetter'
DEFAULT_START_DATE = 'March 1 2020'


def get_sensor_datastreams():
    """
    Creates a list of all sensors with datastream links.

    Returns:
        sensors (list): a list of 'sensors', each sensor being a dictonary with
            information on the sensor
    """
    api_response = req.get(base_url_sls).json()
    # print(api_response)
    def create_sensor_obj(sensor):
        """Turns a 'sensor' from the API into a succinct dictionary."""
        location = (req.get(sensor["Locations@iot.navigationLink"])).json()["value"][0]
        # print(location)
        coordinates = location["location"]["coordinates"]
        # print(coordinates)
        return {
          "name":   sensor["name"],
          "desc":   sensor["description"],
          "link":   sensor["Datastreams@iot.navigationLink"],
          "elev":   sensor["properties"].get("elevationNAVD88"),
          "coords": coordinates}
    return list(map(create_sensor_obj, api_response["value"]))


def get_sensors_with_obs_type(type_name="Water Level"):
    """
    Creates a list of all sensors with water level observation links.

    Parameters:
        type_name (str): type of observation to get
            default: 'Water Level'
    Returns:
        sensors (list): a list of 'sensors', each sensor being a dictionary
            with information on the sensor
    """
    all_sensor_links = get_sensor_datastreams()
    # print(all_sensor_links)
    def get_link_from_sensor(sensor):
        """Grabs the requested datastream from the sensor if it has one."""
        # get all the observation types then filter the ones that say "Water Level"
        obs_type_list   = req.get(sensor["link"]).json()["value"]
        # print(obs_type_list)
        only_water_list = list(filter(lambda obs_type: obs_type["name"] == type_name, obs_type_list))
        # some don't have a water level. Just return in that case
        if len(only_water_list) == 0:
            return
        # variable naming is not my forte
        wataaa = only_water_list[0]
        # print(wataaa)
        return {
            "name":   sensor["name"],
            "desc":   sensor["desc"],
            "elev":   sensor["elev"],
            "coords": sensor["coords"],
            "link":   wataaa['Observations@iot.navigationLink']}
    # the filter simply removes all the Nones due to sensors that don't have a water level link
    return list(filter(None, map(get_link_from_sensor, all_sensor_links)))

"""
Gets all observations for a given link and caches it for future use

    The observations are sorted by date.
    The return list has datetime objects inside, which may pose a challenge
    to json serialization

    This code has only been tested on water observations
    may need tweaking for other observation types

    TODO: THIS CACHE IS NOT VERY INTELLIGENT.
    A PROPER DATABASE OR SOMETHING WOULD BE A GODSEND

    Parameters:
        link         (str):             Datastream link to collect observations from
        start_date   (str)  (optional): Date to start  collecting observations from
        end_date     (str)  (optional): Date to finish collecting observations from
        reset_cache  (bool) (optional): Delete the cache and create a new one
        cache_folder (str)  (optional): Folder to look for cache files

    Returns:
        observations (list): a list of tuples, (observation, date_of_observation)
"""




def get_obs_for_link(link, sensor_name, start_date=None, end_date=None, reset_cache=False):
    observations = []
    today = str(datetime.datetime.utcnow())
    # Parse end and start dates
    # def utcparse(x): return date_parser.parse(x).replace(tzinfo=tzutc())
    parsed_start_date = (utils.utcparse(start_date)
                         if start_date
                         else date_parser.parse(DEFAULT_START_DATE))
    parsed_end_date = (utils.utcparse(end_date)
                       if end_date
                       else datetime.datetime.now(datetime.timezone.utc))

    update = True
    if not reset_cache:
        # check if collection exists
        # if sensor_name not in db.list_collection_names():
        #     collection = db[sensor_name]
        # query for all observations
        try:
            queried_observations = db[sensor_name].find_one({}, {'_id':0, 'observations':1})
        except pymongo.errors.OperationFailure:
            print("DB failed")
        try:
            if queried_observations is None:
                raise FileNotFoundError
            observations = queried_observations['observations']
            """
            # datetime is stored in Mongo as aware object but is queried as
            # naive so it has to be changed back to aware to retain timezone info
            # converts observations to numpy array to vectorize operation of
            # converting all dates to aware
            """
            observations = np.array(observations)
            vfunc = np.vectorize(utils.make_aware_date)
            observations[:, 1] = vfunc(observations[:,1])
            observations = observations.tolist()
            last_observation_date = observations[-1][1]
            if parsed_end_date > last_observation_date:
                last_observation_date = utils.remove_tzinfo(str(last_observation_date))
                observations += get_obs_for_link_uncached(link, str(last_observation_date), str(today))
            else:
                update = False
        except FileNotFoundError:
            observations = get_obs_for_link_uncached(link, DEFAULT_START_DATE, today)
    else:
        observations = get_obs_for_link_uncached(link, DEFAULT_START_DATE, today)
    if update:
        try:
            db[sensor_name].replace_one({}, {"observations": observations}, True)
        except pymongo.errors.OperationFailure:
            print("Error: Couldn't write to the DB")
    start_index = bs.search(observations, (None, parsed_start_date), key=lambda x: x[1])
    end_index = bs.search(observations, (None, parsed_end_date), key=lambda x: x[1])
    return observations[start_index:end_index]




def get_obs_for_link_uncached(link, start_date=None, end_date=None):
    """
    Gets all observations for a given link without using any cache

    The observations are sorted by date.
    The return list has datetime objects inside, which may pose a challenge
    to json serialization

    This code has only been tested on water observations
    may need tweaking for other observation types

    Parameters:
        link       (str):            Datastream link to collect observations from
        start_date (str) (optional): Date to start  collecting observations from
        end_date   (str) (optional): Date to finish collecting observations from

    Returns:
        observations (list): a list of tuples, (observation, date_of_observation)
    """
    # This program is recursive, and can pass an "iot next link" to itself
    # this link will have a "?" in it
    is_iot_next_link = "?" in link
    params = {}
    # an iot next link contains the params, so no need to set them if that's the case
    if not is_iot_next_link:
        params["$select"]       = "resultTime,result"
        params["$resultFormat"] =  "dataArray"

    if end_date and not start_date:
        start_date = DEFAULT_START_DATE

    start_date = date_parser.parse(start_date).isoformat() + "Z" if start_date else None
    end_date   = date_parser.parse(end_date).isoformat()   + "Z" if end_date   else None

    # adding the start and end date to the filters if need be
    if start_date and end_date:
        params["$filter"] = "resultTime ge " + start_date + " and resultTime le " + end_date
    elif start_date:
        params["$filter"] = "resultTime ge " + start_date

    try:
        response = req.get(link, params = params).json()
        # print(repr(response))
    except req.exceptions.HTTPError as err:
        print(err)
    # no response? just return something
    if len(response["value"]) == 0:
        return []
    unparsed_observations = response["value"][0]["dataArray"]
    observations = list(map(lambda x: (x[0], date_parser.parse(x[1])), unparsed_observations))
    """
    the response only returns 100 observations
    so we need to get the rest. Luckily it also returns
    @iot.nextLink which is a link to the next 100
    we use that link to recursively get all the observations we need
    We don't need to deal with params because the @iot.nextLink
    includes all the params
    """
    if "@iot.nextLink" in response:
        all_observations = get_obs_for_link_uncached(response['@iot.nextLink']) + observations
        # sort the observations by time if this is the top of the recursion
        if not is_iot_next_link:
            return sorted(all_observations, key=lambda x: x[1])
        return all_observations
    else:
        # No iot next link? Must be the end, return
        return sorted(observations, key=lambda x: x[1])

def get_ft_pulaski(start_date, end_date):
    """
    Gets tide PREDICTIONS from the ft pulaski NOAA sensor

    uses NAVD datum, GMT timezone, and metric units

    Parameters:
        start_date (str): Date to start  collecting observations from
        end_date   (str): Date to finish collecting observations from

    Returns:
        observations (list): a list of dictionaries with information on predictions
    """
    params = {
        "product":     "predictions",
        "application": "Georgia_Tech",
        "datum":       "NAVD",
        "station":     "8670870",
        "time_zone":   "GMT",
        "units":       "metric",
        "format":      "json"
    }

    def format_time(date):
        return date_parser.parse(date).strftime("%Y%m%d %H:%M")

    params["begin_date"] = format_time(start_date)
    params["end_date"]   = format_time(end_date)

    return req.get(base_url_noaa, params=params).json()["predictions"]


if __name__ == "__main__":
    waaata = get_sensors_with_obs_type()
    print(waaata[14])
    # aa = get_obs_for_link(waaata[14]["link"], "2019-07-03 06:30:00", "2019-07-03 08:30:00")
    oina = get_obs_for_link(waaata[14]["link"], "July 3 2019 0630", "July 3 2019 0830")
    print(oina)
    # print(get_ft_pulaski("April 1 2018", "April 3 2019"))
