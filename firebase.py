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
from scipy.fft import fft, fftfreq

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
    return np.convolve(x, filter, 'valid')

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
        self.v = 3.3 * (self.on - self.off)/1023
        self.id = int(name)

    def plot_timeseries(self, mv):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        lower = self.d_dt[-1] - timedelta(days=7)

        window = (self.d_dt > lower)
        v = moving_average(self.v[window], mv)

        plt.figure()
        plt.plot(self.d_dt[window][mv - 1 :], v, color='c')
        plt.ylabel("$\Delta $ Diode Voltage (V)", fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/biomass/"+ str(self.id) + "_bmass_diff.png")

class egg_sensor():

    def __init__(self, n):
        fref = db.reference('/egg_eye_1/fdata')
        aref = db.reference('/egg_eye_1/adcdata')
        data = dict()
        data['fdata'] = fref.order_by_key().limit_to_last(n).get()
        data['adata'] = aref.order_by_key().limit_to_last(n).get()
        self.d_dt = to_datetime(data['fdata'])
        self.current_time = datetime.now().astimezone(pytz.timezone("US/Eastern")).strftime('%I:%M %p')
        self.id = 'egg'
        self.data = data
        self.keys = list(data['adata'].keys())

    def plot_timeseries(self):
        x = np.arange(200) / 40 #this probably shouldnt be hard coded
        yf = np.array(self.data['fdata'][self.keys[-1]]['data']).astype('int')
        ya = np.array(self.data['adata'][self.keys[-1]]['data']).astype('float')
        
        plt.figure()
        plt.subplot(2,1,1)
        plt.title('Timeseries Sample')
        plt.ylabel("bmass")
        plt.plot(x, yf)
        plt.subplot(2,1,2)
        plt.ylabel("turbidity")
        plt.xlabel("time (seconds)")
        plt.plot(x, ya, color='r')
        plt.savefig("static/graphs/biomass/egg_eye_1_timeseries.png")

    def plot_frequency(self):
        N = 512 # make a multiple of 2
        fs = 40
        freq_range = fftfreq(N, 1 / fs)[:N//2]
        yf = np.array(self.data['fdata'][self.keys[-1]]['data']).astype('int')
        yf = yf / yf.max()
        ya = np.array(self.data['adata'][self.keys[-1]]['data']).astype('float')
        ya = ya / ya.max()
        fft_f = np.abs(fft(yf, N)[:N//2])
        fft_a = np.abs(fft(ya, N)[:N//2])

        plt.figure()
        plt.subplot(2,1,1)
        plt.title("Frequency Sample")
        plt.ylabel("bmass")
        plt.ylim(top=80)
        plt.plot(freq_range, fft_f)
        plt.subplot(2,1,2)
        plt.ylabel("turbidity")
        plt.ylim(top=80)
        plt.xlabel("Hz")
        plt.plot(freq_range, fft_a, color='r')
        plt.savefig("static/graphs/biomass/egg_eye_1_frequency.png")
    
    def plot_prediction(self):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        start = (datetime.now() - timedelta(days=1)).astimezone(pytz.timezone("US/Eastern")).strftime('%Y%m%d_%H:%M:%S')
        end = datetime.now().astimezone(pytz.timezone("US/Eastern")).strftime('%Y%m%d_%H:%M:%S')

        fdata = db.reference('/egg_eye_1/fdetect/').order_by_key().start_at(start).end_at(end).get()
        adata = db.reference('/egg_eye_1/adetect/').order_by_key().start_at(start).end_at(end).get()

        dt = to_datetime(list(fdata.keys()))

        #convert text
        fy = ['eggs' if i == 'outlier' else 'no eggs' for i in list(fdata.values())]
        ay = ['eggs' if i == 'outlier' else 'no eggs' for i in list(adata.values())]
        plt.figure(figsize=(7,5))
        plt.subplot(2,1,1)
        plt.plot(dt, fy)
        plt.title("Detection Algorithm")
        plt.ylabel('bmass')
        plt.subplot(2,1,2)
        plt.plot(dt, ay, color='r')
        plt.ylabel("turbidity")
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/biomass/egg_eye_1_detect.png")

    def plot_peakDetection(self):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Eastern")))
        start = (datetime.now() - timedelta(days=1)).astimezone(pytz.timezone("US/Eastern")).strftime('%Y%m%d_%H:%M:%S')
        end = datetime.now().astimezone(pytz.timezone("US/Eastern")).strftime('%Y%m%d_%H:%M:%S')

        data = db.reference('/egg_eye_1/apeak/').order_by_key().start_at(start).end_at(end).get()

        keys =  list(data.keys())
        dt = to_datetime(keys)
 
        peaks = []
        for i, k in enumerate(keys):
            peaks.append(int(data[k]))

        plt.figure()
        plt.scatter(dt, peaks, color='r')
        plt.plot(dt[9:], moving_average(peaks, 10), color='orange', alpha=1)
        plt.title('Turbidity Peak Detector')
        plt.ylabel("Number of Peaks")
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/biomass/egg_eye_1_peaks.png")



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
