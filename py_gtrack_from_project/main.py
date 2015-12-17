#!/usr/bin/env python
import cv2
import sys
import numpy as np
import requests
import random
import time
import jsg
import ptz

baseline = cv2.getTextSize('+', cv2.FONT_HERSHEY_PLAIN, 2, 2)
CV_LOAD_IMAGE_COLOR = 1
CAMERA_URL = "http://129.241.154.24/mjpg/video.mjpg"

# Glyph tracking
# Vision algorithm is implemented in the imported jsg module.
# Feedback to camera is implemented in the imported ptz module.
#
# Written by Joakim Skjefstad (skjefstad.joakim@gmail.com) Autumn 2014, updated 2015

print "Glyph-tracking proof of concept. Use ESC to exit program."
print "Written by Joakim Skjefstad (skjefstad.joakim@gmail.com) Autumn 2014, updated 2015"
print "Preproject for master thesis. M.Sc in Technical Cybernetics at NTNU, Norway."

# Target specification
#TARGET = np.matrix('1 1 1 1 1; 1 0 1 0 1; 1 0 1 1 1; 1 0 0 0 1; 1 1 1 1 1')
TARGET = np.matrix('1 1 1 1 1; 1 0 0 0 1; 1 1 0 1 1; 1 1 0 1 1; 1 1 1 1 1')


RESIZE_TO_WIDTH = 600.0
P_GAIN_PAN = -0.045
P_GAIN_TILT = -0.045

target_list = []
target_list.append(TARGET)

cross = []

tick_frequency = cv2.getTickFrequency()
tick_at_init = cv2.getTickCount()
print "TICK FREQUENCY"
print "Ticks per second", tick_frequency
print "Ticks at init", tick_at_init
last_tick = tick_at_init
fps = 0
print fps

ptz_last_command_tick = cv2.getTickCount()
ptz_gracetime_ticks = tick_frequency/4 # 1/6th of a second

def interactive_drawing(event,x,y,flags,param):
    if event==cv2.EVENT_LBUTTONDOWN:
        print "pushed button",x,y
        cross.append([x,y])
def init_capture_device(is_cctv):
    if (is_cctv == True):
        print "Using CCTV MJPEG stream"
        session = requests.Session()
        auth = requests.auth.HTTPDigestAuth('ptz', 'ptz')
        request = requests.Request("GET", CAMERA_URL).prepare()
        request.prepare_auth(auth)
        response_stream = session.send(request, stream=True)
        return response_stream
    else:
        print "Using webcam stream"
        cap = cv2.VideoCapture(0)
        return cap

def grab_frame(capture_device, is_cctv):
    if is_cctv == False:
        ret, img = capture_device.read()
        return img
    else:
        bytes=''
        while True:
            bytes+=capture_device.raw.read(1024)
            a = bytes.find('\xff\xd8')
            if a !=-1:
                b = bytes.find('\xff\xd9', a)
                if a!=-1 and b!=-1:
                    jpg = bytes[a:b+2]
                    bytes= bytes[b+2:]
                    i = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), CV_LOAD_IMAGE_COLOR)
                    return i

capture_device = init_capture_device(True) # SET TO TRUE FOR CCTV STREAM
command_this_frame = 0
f = open('full_cycle_py.log','w')
fgrab = open('grab_cycle_py.log','w')
for cycle in range(1, 100):
    millis = int(round(time.time() * 1000))
    #source = grab_frame(capture_device, True) # SET TO TRUE FOR CCTV STREAM
    cap = cv2.VideoCapture("http://ptz:ptz@129.241.154.24/mjpg/video.mjpg")
    val, source = cap.read()
    h_source, w_source, c_source = source.shape
   
    #r = RESIZE_TO_WIDTH / source.shape[1]
    #dim = (int(RESIZE_TO_WIDTH), int(source.shape[0] * r))
    #resized = cv2.resize(source, dim, interpolation = cv2.INTER_AREA)
    #h_resized, w_resized, c_resized = resized.shape
    #source = resized
    
    #cv2.putText(source,'+', (w_resized/2-(baseline[0][0]/2),h_resized/2+(baseline[0][1]/2)), cv2.FONT_HERSHEY_PLAIN, 2, (0,0,255), 2)
    millis_grab = int(round(time.time() * 1000))
    deltamillis_grab = millis_grab - millis

    temp_img = jsg.preprocess(source)
    cv2.imshow('temp',temp_img)
    potential_glyphs = jsg.find_potential_glyphs(temp_img, 100.0)
    print potential_glyphs
    for glyph in potential_glyphs:
        glyph.compute_glyph(source)
        if jsg.compare_glyphs(glyph.glyph_matrix,target_list):
            cv2.drawContours(source,[glyph.approx_poly],0,(0,255,0),1)
            cv2.circle(source,(glyph.cx,glyph.cy),2,(255,0,255),-1)
            cv2.putText(source,str(glyph.nr), (glyph.cx,glyph.cy), cv2.FONT_HERSHEY_PLAIN, 2, (255,255,0), 2)
            delta_array = jsg.delta_to_center(source, glyph)
            print delta_array
            for item in delta_array:
                if abs(delta_array[0]) > 0.1 and (cv2.getTickCount()-ptz_last_command_tick > ptz_gracetime_ticks):
                    print "pan",item
                    ptz.relative_pan(P_GAIN_PAN*delta_array[0])
                    command_this_frame = 1
                    
                if abs(delta_array[1]) > 0.5 and (cv2.getTickCount()-ptz_last_command_tick > ptz_gracetime_ticks):
                    print "tilt",-0.01*delta_array[0]
                    ptz.tilt(P_GAIN_TILT*delta_array[1])
                    command_this_frame = 1
                    
                if command_this_frame:
                    ptz_last_command_tick = cv2.getTickCount()
                    
                command_this_frame = 0
            cv2.imshow('Roi',glyph.img_roi)
            cv2.imshow('Otsu',glyph.img_roi_otsu)
           
    cv2.namedWindow('Source')
    cv2.setMouseCallback('Source',interactive_drawing)

    for item in cross:
        cv2.putText(source,'+', (item[0]-(baseline[0][0]/2),item[1]+(baseline[0][1]/2)), cv2.FONT_HERSHEY_PLAIN, 2, (255,0,255), 2)
    
    # FPS Calculator    
    fps = tick_frequency / (cv2.getTickCount() - last_tick)
    last_tick = cv2.getTickCount()
    
    #cv2.putText(source, "src=%sx%s downscaled=%sx%s" % (w_source,h_source, w_resized, h_resized), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255))
    cv2.putText(source, "fps=%s" % (fps), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255))
    
    cv2.imshow('Source',source)
    print "cycle"
    key = cv2.waitKey(1)
    if key == 27:
        exit(0)
    elif key == 119:
        print "Up"
        ptz.tilt(-P_GAIN_TILT*1000)
    elif key == 115:
        print "Down"
        ptz.tilt(P_GAIN_TILT*1000)
    elif key == 100:
        print "Right"
        ptz.relative_pan(-P_GAIN_PAN*1000)
    elif key == 97:
        print "Left"
        ptz.relative_pan(P_GAIN_PAN*1000)
    
    millis_end = int(round(time.time() * 1000))
    print "cycleno",cycle


    deltamillis = millis_end - millis

    f.write(str(cycle)) # python will convert \n to os.linesep
    f.write(" ") # python will convert \n to os.linesep
    f.write(str(deltamillis)) # python will convert \n to os.linesep
    f.write("\n") # python will convert \n to os.linesep

    fgrab.write(str(cycle)) # python will convert \n to os.linesep
    fgrab.write(" ") # python will convert \n to os.linesep
    fgrab.write(str(deltamillis_grab)) # python will convert \n to os.linesep
    fgrab.write("\n") # python will convert \n to os.linesep




f.close() # you can omit in most cases as the destructor will call it
fgrab.close() 