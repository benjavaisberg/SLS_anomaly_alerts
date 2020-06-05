"""
Helper functions to scrape data from the sea level sensors project.

see https://dev.sealevelsensors.org/
"""
import requests as req
import dateutil.parser as date_parser
from pprint import pprint as print
import json
import os
import datetime
import binary_search as bs
import re
from dateutil.tz import tzutc
from pymongo import MongoClient
import private_config

client = MongoClient(private_config.DB_URI)
db = client.test # collection name: test


base_url_sls       = 'https://api.sealevelsensors.org/v1.0/Things'
base_url_noaa      = 'https://tidesandcurrents.noaa.gov/api/datagetter'
DEFAULT_START_DATE = 'April 1 2019'


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

def get_obs_for_link(link, start_date=None, end_date=None, reset_cache=False, cache_folder='cache'):
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
    observations = []
    # the file name is quite absurd, but hopefully unique
    file_name = './' + cache_folder + '/' + "".join(re.split("[^a-zA-Z0-9]*", link)) + '.json'
    # just parsing some dates
    today = str(datetime.datetime.utcnow())
    def utcparse(x): return date_parser.parse(x).replace(tzinfo=tzutc())
    parsed_start_date = (utcparse(start_date)
                        if start_date
                        else date_parser.parse(DEFAULT_START_DATE))
    parsed_end_date = (utcparse(end_date)
                       if end_date
                       else datetime.datetime.now(datetime.timezone.utc))
    # whether or not to write out a new cache
    do_update = True
    if not reset_cache:
        # if there is no folder to store caches in, create one
        if not os.path.isdir('./' + cache_folder):
            os.mkdir('./' + cache_folder)
        try:
            with open(file_name) as cache_file:
                # load and parse all the observations
                observations = list(map(lambda x: (x[0], utcparse(x[1])), json.load(cache_file)))
                # no observations? time to rebuild the cache
                if len(observations) < 1: 
                	raise FileNotFoundError 
                # the last cached observation
                end_observations = observations[-1][1]
                if parsed_end_date > end_observations:
                    """
                    if the requested end date goes beyond the cache, we need more data
                    note the [:-6]. This is a hacky bandaid because 
                    for some reason the date format wasn't working
                    also note the [1:]
                    this is because the first element is duplicated 
                    in the cache and when getting new data
                    """
                    observations += get_obs_for_link_uncached(link, str(end_observations)[:-6], str(today))[1:]
                else:
                    do_update = False
        except FileNotFoundError:
            # if there is no existing cache, create one with all the data you can get
            observations = get_obs_for_link_uncached(link, DEFAULT_START_DATE, today)
    else:
        # or if the cache is requested to be reset
        observations = get_obs_for_link_uncached(link, DEFAULT_START_DATE, today)

    # write the data back out to the cache
    if do_update:
        with open(file_name, 'w') as cache_file:
            # convert to string because json can't write otherwise
            jsonible_observations = list(map(lambda x: (x[0], str(x[1])), observations))
            json.dump(jsonible_observations, cache_file)

    # now to actually give the requester what they wanted
    start_index = bs.search(observations, (None, parsed_start_date), key=lambda x: x[1])
    end_index   = bs.search(observations, (None, parsed_end_date),   key=lambda x: x[1])

    # slice all the observations to what the request was
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
        params["$select"]       =  "resultTime,result"
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

    response = req.get(link, params = params).json()
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
