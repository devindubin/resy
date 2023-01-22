from dotenv import load_dotenv

load_dotenv()
import os
import requests
import datetime
from urllib.parse import urljoin, quote
import pandas as pd
import logging
#import time

logging.basicConfig(filename='resy.log',level=logging.DEBUG,format=' %(name)s :: %(levelname)-8s :: %(funcName)s ::%(message)s',filemode='w')

# TODO: Clean up argument defaults

STAGING = False
if STAGING:
    BASE_URL = os.getenv("STAGING_URL")
    API_KEY = os.getenv("STAGING_API_KEY")
else:
    BASE_URL = os.getenv("PRODUCTION_URL")
    API_KEY = os.getenv("PRODUCTION_API_KEY")
EMAIL = os.getenv("EMAIL_UN")
PW = os.getenv("PW")
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))


def authenticate(*args, **kwargs):
    url_ext = "/3/auth/password"
    url = urljoin(BASE_URL, url_ext)

    with requests.Session() as s:
        required_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f'ResyAPI api_key="{API_KEY}"',
        }

        s.headers.update(required_header)

        params = {"email": EMAIL, "password": PW}

        response = s.post(url=url, data=params)

        if response.status_code == 200:
            token = response.json().get("token")
            xResyAuthToken = {"X-Resy-Auth-Token": token}
            required_header.update(xResyAuthToken)
            return {"header": required_header}
        else:
            raise Exception((response.text,response.status_code))


def auth(func):
    def inner(*args, **kwargs):
        header = authenticate()

        return func(authheader=header, *args, **kwargs)

    return inner


@auth
def get_venues(
    lat="40.7113",
    long="-74.0077",
    day=datetime.datetime.today(),
    party_size=2,
    venue_id=None,
    limit=None,
    bookmark=None,
    *args,
    **kwargs,
):
    params = {
        "lat": lat,
        "long": long,
        "day": day.strftime("%Y-%m-%d"),
        "party_size": party_size,
        "venue_id": venue_id,
        "limit": limit,
        "bookmark": bookmark,
    }
    required_headers = kwargs.get("authheader")
    print(params)
    with requests.Session() as s:
        url = urljoin(BASE_URL, "4/find")
        s.headers.update(required_headers.get("header"))
        response = s.get(url=url, params=params)
        if response.ok:
            return {"code": response.status_code, "data": response.json()}
        else:
            raise Exception(response.text)


@auth
def get_details(config_id=None, day=None, party_size=None, *args, **kwargs):
    params = {"config_id": config_id, "day": day.strftime("%Y-%m-%d"), "party_size": party_size}
    required_headers = kwargs.get("authheader")
    logging.info(params)
    with requests.Session() as s:
        url = urljoin(BASE_URL, "/3/details")
        s.headers.update(required_headers.get("header"))
        # urljoin(url,params.get('party_size'),params.get('day'),params.get('config-id'))
        response = s.get(url=url, params=params)

        if response.status_code == requests.codes.ok:
            return {"code": response.status_code, "data": response.json()}
        else:
            raise Exception(response.text)


@auth
def book_reservation(book_token: str = None, *args, **kwargs):
    token = f"book_token={quote(book_token)}"
    required_headers = kwargs.get("authheader")

    with requests.Session() as s:
        url = urljoin(BASE_URL, "/3/book")
        s.headers.update(required_headers.get("header"))
        # s.headers.update({'Content-Type':'multipart/form-data'}) #Book Reservation endpoint requires multipart/form-data content type for some reason

        response = s.post(url=url, data=token.encode())
        print(response.status_code)
        if response.ok:
            return {"code": response.status_code, "data": response.json()}
        else:
            raise Exception(response.status_code, response.text)


@auth
def cancel_reservation(resy_token: str = None, *args, **kwargs):
    token = f"resy_token={quote(resy_token)}"
    required_headers = kwargs.get("authheader")

    with requests.Session() as s:
        url = urljoin(BASE_URL, "/3/cancel")
        s.headers.update(required_headers.get("header"))
        response = s.post(url=url, data=token.encode())

        if response.ok:
            return {"code": response.status_code, "data": response.json()}
        else:
            raise Exception(response.text)


@auth
def change_reservation(book_token: str = None, resy_token: str = None, *args, **kwargs):
    data = {"book_token": book_token, "resy_token": resy_token}
    required_headers = kwargs.get("authheader")

    with requests.Session() as s:
        url = urljoin(BASE_URL, "/3/change")
        s.headers.update(required_headers.get("header"))
        response = s.post(url=url, data=data)

        if response.status_code == requests.codes.ok:
            return {"code": response.status_code, "data": response.json()}
        else:
            raise Exception(response.text)


def find_no_cancellation_fee(restaurants: list = None):
    tests = []
    for place in restaurants:
        if (
            "payment_cancellation_fee"
            in place.get("slots").dropna(how="all", axis=1).columns
        ):
            print("Fee", place.get("name"))

        else:
            print("No Fee", place.get("name"))
            tests.append(place)
    return tests


def snipe(
    venue_id: str = None,
    dateTime: datetime.datetime = None,
    party_size: int
     = None,
    allowed_types: list = ['Private','Communal'],
    confirmation = True
):
    FOUND = False
    BOOKED = False
    BOOKEDDETAILS = {}
    notif_for_scan = {'found':FOUND,'booked':BOOKED, 'details': BOOKEDDETAILS,'reservation_details':{}}
    try:
        #day = dateTime.strftime("%Y-%m-%d")
        output = get_venues(venue_id=venue_id, day=dateTime)
        venues = output.get('data').get('results').get('venues')
    except Exception as e:
        logging.error(e)
        raise e

    out = []
    for venue in venues:
        
        venue_info = venue.get("venue")
        venue_name = venue_info.get("name")
        venue_location = venue_info.get("location")
        venue_id = venue_info.get("id").get("resy")

        slots = venue.get("slots")
        if slots:
            slots_df = pd.DataFrame(slots)
            slots_df_1 = pd.concat(
                [
                    slots_df,
                    slots_df["config"].apply(
                        lambda x: pd.Series(x).add_prefix("config_")
                    ),
                ],
                axis=1,
            )
            slots_df_2 = pd.concat(
                [
                    slots_df_1,
                    slots_df_1["date"].apply(
                        lambda x: pd.Series(x).add_prefix("date_")
                    ),
                ],
                axis=1,
            )
            slots_df_3 = pd.concat(
                [
                    slots_df_2,
                    slots_df_2["payment"].apply(
                        lambda x: pd.Series(x).add_prefix("payment_")
                    ),
                ],
                axis=1,
            )
            slots_df_3["resyId"] = venue_id
            slots_df_4 = pd.concat(
                [
                    slots_df_3,
                    slots_df_3["size"].apply(
                        lambda x: pd.Series(x,dtype=int).add_prefix("size_")
                    ),
                ],
                axis=1,
            )
        else:
            slots_df_4 = pd.DataFrame()
        # slots_df_4 = pd.concat([slots_df_3,slots_df_3['config_token'].apply(lambda x: pd.Series(re.findall(r"(?<=resy/)\d+",x),index=['resyId']))],axis=1)
        out.append(
            {
                "name": venue_name,
                "id": venue_id,
                "location": venue_location,
                "slots": slots_df_4,
            }
        )


    place = out.pop()
    slots = place.get('slots')
    
    if not slots.empty:
        slots["date_start"] = pd.to_datetime(slots["date_start"])
        print(dateTime + datetime.timedelta(minutes=-30))
        print(dateTime + datetime.timedelta(minutes=30))
        valid_slots = slots[
            (slots["size_min"] <= party_size)
            & (slots["size_max"] >= party_size)
            & (
                (slots["date_start"] >= dateTime + datetime.timedelta(minutes=-30))
                & (slots["date_start"] <= dateTime + datetime.timedelta(minutes=30))
            ) & (
                slots['config_type'].isin(allowed_types)
            )
        ]
    else:
        logging.info('No slots found')
        return notif_for_scan

    valid_slots=valid_slots.reset_index(drop=True)
    print(len(valid_slots))
    if len(valid_slots) >= 1:
        #Take first valid configuration
        reservation = valid_slots.loc[0]
        notif_for_scan['found'] = True
    else:
        logging.info("No Slots Meet Criteria")
        logging.info(slots.to_string())
        reservation = None
        return notif_for_scan

    print(FOUND)
    print(notif_for_scan)
    config_token = reservation.get('config_token')

    details = get_details(config_id=config_token,day=dateTime,party_size=party_size)

    

    detail_data = details.get('data')
    book_token = detail_data.get('book_token')
    
    print(detail_data.get('cancellation').get('display').get('policy'))
    if confirmation:
        res = input("Proceed with booking? y/N")
    else:
        res = 'y'
    if res.lower()[0] == 'y':
        try:
            booked_details = book_reservation(book_token=book_token.get('value'))
            notif_for_scan["booked"] = True
            notif_for_scan["reservation_details"] = booked_details
            notif_for_scan['details'] = detail_data
            
        except Exception as e:
            logging.error('Booking Failed')
            return notif_for_scan
    else:
        logging.info('Booking cancelled')
        return notif_for_scan
    logging.info('Booking Successful')
    return notif_for_scan

def scan(venue_id: str = None,party_size:int = 2,day= NOW,allowed_types=['Private','Communal','The Bar Room'],confirmation=True,max_attempts=None, delay = 1):
    logging.info('Starting Scan')
    TRY_AGAIN = True
    if max_attempts:
        i = 0
    while TRY_AGAIN:
        notif_for_scan = snipe(venue_id=venue_id,dateTime=day,party_size=party_size,allowed_types=allowed_types,confirmation=confirmation)
        print(notif_for_scan)
        if notif_for_scan.get('found'):
            TRY_AGAIN = False
            if notif_for_scan.get('booked'):
                logging.info('Reservation booked!')
                logging.info(notif_for_scan.get('details'))
                return {'retry':TRY_AGAIN,'details': notif_for_scan}
            else:
                logging.info('Error booking reservation, scanning stopped. Please check logs')
                return {'retry':TRY_AGAIN,'details': notif_for_scan}
        else:
            if i == max_attempts - 1:
                logging.info('Hit max attempts, shutting down')
                TRY_AGAIN = False
                return 
            print('Nothing Found, Trying Again')
            logging.info('Nothing Found. Trying again')
            logging.info({'retry':TRY_AGAIN,'details':notif_for_scan})
            i += 1
            time.sleep(delay*60)
            continue

