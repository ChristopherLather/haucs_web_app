import smtplib
from email.mime.text import MIMEText
import firebase
from firebase_admin import db
from firebase_admin import credentials
from datetime import datetime
from datetime import timedelta
import pytz
import schedule
import time

bmass_sensors = [1, 2, 3, 4, 5]

eastern_timezone = pytz.timezone('US/Eastern')

last_egg_alert = datetime.now(eastern_timezone) - timedelta(days = 1)

with open('fb_key.json', 'r') as file:
    fb_key = file.read()

#login to firebase
fb_app = firebase.login(fb_key)

def get_api_key():
    f = open('sendgrid_api_key.txt', 'r')
    key = f.read()
    return str(key)

def get_email_addresses(group):
    f = open(f'{group}_recipients.txt', 'r')
    addresses = f.read().split('\n')
    return addresses


# bmass_addresses = get_email_addresses('bmass')
egg_addresses = get_email_addresses('egg')

api_key = get_api_key()

sendgrid_server = {
    'server': 'smtp.sendgrid.net',
    'port': 465,
    'username': 'apikey',
    'password': api_key
}

def send_email(server_data, email_data):
    message = MIMEText(email_data['body'])
    message['From'] = email_data['from']
    message['To'] = email_data['to']
    message['Subject'] = email_data['subject']

    mail_server = smtplib.SMTP_SSL(server_data['server'], server_data['port'])
    mail_server.login(server_data['username'], server_data['password'])
    mail_server.send_message(message)
    mail_server.quit()

    print('Email sent')

def get_biomass_voltages():
    sensors = bmass_sensors
    sensors_voltages = {}
    for sensor in sensors:
        ref_status = db.reference('/bmass_' + str(sensor) + '/status')
        status_dict = ref_status.order_by_key().limit_to_last(1).get()
        # print(status_dict)
        date_key = list(status_dict.keys())[0]
        # print(date_key)
        sensors_voltages[sensor] = status_dict[date_key]['batt_v']
    # print(sensors_voltages)
    return sensors_voltages

def check_sensor_reporting(hours):
    sensors = bmass_sensors
    unreported_sensors = []
    current_time = datetime.now(eastern_timezone)
    for sensor in sensors:
        ref_data = db.reference('/bmass_' + str(sensor) + '/data')
        data_dict = ref_data.order_by_key().limit_to_last(1).get()
        # print(list(data_dict.values())[-1])
        # i = range(5)
        # for x,y,z in list(data_dict.values()):
        #     print(x)
        #     print(y)
        #     print(z)

        date_str = list(data_dict.keys())[0]
        date_format = '%Y%m%d_%H:%M:%S'
        date_obj = datetime.strptime(date_str, date_format).astimezone(eastern_timezone)
        date_cutoff = current_time - timedelta(hours=hours)
        if date_obj < date_cutoff:
            unreported_sensors.append(sensor)
    return (unreported_sensors, hours)


#returns last n uploads, and checks if last upload is 
def get_egg_data(n):
    egg_data = {
        'data': []
    }
    ref_data = db.reference('/egg_eye_1/data')
    data_dict = ref_data.order_by_key().limit_to_last(n).get()

    last_date_str = list(data_dict.keys())[-1]
    date_format = '%Y%m%d_%H:%M:%S'
    last_date_obj = datetime.strptime(last_date_str, date_format).astimezone(eastern_timezone)
    current_time = datetime.now(eastern_timezone)
    time_differential = current_time - last_date_obj
    rounded_differential = round(time_differential.total_seconds() / 60.0)
    egg_data['last_upload'] = rounded_differential

    readings = list(data_dict.values())
    for reading in readings:
        egg_data['data'].append((reading['off'], reading['on']))

    return egg_data

def build_egg_alert(egg_data, t):
    egg_alert = {
        'active_alerts': False,
        'alert_body': 'Here is a summary of current Egg Eye alerts:'
    }

    last_upload = egg_data['last_upload']

    if last_upload >= t:
        egg_alert['active_alerts'] = True
        egg_alert['alert_body'] += ('\n')
        egg_alert['alert_body'] += f'The sensor has not reported data in over {str(last_upload)} minutes.'

    neg1_count = 0
    zero_count = 0

    for off, on in egg_data['data']:
    
        # print('off ' + off)
        # print('on ' + on)

        if int(on) == 0:
            zero_count += 1

        if int(off) == -1 or int(on) == -1:
             neg1_count += 1

    minutes = round(len(egg_data['data'])/2)

    if zero_count == len(egg_data['data']):
        egg_alert['active_alerts'] = True
        egg_alert['alert_body'] += ('\n')
        egg_alert['alert_body'] += f'The sensor has reported all zeros for the last {str(minutes)} minutes.'

#{str(round(len(egg_data['data'])/2))}

    elif neg1_count == len(egg_data['data']):
        egg_alert['active_alerts'] = True
        egg_alert['alert_body'] += ('\n')
        egg_alert['alert_body'] += f'The sensor has reported all -1 values for the last {str(minutes)} minutes.'

    return egg_alert

def send_egg_alert(egg_alert):
    email_data = {
    'subject': 'Active HAUCS Alerts',
    'body': egg_alert['alert_body'],
    'from': 'haucsmon@gmail.com',
    'to': ', '.join(egg_addresses)
    }

    global last_egg_alert

    if egg_alert['active_alerts'] and (datetime.now(eastern_timezone) - timedelta(hours= 1)) > last_egg_alert:
        try:
            send_email(sendgrid_server, email_data)
            last_egg_alert = datetime.now(eastern_timezone)

        except Exception as e:
            print(f'Error sending egg alert: {e}')
        


def build_alert(voltages, sensor_reporting):
    alert = {
        'active_alerts': False,
        'alert_body': 'Here is a summary of current biomass alerts:'
    }

    for sensor, voltage in voltages.items():
        if float(voltage) <= 3.6:
            alert['active_alerts'] = True
            alert['alert_body'] += '\n'
            alert['alert_body'] += f'Sensor #{sensor} battery voltage is currently: {voltage}'

    if sensor_reporting[0]:
        alert['active_alerts'] = True
        alert['alert_body'] += '\n'

    for sensor in sensor_reporting[0]:
        alert['alert_body'] += '\n'
        alert['alert_body'] += f'Sensor {sensor} has not reported any data in over {sensor_reporting[1]} hours.'

    return alert

def send_bmass_alert(alert):
    email_data = {
    'subject': 'Active HAUCS Alerts',
    'body': alert['alert_body'],
    'from': 'haucsmon@gmail.com',
    'to': ', '.join(bmass_addresses)
    }
    if alert['active_alerts']:
        try:
            send_email(sendgrid_server, email_data)
        except Exception as e:
            print(f'Error: {e}')

# sensor_reporting = check_sensor_reporting(12)


# voltages = get_biomass_voltages()
# alert = build_alert(voltages, sensor_reporting)

# print(alert)
# send_alert(alert)


# test_data = {'data': [(0, -1), (0, -1), (-1, -1), (0, -1)], 'last_upload': 1}
# test_egg_alert = build_egg_alert(test_data, 2)
# print(test_egg_alert)

# send_egg_alert(test_egg_alert)

def egg_alert_process():
    egg_data = get_egg_data(4)
    egg_alert = build_egg_alert(egg_data, 2)
    send_egg_alert(egg_alert)

schedule.every(60).seconds.do(egg_alert_process)

while True:
    schedule.run_pending()
    time.sleep(1)