import smtplib
from email.mime.text import MIMEText
import time
import json
import os
import firebase_admin
import firebase
from firebase_admin import db
from firebase_admin import credentials

# fb_key = os.getenv('fb_key')

# if fb_key:
#     print("running in deployment mode")
#     deployed = True
# else:
#     print("running in debug mode")
#     deployed = False
with open('fb_key.json', 'r') as file:
    fb_key = file.read()

#login to firebase
fb_app = firebase.login(fb_key)

def get_api_key():
    f = open('sendgrid_api_key.txt', 'r')
    key = f.read()
    return str(key)

def get_email_addresses():
    f = open('alert_recipients.txt', 'r')
    addresses = f.read().split('\n')
    return addresses

api_key = get_api_key()
email_addresses = get_email_addresses()

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

def check_biomass_voltages():
    sensors = [1, 2, 3, 4, 5]
    sensors_voltages = {}
    for sensor in sensors:
        ref_status = db.reference('/bmass_' + str(sensor) + '/status')
        status_dict = ref_status.order_by_key().limit_to_last(1).get()
        date_key = list(status_dict.keys())[0]
        sensors_voltages[sensor] = status_dict[date_key]['batt_v']
    print(sensors_voltages)
    return sensors_voltages

def build_alert(voltages):
    alert = {
        'active_alerts': False,
        'alert_body': 'Here is a summary of current biomass alerts:'
    }

    for sensor, voltage in voltages.items():
        if float(voltage) <= 3.6:
            alert['active_alerts'] = True
            alert['alert_body'] += '\n'
            alert['alert_body'] += f'Sensor #{sensor} battery voltage is currently: {voltage}'

    return alert

def send_alert(alert):
    email_data = {
    'subject': 'Active HAUCS Alerts',
    'body': alert['alert_body'],
    'from': 'haucsmon@gmail.com',
    'to': ', '.join(email_addresses)
    }
    if alert['active_alerts']:
        try:
            send_email(sendgrid_server, email_data)
        except Exception as e:
            print(f'Error: {e}')


voltages = check_biomass_voltages()
alert = build_alert(voltages)
send_alert(alert)
