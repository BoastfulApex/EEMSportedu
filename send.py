import requests
import time
import random
from apscheduler.schedulers.blocking import BlockingScheduler
import datetime
from data import config


def send_message(data):
    bottoken = "5599692359:AAEn8-k3t2kFoTLvGEPrqiMumB77VcrNGOI"
    url = "https://api.telegram.org/bot" + bottoken + "/sendMessage"
    res = requests.post(url=url, headers={}, files=data)
    

def send():
    if datetime.datetime.now().minute == 30:
        data = {
            'text': (None, f'SendPostNotification'),
            'chat_id': (None, -1001958087778),
            'parse_mode': (None, 'Markdown')}
        send_message(data)

import pytz
tashkent_tz = pytz.timezone("Asia/Tashkent")

scheduler = BlockingScheduler(timezone=tashkent_tz)
scheduler.add_job(send, "cron", hour=21, minute=30)
scheduler.start()