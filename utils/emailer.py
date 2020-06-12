import config as conf
import yagmail
from yagmail import inline
from datetime import date
from pprint import pprint as print
import os
import pandas as pd
try:
    import private_config as p_conf
except ModuleNotFoundError:
    print("No private_config found!")
    print("copy private_config_example.py to private_config.py and fill it out")
    print("DO NOT ADD YOUR PRIVATE_CONFIG TO VERSION CONTROL")
    exit()

def daily_mail(send=True):
    """
    Send mail about the days interesting sensors
    intended to be run daily
    """
    params                 = {}
    params["to"]           = p_conf.TO_LIST
    params["subject"]      = f"{date.today()} anomaly updates"
    params["contents"]     = list_anomalous_sensors()
    params["attachments"]  = [conf.CSV_OUTFILE]
    params["attachments"] += get_all_pngs()
    if send:
        with yagmail.SMTP(p_conf.USERNAME, p_conf.PASSWORD) as sender:
            sender.send(**params)
    else:
        print(params)

def get_all_pngs():
    """gets the name of every png in the 'images' folder"""
    try:
        return list(
               map(lambda x: "./images/" + x,
                   filter(lambda x: '.png' in x,
                          os.listdir('../images/'))))
    except FileNotFoundError:
        return []

def list_anomalous_sensors():
    """creates email text discussing which sensors are flagged"""
    sensors = pd.read_csv(conf.CSV_OUTFILE)
    sens_1_hour  = sensors[sensors["flag_1hour"]]
    sens_1_day   = sensors[sensors["flag_1day"]]
    sens_3_day   = sensors[sensors["flag_3days"]]
    sens_min_val = sensors[sensors["flag_min_vals"]]
    def message_for_sensor(sensor):
        return ("{} ({})".format(sensor["desc"], sensor["name"])
                if not sensor.empty
                else "This value is thrown away by pandas")
    return (["<font size=\"4\"><b>Sensors flagged for an hour-long event</b></font>"] + 
            list(sens_1_hour.apply(message_for_sensor, axis=1)) + 
            ["<font size=\"4\"><b>Sensors flagged for a day long event</b></font>"] + 
            list(sens_1_day.apply(message_for_sensor, axis=1)) + 
            ["<font size=\"4\"><b>Sensors flagged for a 3 day long event</b></font>"] + 
            list(sens_3_day.apply(message_for_sensor, axis=1)) + 
            ["<font size=\"4\"><b>Sensors flagged for having too few values</b></font>"] + 
            list(sens_min_val.apply(message_for_sensor, axis=1)))

##
if __name__ == "__main__":
    daily_mail()
