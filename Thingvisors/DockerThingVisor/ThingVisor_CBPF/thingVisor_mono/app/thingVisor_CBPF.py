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

# This is a Fed4IoT ThingVisor for Face Recognition

import os
# from ThingVisor_CBPF.thingVisor_facerecognition import periodically_every_fps

import thingVisor_generic_module as thingvisor

import sys
import datetime
# import requests
import json
import logging
import traceback
import threading
# from eve import Eve
from flask import Flask, request, render_template
from bson.objectid import ObjectId
#import face_recognition
import cv2
import numpy as np
import base64
import uuid
from PIL import Image, ImageDraw

#import shlex
import shutil
#from multiprocessing import Process, Pipe
import threading
import glob
import time
from time import CLOCK_PROCESS_CPUTIME_ID, sleep
from open_the_camera import open_camera as op_cam
#from face_detction import face_detection_api as face_rec
import datetime
#from sub_main_multithreading import run_face_find_pana, close_thread
#import find_face_recognition, config
#import werkzeug
from flask import Flask, jsonify, render_template
from werkzeug.utils import secure_filename

import config
from azure.cognitiveservices.vision.face import FaceClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person

import netifaces as ni
import psutil

# <snippet_persongroupvars>
# Used in the Person Group Operations and Delete Person Group examples.
# You can call list_person_groups to print a list of preexisting PersonGroups.
# SOURCE_PERSON_GROUP_ID should be all lowercase and alphanumeric. For example, 'mygroupname' (dashes are OK).
PERSON_GROUP_ID = str(uuid.uuid4())  # assign a random ID (or name it anything)

# Used for the Delete Person Group example.
TARGET_PERSON_GROUP_ID = str(uuid.uuid4())  # assign a random ID (or name it anything)

try:
    parameters = json.loads(os.environ['params'])
except json.decoder.JSONDecodeError:
    print("error on params (JSON) decoding" + "\n")
    exit()
except Exception as e:
    print("Error: Parameters not found", e)
    exit()

KEY = parameters["AZURE_KEY"]
# This endpoint will be used in all examples in this quickstart.
#ENDPOINT = "https://fed4iot.cognitiveservices.azure.com/"
ENDPOINT = parameters["ENDPOINT"]

# Create an authenticated FaceClient.
face_client = FaceClient(ENDPOINT, CognitiveServicesCredentials(KEY))


# -*- coding: utf-8 -*-

api = Flask(__name__, static_folder='image')

UPLOAD_DIR = config.find_img_dir

face_rec_start_flg = False

pana_cam = True

if pana_cam:
    web_cam = op_cam.PanaCamera()
    result, capture = web_cam.open_camera()
else:
    web_cam = op_cam.WebCamera()
    result, capture = web_cam.open_camera()
print("web cam result: ", result, capture)

if not result:
    print("api result: failed")
    # return jsonify({"api result": "ERR: Camera is not connected!"})
    sys.exit(1)
else:
    print("api result: success")
    # return jsonify({"api result": "Face recognition started"})

#t_azure = run_face_find_pana()

# to actuate this detector, use your Broker to channge the "start" Property, as follows:
# start : {
#   type : Property
#   value : {
#     cmd-value : {"job":"dsfsdfdsf234"}
#     cmd-qos : 2
#   }
# }

def decode_base64url(s):
    return base64.urlsafe_b64decode(s + b'=' * ((4 - len(s) & 3) & 3))

def on_start(vThingID, cmd_entity, cmd_name, cmd_info):
    global face_rec_start_flg

    print("***Face search start at: " + str(datetime.datetime.utcnow().isoformat()))

    if "cmd-value" in cmd_info:
        #if "job" in cmd_info["cmd-value"]:
        job = cmd_info["cmd-value"]["job"]
        #'''
        coded_img = cmd_info["cmd-value"]["img"]
        # int_img = coded_img.encode('utf-8')
        # print(int_img)
        img = decode_base64url(coded_img.encode('utf-8'))
        with open(UPLOAD_DIR+"/target.jpg", "bw") as target_face_img_file:
            target_face_img_file.write(img)

        face_rec_start_flg = True
        #'''
            # thingvisor.publish_actuation_response_message(vThingID, cmd_entity, cmd_name, cmd_info, jsonify({"api result": "Face recognition is started."}))

        # os.chdir(config.root_path)

        camera_thread = threading.Thread(target=periodically_every_fps)
        camera_thread.start()

        result = []
        address_list = psutil.net_if_addrs()
        print(address_list)
        for nic in address_list.keys():
            ni.ifaddresses(nic)
            try:
                ip = ni.ifaddresses(nic)[ni.AF_INET][0]['addr']
                if ip not in ["127.0.0.1"]:
                    result.append(ip)
            except KeyError as err:
                pass
        # give status uodate that we have started
        if "cmd-qos" in cmd_info:
            if int(cmd_info['cmd-qos']) > 0:
                thingvisor.publish_actuation_response_message(vThingID, cmd_entity, cmd_name, cmd_info, "STARTING job: "+job+"\n Upload a face picture at http://"+result[0]+"/api/upload", "result")
    else:
        print("no cmd-value for START command")

# Permissible file extensions for upload
ALLOW_EXTENSIONS = ['jpg', 'jpeg', 'png']

def on_stop(vThingID, cmd_entity, cmd_name, cmd_info):
    global face_rec_start_flg

    print("***Face search stop at: " + str(datetime.datetime.utcnow().isoformat()))

    if "cmd-value" in cmd_info:
        job = cmd_info["cmd-value"]["job"]
        face_rec_start_flg = False
        if "cmd-qos" in cmd_info:
            if int(cmd_info['cmd-qos']) > 0:
                thingvisor.publish_actuation_response_message(vThingID, cmd_entity, cmd_name, cmd_info, "STOPPED job: "+job, "result")
    else:
        print("no cmd-value for STOP command")
        

def on_delete_by_name(vThingID, cmd_entity, cmd_name, cmd_info):
    print("***delete_by_name is requested at: " + str(datetime.datetime.utcnow().isoformat()))

    result_str = "Nothing to delete"
    if "cmd-value" in cmd_info:
        job = cmd_info["cmd-value"]["job"]
        if "img_name" in cmd_info["cmd-value"]:
            name = cmd_info["cmd-value"]["img_name"]
            if name == 'all':
                file_list = glob.glob(os.path.join(config.temp_image_dir, '*.*'))
                for file in file_list:
                    os.remove(file)
                    result_str = "All image files are deleted"
            else:
                file_list = glob.glob(os.path.join(config.temp_image_dir, name))
                for file in file_list:
                    os.remove(file)
                    result_str = name + " is deleted"
        else:
            print("No image name")

        if "cmd-qos" in cmd_info:
            if int(cmd_info["cmd-qos"]) > 0:
                thingvisor.publish_actuation_response_message(vThingID, cmd_entity, cmd_name, cmd_info, result_str, "result")
        

def allowed_file(file_name):
    return '.' in file_name and file_name.rsplit('.', 1)[-1] in ALLOW_EXTENSIONS


#@api.route('/api/upload', methods=['GET', 'POST'])
def uploads():
    global face_rec_start_flg

    if request.method == 'POST':
        # get POST
        file = request.files['file']

        if file and allowed_file(file.filename):

            # secure_filename
            file_name = secure_filename(file.filename)
            # save image file
            file.save(os.path.join(UPLOAD_DIR, file_name))
            #face_rec_start_flg = True;
            return jsonify({"api result": "File upload success!"})
        else:
            return jsonify({"api result": "File format is not 'jpg', 'jpeg', 'png'"})
    return render_template('index.html')


def periodically_every_fps():
    global face_rec_start_flg, t_azure
    global capture

    if not face_rec_start_flg:
        return

    logging.debug('camera thread execution')
    # print("Start find_face_recognition.")

    # threading.Timer(1/thingvisor.params['fps'], periodically_every_fps).start()

    active_flg = True
    files = glob.glob(UPLOAD_DIR + '*')
    ret, img = capture.read()

    if ret:
        ts1 = time.time()
        print("***Camera picture at: " + str(datetime.datetime.utcnow().isoformat()))
        #img, len_face_rec = face_rec.facial_detection(img)

        #if len_face_rec > 0 and t_azure.implement_flg is False:
        print('Start Face Recognition')
        cur_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        img_name = 'img' + cur_time + '.jpg'
        img_path = config.cache_dir + img_name
        cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY,75])
        #t_azure.implement_flg = True
        #t_azure.cache_img_path = img_path

        find_flag = False

        for file in files:
            result = find_face(file, img_path)
            if not result:
                pass
            else:
                find_flag = True

            if find_flag:
                #t_mqtt.publish_order = True
                #t_mqtt.image_name = img_name
                print("A face appeared")
                location = '{ "type": "Point", "coordinates": [' + ','.join(map(str, config.location)) + '] }'
                createdat = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                result = []
                address_list = psutil.net_if_addrs()
                print(address_list)
                print("***Face found at: " + str(datetime.datetime.utcnow().isoformat()))
                for nic in address_list.keys():
                    ni.ifaddresses(nic)
                    try:
                        ip = ni.ifaddresses(nic)[ni.AF_INET][0]['addr']
                        if ip not in ["127.0.0.1"]:
                            result.append(ip)
                    except KeyError as err:
                        pass
                filename = "http://"+result[0]+ ":5000/api/view/" + img_name
                attributes = [{"attributename": 'location', "attributevalue": location, "attributetype": "GeoProperty"}, 
                {"attributename": 'createdAt', "attributevalue": createdat},
                {"attributename": 'Source', "attributevalue": config.source},
                {"attributename": 'dataProvider', "attributevalue": filename},
                {"attributename": 'entityVersion', "attributevalue": config.entityVersion},
                {"attributename": 'deviceModel', "attributevalue": config.pana_cam_model, "attributetype": "Relationship"},
                {"attributename": 'description', "attributevalue": config.description},
                {"attributename": 'FileName', "attributevalue": filename}
                ]
                thingvisor.publish_attributes_of_a_vthing("detector", attributes)
            else:
                os.remove(img_path)
        ts2 = time.time()
        print("processing time {}".format(ts2-ts1)) 
    threading.Timer(1/thingvisor.params['fps'], periodically_every_fps).start()

@api.route('/api/view/<img>')
def picture_view(img=None):
    return render_template('detected_face.html', title='Found Face', image='/image/temp_image/'+img)


def single_face_detect(image_path):
    '''

    :param image_path:
    :return:
    '''

    # Detect a face in an image that contains a single face
    single_face_image_path = image_path
    # single_image_name = os.path.basename(single_face_image_path)
    # print('single_face_image_path: ', single_face_image_path)
    # We use detection model 3 to get better performance.
    find_image = open(single_face_image_path, 'rb')
    try:
        detected_faces = ''
        detected_faces = face_client.face.detect_with_stream(image=find_image, detection_model='detection_03')
    except Exception as e:
        print(e)
        sleep(5)

    if not detected_faces:
        # raise Exception('No face detected from image {}'.format(single_image_name))
        return None

    # Display the detected face ID in the first single-face image.
    # Face IDs are used for comparison to faces (their IDs) detected in other images.
    # print('Detected face ID from', single_image_name, ':')
    for face in detected_faces:
        # print(face.face_id)
        continue
    # Save this ID for use in Find Similar
    first_image_face_ID = detected_faces[0].face_id

    return first_image_face_ID


def multi_face_detect(image_path=None, image=None):
    '''
    :param image_path: 探したい人の画像の保存パス　image/find_image/
    :param image: カメラのフィルムイメージ
    :return: 顔識別結果、イメージファイルの名前
    '''
    # Each detected face gets assigned a new ID

    if image_path is None and image is None:
        # raise Exception('No face detected from image.')
        return None, None
    if image is None:
        multi_face_image_path = image_path
        multi_image_name = os.path.basename(multi_face_image_path)
        detect_image = open(multi_face_image_path, 'rb')
        detect_show_image = Image.open(multi_face_image_path, 'r')

    else:
        detect_image = image
        detect_show_image = image
    # We use detection model 3 to get better performance.

    try:
        multi_detected_faces = ''
        multi_detected_faces = face_client.face.detect_with_stream(image=detect_image, detection_model='detection_03')
    except Exception as e:
        print(e)
        sleep(5)

    # print('Detected face IDs from', multi_image_name, ':')
    if not multi_detected_faces:
        # raise Exception('No face detected from image {}.'.format(multi_image_name))
        return None, None
    else:
        for d_face in multi_detected_faces:
            print(d_face.face_id)
            continue
        print_image_draw_rect(detect_show_image, multi_detected_faces)

    return multi_detected_faces, multi_image_name


# Convert width height to a point in a rectangle
def getRectangle(faceDictionary):
    '''

    :param faceDictionary: 顔のデーター
    :return: 顔枠の位置
    '''
    rect = faceDictionary.face_rectangle
    left = rect.left
    top = rect.top
    right = left + rect.width
    bottom = top + rect.height

    return ((left, top), (right, bottom))


def print_image_draw_rect(image, detected_faces):
    '''
    Print image and draw rectangles around faces
    :param image:
    :param detected_faces:
    :return:
    '''

    # For each face returned use the face rectangle and draw a red box.
    # print('Drawing rectangle around face... see popup for results.')
    draw = ImageDraw.Draw(image)
    for d_face in detected_faces:
        draw.rectangle(getRectangle(d_face), outline='red')

    # Display the image in the users default image browser.
    # image.show()


def find_similar_face(find_face_id, detected_faces, multi_image_name):

    # Search through faces detected in group image for the single face from first image.
    # First, create a list of the face IDs found in the second image.
    second_image_face_IDs = list(map(lambda x: x.face_id, detected_faces))
    # Next, find similar face IDs like the one detected in the first image.
    similar_faces = face_client.face.find_similar(face_id=find_face_id, face_ids=second_image_face_IDs)
    if not similar_faces:
        print('No similar faces found in', multi_image_name, '.')
        return False
    # Print the details of the similar faces detected
    else:
        # print('Similar faces found in', multi_image_name)
        for face in similar_faces:
            first_image_face_ID = face.face_id
            # The similar face IDs of the single face image and the group image do not need to match,
            # they are only used for identification purposes in each image.
            # The similar faces are matched using the Cognitive Services algorithm in find_similar().
            face_info = next(x for x in detected_faces if x.face_id == first_image_face_ID)
            if face_info:
                print('  Face ID: ', first_image_face_ID)
                print('  Face rectangle:')
                print('    Left: ', str(face_info.face_rectangle.left))
                print('    Top: ', str(face_info.face_rectangle.top))
                print('    Width: ', str(face_info.face_rectangle.width))
                print('    Height: ', str(face_info.face_rectangle.height))
        return True

def find_face(find_img_path, detected_img_path=None, detected_img=None):
    if find_img_path:
        image_face_id = single_face_detect(find_img_path)
        if image_face_id is None:
            return False
        detected_faces, multi_image_name = multi_face_detect(detected_img_path, detected_img)
        if detected_faces is None or multi_image_name is None:
            return False
        result = find_similar_face(image_face_id, detected_faces, multi_image_name)
        return result
    else:
        return False


if __name__ == '__main__':
    thingvisor.initialize_thingvisor('thingVisor_CBPF')
    known_encodings = []
    known_metadata = []
    
    thingvisor.initialize_vthing("detector","CBPF Event","CBPF virual thing",["start","stop","delete-by-name"])
    print("All vthings initialized")
    print(thingvisor.v_things['detector'])
    if 'fps' in thingvisor.params:
        print("parsed fps parameter: " + str(thingvisor.params['fps']))
    else:
        thingvisor.params['fps'] = 0.1
        print("defaulting fps parameter: " + str(thingvisor.params['fps'])) 

    api.run(host='0.0.0.0',port=5000,debug=False)
    
