import json
from datetime import datetime
from datetime import timedelta
import numpy as np
import matplotlib
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
import firebase_admin
from firebase_admin import db, credentials
import pytz
from scipy.fft import fft, fftfreq
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
            # tz = pytz.timezone('US/Eastern')
            tz = pytz.timezone('UTC')
            i_dt = tz.localize(i_dt)
            dt.append(i_dt.astimezone(pytz.timezone('US/Eastern')))
        else:
            dt.append(i_dt)
    return np.array(dt)  

def get_time_header():
    return time.strftime('%Y%m%d_%H:%M:%S', time.gmtime(time.time()))

def convert_to_mgl(do, t, p, s=0):
    '''
    do: dissolved oxygen in percent saturation
    t: temperature in celcius
    p: pressure in hPa
    s: salinity in parts per thousand
    '''
    T = t + 273.15 #temperature in kelvin
    P = p * 9.869233e-4 #pressure in atm

    DO_baseline = np.exp(-139.34411 + 1.575701e5/T - 6.642308e7/np.power(T, 2) + 1.2438e10/np.power(T, 3) - 8.621949e11/np.power(T, 4))

    Fs = np.exp(-s * (0.017674 - 10.754/T + 2140.7/np.power(T, 2)))

    theta = 0.000975 - 1.426e-5 * t + 6.436e-8 * np.power(t, 2)
    u = np.exp(11.8571 - 3840.7/T - 216961/np.power(T, 2))
    Fp = (P - u) * (1 - theta * P) / (1 - u) / (1 - theta)

    DO_corrected = DO_baseline * Fs * Fp
    DO_mgl = do / 100 * DO_corrected

    return DO_mgl

class pond():

    def __init__(self, name, days=3):
        start = (datetime.now() - timedelta(days)).astimezone(pytz.timezone("UTC")).strftime('%Y%m%d_%H:%M:%S')
        end = datetime.now().astimezone(pytz.timezone("UTC")).strftime('%Y%m%d_%H:%M:%S')
        ref = db.reference('/LH_Farm/pond_' + str(name))
        data = ref.order_by_key().start_at(start).end_at(end).get()
        self.d_dt = to_datetime(data)
        if (len(self.d_dt) > 0):
            final_do = []
            final_temp = []
            final_pressure = []
            init_do = []
            lat = []
            lng = []
            for i in data:
                if (data[i]['type'] == 'manual') and (len(final_do) != 0):
                    final_do.append(data[i]['do'])
                    final_temp.append('nan')
                    final_pressure.append('nan')
                    init_do.append('nan')
                    lat.append('nan')
                    lng.append('nan')

                else:
                    pressure = np.array(data[i]['pressure']).astype('float')
                    do = np.array(data[i]['do']).astype('float')
                    temp = np.array(data[i]['temp']).astype('float')
                    initial_do = int(data[i]['init_do'])
                    if initial_do == 0:
                        initial_do = 0.01

                    #remove 0s from do
                    do = do[do != 0]
                    final_do.append(int(do.mean() / initial_do * 100))
                    final_temp.append(round(temp.mean() * (9/5) + 32, 2))
                    final_pressure.append(np.mean(pressure))
                    #append other variables
                    init_do.append(initial_do)
                    lat.append(float(data[i]['lat']))
                    lng.append(float(data[i]['lng']))
            
            
            self.init_do = np.array(init_do, dtype='float')
            self.lat = np.array(lat, dtype='float')
            self.lng = np.array(lng, dtype='float')
            self.do = np.array(final_do, dtype='float')
            self.temp =np.array(final_temp, dtype='float')
            self.temp_c = (self.temp - 32) * 5 / 9
            self.pressure = np.array(final_pressure, dtype='float')
            self.do_mgl = convert_to_mgl(self.do, self.temp_c, self.pressure)
            self.id = str(name)

    def plot_temp_do(self, mv):
        # Set date format for x-axis labels
        date_fmt = '%m-%d %H:%M'
        # Use DateFormatter to set the data to the correct format.
        date_formatter = mdates.DateFormatter(date_fmt, tz=(pytz.timezone("US/Central")))
        fig, ax1 = plt.subplots(figsize=(8, 5))
        ax1.plot(self.d_dt, self.do_mgl, 'o-', color='r')
        ax1.set_ylabel('mg/l', fontsize=14)
        plt.title('Dissolved Oxygen')
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        ax2 = ax1.twinx()
        ax2.set_ylim(self.do.min(), self.do.max())
        ax2.set_ylabel("% Saturation", fontsize=14)
        plt.savefig("static/graphs/haucs/"+ str(self.id) + "_do_graph.png")
        plt.figure(figsize=(8, 5))
        plt.plot(self.d_dt, self.temp, 'o-',color= 'c')
        plt.ylabel("Water temperature (°F)", fontsize=14)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.savefig("static/graphs/haucs/"+ str(self.id) + "_temp_graph.png")

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
        plt.savefig("static/graphs/egg/egg_eye_1_timeseries.png")

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
        plt.savefig("static/graphs/egg/egg_eye_1_frequency.png")
    
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
        plt.savefig("static/graphs/egg/egg_eye_1_detect.png")

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
        plt.savefig("static/graphs/egg/egg_eye_1_peaks.png")

if __name__ == "__main__":

    app = login("fb_key.json")

    logout(app)
