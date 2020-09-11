# SLS_anomaly_alerts
## Introduction
If you are reading this, you hopefully know about the [sea level sensors project](https://www.sealevelsensors.org/). At the time of this writing, the sls project was just beginning to get good data, but there were some sensors that were still causing issue. In addition, there was no real way to know if anything "interesting" was going on with the water levels aside from clicking through each sensor individually and examining it visually.

The purpose of our project was to create a programatic way to flag "interesting events". These events include both issues with the sensor and weather related issues. While our algorithm flags these events, it leaves it up to the user to determine what kind of events they are and what action should be taken.

**[Model explanation](https://docs.google.com/document/d/19SrmgpOm4aGNnZ0fbpc6kFA3_RETxNzuNxykFA1-SjU/edit?usp=sharing)**
## Usage
This project has two end products: An email alert system and a website. Both are coupled and ran together (although they can be ran semi-individually if preferred).
### Email alerts
If you run daily_controller.py it will perform a variety of analysis on each of the sensors, save the data, and then send an email to the recipients in private_config.py detailing interesting sensors. This file is intended to be run daily. (and will be automatically by the gunicorn server)
### Website
run website.py to show our interactive data visualization website. A server like gunicorn can be used with the included config if the website is intended to be displayed public facing. 

It is highly recommended to give this website as many cores as possible (the speed of these cores does not matter)

**NOTE: The website has a feature that highlights anomalous sensors. This feature will not work if daily_controller.py is not run every night. The gunicorn config includes code to do this automatically**
## Docker
this project has an included Dockerfile. Docker is the intended way to use this project. Copy private_config_example.py to private_config.py and fill it out. Then install docker and run
```
sudo docker build --tag=anomalyserver .
sudo docker run -p 8000:8000 anomalyserver
```
(-p binds your computers port 8000 to the gunicorn server's port 8000)

Optional: If you follow the above instructions you will build a image which will then build its own cache. This can take a long time, which can be irritating if you keep making small changes and then having to rebuild. You can instead pre-build a cache by running daily_controller.py and then building your docker image. Then, small code changes can be rebuilt without needing to wait an hour each time
## For future developers
### api_scraper.py
This file contains a variety of methods that make using the api easier. Useful to probably any developer.
### config.py
a config where you can define thresholds for when a sensor is "interesting". 
### emailer.py
file containing code that actually sends the emails
### analysis.py
In very broad strokes: The code in this file grabs data from every sensor, fits the fort pulaski predictions onto that data, and sees how much a sensor deviates from the ft. pulaski predictions (if the deviation is too high, the sensor is flagged as "interesting"). We also considered fitting a sine wave onto the sensors, but ran into some problems there.
The data is fetched from the API and stored in MongoDB to act as a cache. Data is fetched from the DB first, if the data is stale then it fetches the API for new data and overwrites the DB.

Unfortunately some of the code in analysis.py is inflexible, hardcoded to only really be able to run the tests for 1 hour, 1 day, 3 days. If you would like to use this code for your own analysis however, many of the helper functions are perfectly flexible and usable for other analysis purposes. 
