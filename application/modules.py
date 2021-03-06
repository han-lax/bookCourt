import json
import time
from urllib.parse import urlencode
import ntplib
import requests
import datetime as dt

from application.utils import get_key, cryptCBCPkcs7


def resolveInfo(params):
    if params['success']:
        return "场地信息如下："
    else:
        return params['errMsg']


class Features:
    def __init__(self, myToken, config):  # init with host and token

        self.token = myToken
        self.headers = config['basicHeaders']
        self.host = config['host']
        self.periodIdList = config['periodIdList']
        self.stadiumIdList = config['stadiumIdList']
        self.time = config['time']

    def cancelCourt(self):  # you can try to cancel the booking with this function
        data, _ = self.getPriLogs()
        stadiumId = data['data'][0]['id']  # the id of the latest court booking
        params = {"logId": str(stadiumId)}  # request params
        params = json.dumps(params)

        url = self.host + "/user/cancel"  # url to which cancel request post
        headers = self.headers
        headers.update({"Token": self.token, "Content-Type": "application/x-www-form-urlencoded"})  # request headers

        s = requests.post(url, params, headers=headers)  # response information
        return s.json

    def bookBadminton(self, p):  # try to book a Badminton court
        today = '{:%Y-%m-%d}'.format(dt.datetime.now())  # the date today
        # request params including the id and the time you want to book
        params = {"periodId": p[0], "date": today, "stadiumId": p[1]}
        params = json.dumps(params)
        url = self.host + "/user/book"  # url to which book request post

        # time and signature time when request sends
        timestamp, timestampSignature = ConfigureTime(self.time).getTimeVerify()
        headers = self.headers
        headers.update({"token": self.token, "Resultjson": timestamp, "Content-Type": "application/json",
                        "Resultjsonsignature": timestampSignature, "Content-Length": "49"})  # request headers

        # print("数据提交时间：", dt.datetime.now())  # print the time when the request sends
        s = requests.post(url, params, headers=headers)  # response information including the result of booking
        return s.json()

    def getPriLogs(self):  # get the latest booking info
        # limit param means only return the latest booking info
        params = {"containCanceled": "false", "desc": "true", "limit": "1", "offset": "0"}
        params = json.dumps(params)
        url = self.host + "/user/getPriLogs"  # url to which query request post

        headers = self.headers
        # request headers
        headers.update({"token": self.token, "Content-Type": "application/json"})

        s = requests.post(url, params, headers=headers).json()
        # print(s)

        # resolve the serial number of the court from the response info
        court = get_key(self.stadiumIdList, str(s["data"][0]["stadiumId"]))[0]
        infoSum = "The latest:\n" + court + '\n' + s['data'][0]['period'] + '\n' + s['data'][0]['date']
        return s, infoSum

    def bookCourt(self, params):  # countdown and then book
        info = ""
        postTime = None
        _, _, _, t_delay = self.time  # get delay microseconds
        ct = ConfigureTime(self.time)
        ct.countTo2()  # countdown to last 2 min
        params = [self.periodIdList[params[0]], self.stadiumIdList[params[1]]]

        flag = True
        # countdown to the timing time
        while flag:
            time.sleep(0.989)
            # print(getLocalInterval(rt, de))
            if ct.getLocalInterval() <= 3:
                while flag:
                    # time.sleep(0.003)
                    # print(getLocalInterval(ringTime, de))
                    if ct.getLocalInterval() <= t_delay:
                        postTime = time.time()
                        info = self.bookBadminton(params)
                        # print("数据返回时间：", dt.datetime.now())
                        # print(info)
                        flag = False

        # print the latest booked court after 5 sec
        time.sleep(5)

        ntpTime, _ = ct.getNtpTime()
        relTime = ntpTime.tx_time + ntpTime.delay / 2 - (time.time()-postTime)

        info = ct.styledTime(relTime, False) + '\n' + resolveInfo(info)
        _, info2 = self.getPriLogs()
        return info2, info

    def getToken(self):
        params = {
            # "code": "033iBAml27M8g94VYDll2B9KQW2iBAmL"
        }
        params = urlencode(params)
        url = self.host + "/auth/?code=073Aij000Ot2VN1ZN2000CbmYt1Aij0x"

        headers = self.headers
        headers.update({"Content-Type": "application/x-www-form-urlencoded"})

        s = requests.post(url, data=params, headers=headers)
        print(s.json())


class ConfigureTime:
    def __init__(self, myTime):  # init the delay with 0 and the timing time
        self.delay = 0
        self.time = myTime
        self.timingTime = self.setTime()

    def countTo2(self):  # countdown to last 2 min
        self.getTimeDelay()
        flag = True
        while flag:
            if self.getLocalInterval() > 120:
                time.sleep(60)
            else:
                flag = False
        self.getTimeDelay()

    def getTimeDelay(self):  # get delay between local time and server time
        timeDelay = 0

        # take the average of ten items as delay
        for i in range(10):
            ntpClient = ntplib.NTPClient()
            times = ntpClient.request("edu.ntp.org.cn", version=2)  # get the server time from the china education web

            timeDelay += times.tx_time + times.delay / 2 - time.time()

        self.delay = timeDelay / 10
        return self.delay

    def getInterval(self):  # get time interval between server time and timing time
        ntpClient = ntplib.NTPClient()
        interval = self.timingTime - ntpClient.request("edu.ntp.org.cn", version=2, timeout=3).tx_time
        return interval

    def getLocalInterval(self):  # get the time interval between local time and timing time but within delay
        localTimestamp = time.time()
        interval = self.timingTime - localTimestamp - self.delay
        return interval

    def setTime(self):  # get the timestamp of the timing time
        th, tm, ts, _ = self.time

        today = "{:%Y-%m-%d}".format(dt.datetime.now())

        tm = tm + 1 if ts == 59 else tm
        th = th + 1 if tm == 60 else th
        ts = ts + 1
        ts = 0 if ts == 60 else ts
        tm = 0 if tm == 60 else tm

        ret_hour = str(th)
        ret_min = '0' + str(tm) if tm <= 9 else str(tm)
        ret_sec = '0' + str(ts) if ts <= 9 else str(ts)

        ret = today + ' ' + ret_hour + ':' + ret_min + ':' + ret_sec
        ret = time.strptime(ret, '%Y-%m-%d %H:%M:%S')
        return time.mktime(ret)

    def styledTime(self, t, local=True):
        if local:
            t = t + self.delay
        tmp = time.localtime(t)
        tmp = time.strftime('%Y-%m-%d %H:%M:%S', tmp)

        st = tmp + ' ' + str(round(t % 1 * 1000))

        return st

    @staticmethod
    def getTimeVerify():  # get signature value of timestamp when request sends
        key = "6f00cd9cade84e52"
        iv = "25d82196341548ef"
        cryptor = cryptCBCPkcs7(key, iv)

        TS = str(round(time.time() * 1000))
        TSS = cryptor.encrypt(TS).decode()
        return TS, TSS

    @staticmethod
    def getNtpTime():  # just get the server time
        ntpClient = ntplib.NTPClient()
        times = ntpClient.request("edu.ntp.org.cn", version=2)

        localTime = time.localtime(times.tx_time)
        localTime = time.strftime("%Y-%m-%d %H:%M:%S", localTime)
        return times, localTime + str(times.tx_time % 1)
