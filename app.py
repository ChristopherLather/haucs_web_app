from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import firebase
import json
import os
from firebase_admin import db

#create folder structure
if not os.path.exists('static/graphs'):
    os.mkdir('static/graphs')
if not os.path.exists('static/graphs/eggs'):
    os.mkdir('static/graphs/eggs')
if not os.path.exists('static/graphs/haucs'):
    os.mkdir('static/graphs/haucs')
if not os.path.exists('static/graphs/biomass'):
    os.mkdir('static/graphs/biomass')

fb_key = os.getenv('fb_key')

if fb_key:
    print("running in deployment mode")
    deployed = True
else:
    print("running in debug mode")
    deployed = False
    with open('fb_key.json', 'r') as file:
        fb_key = file.read()

#login to firebase
fb_app = firebase.login(fb_key)


def get_all_battv():
    """
    Get the latest battery voltages for all biomass sensors
    TODO: THIS IS HARDCODED
    """
    last_battv=dict()
    for i in range(1, 6):
        bmx = firebase.bmass_sensor(i, 1)
        last_battv[bmx.id] = bmx.battv[-1]

    return last_battv

def get_all_do():
    """
    Get latest dissolved oxygen values for all ponds
    """
    last_do = dict()
    data = db.reference('/LH_Farm/overview').get()

    for i in data:
        idx = i.split('_')[-1]
        last_do[idx] = data[i]['last_do']

    return last_do


app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/biomass')
def bmass():
    last_battv = get_all_battv()
    with open('static/json/tanks_features.json', 'r') as file:
        data = file.read()

    return render_template('biomass.html', data=data,battv=json.dumps(last_battv))

'''
Data Source: call this from javascript to get fresh data
'''
@app.route('/data/' + '<ref>', methods=['GET'])
def data(ref):
    db_path = ref.split(' ')
    db_path = "/".join(db_path)
    data = db.reference(db_path).get()
    return jsonify(data)

'''
Data Source: call this from javascript to get fresh data in given time range
'''
@app.route('/dataTime/' + '<ref>', methods=['GET'])
def dataTime(ref):
    variables = ref.split(' ')
    db_path = "/".join(variables[:-2])
    start = variables[-2]
    end = variables[-1]
    data = db.reference(db_path).order_by_key().start_at(start).end_at(end).get()
    return jsonify(data)

@app.route('/drone')
def drone_list():
    data = db.reference('/LH_Farm/drone').get()
    keys = list(data.keys())
    keys.sort(key=str.lower)
    return render_template('drone_list.html', keys=keys)

@app.route('/drone/'+'<drone_id>')
def drone(drone_id):
    return render_template('drone.html', id=drone_id)

@app.route('/eggs')
def eggs():
    egg = firebase.egg_sensor(800)
    last_dt = egg.d_dt[-1]
    str_date = last_dt.strftime('%A, %B %d')
    str_time = last_dt.strftime('%I:%M %p')
    current_time = egg.current_time
    egg.plot_timeseries()
    egg.plot_frequency()
    egg.plot_prediction()
    egg.plot_peakDetection()
    return render_template('eggs.html',  last_date=str_date, last_time=str_time, last_refresh = current_time)

@app.route('/feedback', methods=['POST', 'GET'])
def feedback():
    if request.method == 'POST':
        msg_time = firebase.get_time_header()
        #handle comment requests
        if request.values.get('comment'):
            comment = request.values.get('comment')
            db.reference('/LH_Farm/comments/' + msg_time + '/').set(comment)
        #handle manual do inputs
        elif request.values.get('pond'):
            pond_id = "pond_" + request.values.get('pond')
            do = request.values.get('do')
            do = do.replace("%", "")
            try:
                do = int(do)
                db.reference("/LH_Farm/overview/" + pond_id + "/last_do/").set(do)
                data = {'type':'manual', 'do':do}
                db.reference("/LH_Farm/" + pond_id + "/" + msg_time + "/").set(data)
            except:
                print("cannot  convert")
            
    return render_template('feedback.html')

@app.route('/HAUCS')
def haucs():
    last_do = get_all_do()
    with open('static/json/farm_features.json', 'r') as file:
        data = file.read()
    
    return render_template('HAUCS.html', data=data, do_values=json.dumps(last_do))

@app.route('/history')
def history():
    with open('static/json/farm_features.json', 'r') as file:
        data = file.read()
    
    return render_template('history.html', data=data)

@app.route('/pond'+'<pond_id>')
def show_pond(pond_id):
    days = 2
    pondx = firebase.pond(pond_id, days)
    last_do = 0
    last_do_mgl = 0
    last_temp = 0
    str_date = f"NO DATA FROM PAST {days} DAYS"
    if (len(pondx.d_dt) > 0):
        pondx.plot_temp_do(mv=10)
        last_do = round(pondx.do[-1],2)
        last_do_mgl = round(pondx.do_mgl[-1], 2)
        last_temp = round(pondx.temp[-1],2)
        last_dt = pondx.d_dt[-1]
        str_date = last_dt.strftime('%m/%d %I:%M %p')
    return render_template('haucs_analytics.html', pond_id=pond_id, last_date=str_date, last_do=last_do, last_do_mgl=last_do_mgl, last_temp=last_temp)

@app.route('/recent')
def recent():
    data = db.reference("/LH_Farm/recent").get()
    return render_template('haucs_recent.html', keys=reversed(data.keys()), data=data)

@app.route('/sensor'+'<int:sensor_id>')
def show_sensor(sensor_id):
    bmx = firebase.bmass_sensor(sensor_id, 600)
    last_battv = bmx.battv[-1]
    last_dt = bmx.s_dt[-1]
    str_date = last_dt.strftime('%A, %B %d')
    str_time = last_dt.strftime('%I:%M %p')
    bmx.plot_timeseries(mv=10)
    return render_template('tanks_analytics.html', sensor_id=sensor_id, last_date=str_date, last_time = str_time, last_battv=last_battv, last_dt=last_dt)

if __name__ == "__main__":
    if not deployed:
        app.run(debug=True)

    
