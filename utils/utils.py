import datetime
import dateutil.parser as date_parser
from dateutil.tz import tzutc
import pytz


# Date parser helper function
def utcparse(date):
    return date_parser.parse(date).replace(tzinfo=tzutc())

def make_aware_date(date):
    return date.replace(tzinfo=tzutc())

def remove_tzinfo(date):
    return date[:-6]