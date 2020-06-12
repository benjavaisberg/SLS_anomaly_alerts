import pymongo
from pymongo import MongoClient
import private_config


def mongodb_connection():
    try:
        client = MongoClient(private_config.DB_URI)
        db = client.test  # db name: test
    except pymongo.errors.ConnectionFailure as e:
        print("Could not connect to server: %s" % e)
    return db
