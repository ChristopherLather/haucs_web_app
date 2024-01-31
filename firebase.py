import json
from datetime import datetime
from datetime import timedelta
import numpy as np
import matplotlib
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
import firebase_admin
from firebase_admin import db
from firebase_admin import credentials
import pytz

import threading
import time


matplotlib.use('agg')

def login(key_dict):
    """
    Start a Firebase Instance

    return: an app instance
    """
    data = json.loads(key_dict)
    cred = credentials.Certificate(data)
    return firebase_admin.initialize_app(cred, {'databaseURL': 'https://haucs-monitoring-default-rtdb.firebaseio.com'})

def logout(app):
    """
    Logout of a Firebase Instance
    """
    firebase_admin.delete_app(app)

def restart_firebase(app, key_dict):
    firebase_admin.delete_app(app)
    time.sleep(10)
    new_app = login(key_dict)
    return new_app

def moving_average(x, n):
    """
    Simple moving average filter
    """
    filter = np.ones(n) / n
    return np.convolve(x, filter, 'same')

def to_datetime(dates, tz_aware=True):
    """
    Standardizes the various types of string datetime formats
    """
    dt = []
    for i in dates:
        i = i.replace('T','_')
        i = i.replace('-','')
        i = i.replace(' ', '_')
        try:
            i_dt = datetime.strptime(i, '%Y%m%d_%H:%M:%S')
        except:
            print(i)
        if tz_aware:
            tz = pytz.timezone('US/Eastern')
            i_dt = tz.localize(i_dt)

        dt.append(i_dt)
    return np.array(dt)

def check_egg_data():
    email_sent = False
    while email_sent is False:
        ref_data = db.reference('/egg_eye_1/data')
        data = dict()
        data['data'] = ref_data.order_by_key().limit_to_last(3).get()
        on = np.array([int(data['data'][i]['on']) for i in data['data']])
        off = np.array([int(data['data'][i]['off']) for i in data['data']])
        v = (on - off)/1024
        
        for datum in v:
            if datum > 0.6:
                print("Triggered an email")
                email_sent = True
                break

        time.sleep(60)
        


class bmass_sensor():

    def __init__(self, name, n):
        ref_data = db.reference('/bmass_' + str(name) + '/data')
        ref_status = db.reference('/bmass_' + str(name) + '/status')
        data = dict()
        data['data'] = ref_data.order_by_key().limit_to_last(n).get()
        data['status'] = ref_status.order_by_key().limit_to_last(n).get()
        self.d_dt = to_datetime(data['data'])
        self.s_dt = to_datetime(data['status'])
        self.on = np.array([int(data['data'][i][1]) for i in data['data']])
        self.off = np.array([int(data['data'][i][0]) for i in data['data']])
        self.g = np.array([int(data['data'][i][2]) for i in data['data']])
        self.battv = np.array([float(data['status'][i]['batt_v']) for i in data['status']])
        self.v = (self.on - self.off)/1024
        self.id = int(name)

    def plot_timeseries(self, mv):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        lower = self.d_dt[-1-mv] - timedelta(days=7)
        upper = self.d_dt[-1-mv]

        window = (self.d_dt > lower) & (self.d_dt < upper)
        v = moving_average(self.v, mv)[window]

        plt.figure()
        plt.plot(self.d_dt[window], v, color='c')
        plt.ylabel("$\Delta $ Diode Voltage (V)", fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/biomass/"+ str(self.id) + "_bmass_diff.png")

class egg_sensor():

    def __init__(self, n):
        ref_data = db.reference('/egg_eye_1/data')
        data = dict()
        data['data'] = ref_data.order_by_key().limit_to_last(n).get()
        self.d_dt = to_datetime(data['data'])
        self.on = np.array([int(data['data'][i]['on']) for i in data['data']])
        self.off = np.array([int(data['data'][i]['off']) for i in data['data']])
        self.v = (self.on - self.off)/1024
        self.id = 'egg'

    def plot_timeseries(self, mv):
        date_fmt = '%m-%d %H:%M'
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        lower = self.d_dt[-1-mv] - timedelta(days=1)
        upper = self.d_dt[-1-mv]

        #potentially learn & use a different smoothing algorithm??
        window = (self.d_dt > lower) & (self.d_dt < upper)
        v = moving_average(self.v, mv)[window]

        plt.figure()
        plt.plot(self.d_dt[window], v, color='c')
        plt.ylabel("$\Delta $ Diode Voltage (V)", fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/biomass/egg_eye_1_diff.png")

class pond():

    def __init__(self, name, n):
        ref = db.reference('/LH_Farm/pond_' + str(name))
        data = ref.order_by_key().limit_to_last(n).get()
        final_pressure=[]
        final_do = []
        final_temp = []

        for i in data:
            pressure = data[i]['pressure']
            do = data[i]['do']
            temp = data[i]['temp']
            high_pressure = max(pressure)
            index_hp = pressure.index(high_pressure)
            final_pressure.append(pressure[index_hp])
            final_do.append(do[index_hp])
            final_temp.append(temp[index_hp])
        
        self.d_dt = to_datetime(data)
        self.heading = np.array([(data[i]['heading']) for i in data], dtype='float')
        self.init_do = np.array([(data[i]['init_do']) for i in data], dtype='int')
        self.init_pressure = np.array([(data[i]['init_pressure']) for i in data], dtype='float')
        self.lat = np.array([(data[i]['lat']) for i in data], dtype='float')
        self.lng = np.array([(data[i]['lng']) for i in data], dtype='float')
        self.pressure = np.array(final_pressure, dtype='float')
        self.do = (np.array(final_do, dtype='int') / self.init_do * 100).round()
        self.temp = (np.array(final_temp, dtype='float'))*(9/5)+32
        self.id = int(name)

    def plot_temp_do(self, mv):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        lower = self.d_dt[-1] - timedelta(hours=24)

        window = self.d_dt > lower
        data_pts = np.count_nonzero(window)

        if data_pts < mv:
            mv=data_pts
        print(self.d_dt[window])
        plt.figure(figsize=(12,5))
        plt.subplot(1,2,1)
        # plt.plot(self.d_dt[window],moving_average(self.do[window],mv), 'o-',color='r')
        plt.plot(self.d_dt[window], self.do[window], 'o-', color='r')
        # plt.scatter(self.d_dt[window],self.do[window], color='r')
        plt.ylabel('Dissolved Oxygen (%)', fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.subplot(1,2,2)
        # plt.plot(self.d_dt[window], moving_average(self.temp[window],mv), 'o-',color= 'c')
        plt.plot(self.d_dt[window], self.temp[window], 'o-',color= 'c')
        plt.ylabel("Water temperature (°F)", fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/haucs/"+ str(self.id) + "_temp_do_graph.png")
    
if __name__ == "__main__":

    app = login("fb_key.json")

    logout(app)
