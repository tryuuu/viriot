# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Fed4IoT Thing ThingVisor hello world

import time
import os
import random
import json
import traceback
import paho.mqtt.client as mqtt
from threading import Thread
from pymongo import MongoClient
from context import Context

with open('/app/data/entry.json', 'r') as f:
    data = json.load(f)

# 変数の初期化
thing_visor_ID = data["thing_visor_ID"]
MQTT_data_broker_IP = data["MQTTDataBrokerIP"]
MQTT_data_broker_port = data["MQTTDataBrokerPort"]
MQTT_control_broker_IP = data["MQTTControlBrokerIP"]
MQTT_control_broker_port = data["MQTTControlBrokerPort"]
tv_control_prefix = data["tv_control_prefix"]
v_thing_prefix = data["v_thing_prefix"]
in_data_suffix = data["in_data_suffix"]
out_data_suffix = data["out_data_suffix"]
in_control_suffix = data["in_control_suffix"]
out_control_suffix = data["out_control_suffix"]
v_silo_prefix = data["v_silo_prefix"]

params = data["params"]
v_thing_ID = thing_visor_ID + "/" + "hello"
v_thing_label = "helloWorld"
v_thing_description = "hello world virtual thing"
v_thing = {"label": v_thing_label,
           "id": v_thing_ID,
           "description": v_thing_description}

if params:
    if 'rate' in params:
        sleep_time = params['rate']
    else:
        sleep_time = 5
else:
    sleep_time = 5

v_thing_topic = v_thing_prefix + "/" + v_thing_ID
context_hello = Context()
contexts = {v_thing_ID: context_hello}


class FetcherThread(Thread):
    c = random.randint(0, 500)              # counter

    # Thread used to fetch and publish data
    def __init__(self, sleep_time):
        Thread.__init__(self)
        self.sleep_time = sleep_time

        self.restart = False

        # Create initial status
        ngsiLdEntity1 = {"id": "urn:ngsi-ld:HelloSensor1",
                         "type": "my-counter",
                         "counter": {"type": "Property", "value": self.c}}

        ngsiLdEntity2 = {"id": "urn:ngsi-ld:HelloSensor2",
                         "type": "my-double-counter",
                         "double-counter": {"type": "Property", "value": 2 * self.c}}

        data = [ngsiLdEntity1, ngsiLdEntity2]
        # set initial context for hello virtual thing
        context_hello.set_all(data)

    def run(self):
        # while True:
        while not self.restart:
            print("Started thread with sleep time:", self.sleep_time)
            self.c = self.c + 1
            # neutral-format {"data":<NGSI-LD Entity Array>, "meta": {"vThingID":<v_thing_ID>}}
            # vThingID is mandatory, making possible to identify the vThingID without exploiting the data_out topic name

            # 定期的にカウンターをインクリメントし、新しいデータを生成する
            ngsiLdEntity1 = {"id": "urn:ngsi-ld:HelloSensor1",
                             "type": "my-counter",
                             "counter": {"type": "Property", "value": self.c}}

            ngsiLdEntity2 = {"id": "urn:ngsi-ld:HelloSensor2",
                             "type": "my-double-counter",
                             "double-counter": {"type": "Property", "value": 2*self.c}}

            # update context status for virtual thing hello
            context_hello.update([ngsiLdEntity1, ngsiLdEntity2])

            # publish changed entities
            data = [ngsiLdEntity1, ngsiLdEntity2]
            message = {"data": data, "meta": {"vThingID": v_thing_ID}}
            self.publish(message)

            time.sleep(self.sleep_time)  # possible fetch interval
        print("Killing thread...")

    def publish(self, message):
        print("topic name: " + v_thing_topic + '/' + out_data_suffix + ", message: " + json.dumps(message))
        mqtt_data_client.publish(v_thing_topic + '/' + out_data_suffix,
                                 json.dumps(message))  # publish received data to data topic by using neutral format

    def restart_thread(self):
        self.restart = True


class mqttDataThread(Thread):
    # mqtt client for sending data
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        print("Thread mqtt data started")
        global mqtt_data_client
        mqtt_data_client.connect(MQTT_data_broker_IP, MQTT_data_broker_port, 30)
        mqtt_data_client.loop_forever()
        print("Thread '" + self.name + "' terminated")


class MqttControlThread(Thread):

    def on_message_get_thing_context(self, jres):
        silo_id = jres["vSiloID"]
        message = {"command": "getContextResponse", "data": context_hello.get_all(), "meta": {"vThingID": v_thing_ID}}
        mqtt_control_client.publish(v_silo_prefix + "/" + silo_id + "/" + in_control_suffix, json.dumps(message))

    def send_destroy_v_thing_message(self):
        msg = {"command": "deleteVThing", "vThingID": v_thing_ID, "vSiloID": "ALL"}
        mqtt_control_client.publish(v_thing_prefix + "/" + v_thing_ID + "/" + out_control_suffix, json.dumps(msg))
        return

    def send_destroy_thing_visor_ack_message(self):
        msg = {"command": "destroyTVAck", "thingVisorID": thing_visor_ID}
        mqtt_control_client.publish(tv_control_prefix + "/" + thing_visor_ID + "/" + out_control_suffix, json.dumps(msg))
        return

    def on_message_destroy_thing_visor(self, jres):
        global db_client
        db_client.close()
        self.send_destroy_v_thing_message()
        self.send_destroy_thing_visor_ack_message()
        print("Shutdown completed")

    def on_message_update_thing_visor(self, jres):
        # mqtt_control_client.publish(v_thing_prefix + "/" + v_thing_ID + "/" + out_control_suffix, json['update-info'])
        print("Print updateInfo:", jres['updateInfo'])
        sleep_time = jres['params']['rate']
        # kill thread
        self.data_thread.restart_thread()
        # restart thread with new parameters
        self.data_thread = FetcherThread(sleep_time)
        self.data_thread.start()

    # handler for mqtt control topics
    def __init__(self, data_thread):
        Thread.__init__(self)
        self.data_thread = data_thread

    def on_message_in_control_vThing(self, mosq, obj, msg):
        payload = msg.payload.decode("utf-8", "ignore")
        print(msg.topic + " " + str(payload))
        jres = json.loads(payload.replace("\'", "\""))
        try:
            command_type = jres["command"]
            if command_type == "getContextRequest":
                self.on_message_get_thing_context(jres)
        except Exception as ex:
            traceback.print_exc()
        return

    def on_message_in_control_TV(self, mosq, obj, msg):
        payload = msg.payload.decode("utf-8", "ignore")
        jres = json.loads(payload)

        print(msg.topic + " " + str(jres))

        try:
            command_type = jres["command"]
            if command_type == "destroyTV":
                self.on_message_destroy_thing_visor(jres)
            elif command_type == "updateTV":
                self.on_message_update_thing_visor(jres)
        except Exception as ex:
            traceback.print_exc()
        return 'invalid command'

    # MQTT制御ブローカーに接続し、制御メッセージを受信して処理するためのループを実行
    def run(self):
        print("Thread mqtt control started")
        global mqtt_control_client
        mqtt_control_client.connect(MQTT_control_broker_IP, MQTT_control_broker_port, 30)

        # Publish on the thingVisor out_control topic the createVThing command and other parameters
        v_thing_message = {"command": "createVThing",
                           "thingVisorID": thing_visor_ID,
                           "vThing": v_thing}

        mqtt_control_client.publish(tv_control_prefix + "/" + thing_visor_ID + "/" + out_control_suffix,
                                    json.dumps(v_thing_message))

        # Add message callbacks that will only trigger on a specific subscription match
        mqtt_control_client.message_callback_add(v_thing_topic + "/" + in_control_suffix,
                                                 self.on_message_in_control_vThing)
        mqtt_control_client.message_callback_add(tv_control_prefix + "/" + thing_visor_ID + "/" + in_control_suffix,
                                                 self.on_message_in_control_TV)
        mqtt_control_client.subscribe(v_thing_topic + '/' + in_control_suffix)
        mqtt_control_client.subscribe(tv_control_prefix + "/" + thing_visor_ID + "/" + in_control_suffix)
        mqtt_control_client.loop_forever()
        print("Thread '" + self.name + "' terminated")

if __name__ == '__main__':
    mqtt_control_client = mqtt.Client()
    mqtt_data_client = mqtt.Client()

    data_thread = FetcherThread(sleep_time)
    data_thread.start()

    mqtt_control_thread = MqttControlThread(data_thread)
    mqtt_control_thread.start()

    mqtt_data_thread = mqttDataThread()
    mqtt_data_thread.start()

    while True:
        try:
            time.sleep(3)
        except:
            print("KeyboardInterrupt" + "\n")
            time.sleep(1)
            os._exit(1)