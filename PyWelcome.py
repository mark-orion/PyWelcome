#!/usr/bin/env python
from __future__ import print_function
import sys, os, argparse, time, signal
import cv2
import cv2.cv as cv
#import subprocess

try:
    import serial
    display_active = True
except:
    display_active = False
    print("PySerial not found. VFD output disabled.", file=sys.stderr)
    
try:
    from espeak import espeak
    from espeak import core as espeak_core
    # done_synth signals when the speech synthesizer has finished
    global old_count
    old_count = 0    
    global done_synth
    done_synth = True
    def espeak_callback(event, pos, length):
        if event == espeak_core.event_MSG_TERMINATED:
            global done_synth
            done_synth = True
    espeak.set_SynthCallback(espeak_callback)
    voice_active = True
except:
    voice_active = False
    print("Espeak not found. Voice output deactivated", file=sys.stderr)

default_cascade = "/usr/share/opencv/haarcascades/haarcascade_frontalface_alt.xml"

# Control commands for Toshiba LIUST-51 Vacuum Fluorescent Display
vfd_clear = '\x1B\x5B\x32\x4A'
vfd_del = '\x1B\x5B\x30\x4B'
vfd_lf = '\x0A'
vfd_cr = '\x0D'
vfd_line1 = '\x1B\x5B\x01\x3B\x01\x48'
vfd_line2 = '\x1B\x5B\x02\x3B\x01\x48'

display_text = ''
voice_text = ''
output_file = sys.stdout

try:
    ser = serial.Serial(
        port='/dev/ttyUSB0',
        baudrate=9600,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        rtscts=True
        )
except:
    display_active = False
    print("No serial device found. Disabling VFD support \n", file=sys.stderr)

def counter_output(counter, size, pos_x, pos_y):
    global done_synth
    global old_count
    if voice_text != '' and voice_active:
        if done_synth:
            if old_count == 0:
                espeak.synth(voice_text + ' ' + str(counter))
                done_synth = False
            else:
                espeak.synth('Welcome visitors ' + str(old_count) + ' to ' + str(counter))
                done_synth = False
                old_count = 0
        else:
            if old_count == 0:
                old_count = counter
        #subprocess.call("speak.sh '" + voice_text + ' ' + str(counter) + "'&",shell=True)
        #subprocess.call("echo '" + voice_text + ' ' + str(counter) + "'| festival --tts &",shell=True)
    if display_text != '' and display_active:
        ser.write(vfd_cr + str(counter) + ' people counted' + vfd_del)
    output_file.write( str(counter) + ',' + str(time.time()) + ',' + time.strftime('%Y-%m-%d %H:%M:%S') + ',' + str(size) + ',' + str(pos_x) + ',' + str(pos_y) + '\n')    
    return

def signal_handler(signal, frame):
    if display_text != '':
        ser.write(vfd_clear)
    sys.exit(0)

def nothing(par):
    return

if __name__ == '__main__':
    # register signal handler for a clean exit    
    signal.signal(signal.SIGINT, signal_handler)
    
    # command line parser
    parser = argparse.ArgumentParser(description='OpenCV People Counter')
    parser.add_argument('-i', '--input_source', default=0, help='Input Source, either filename or camera index, default = 0')
    parser.add_argument('-iw', '--input_width', default=0, help='Width of captured frames')
    parser.add_argument('-ih', '--input_height', default=0, help='Height of captured frames')
    parser.add_argument('-s', '--start_value', default=0, help='Start Value of people counter, default = 0')    
    parser.add_argument('-ta', '--tracker_age', default=10, help='Max age of object in tracker memory, default = 10')        
    parser.add_argument('-tm', '--tracker_method', default='TAC', help='Tracking method to count faces, TAC (Track And Count) or VLB (Virtual Light Barrier), default = TAC')
    parser.add_argument('-to', '--tracker_offset', default=1, help='Max offset allowed for face tracing, default = 1')
    parser.add_argument('-vlb', '--vlb_position', default=0, help='Position of Virtual Light Barrier, default = 0 = half frame height')
    parser.add_argument('-c', '--cascade', default=default_cascade, help='Haar Cascade to use, default = ' + default_cascade)
    parser.add_argument('-cs', '--cascade_scale', default=1.4, help='Cascade Scale Factor, default = 1.4')    
    parser.add_argument('-o', '--output', default='stdout', help='Output: filename or stdout, defaults to stdout')
    parser.add_argument('-os', '--output_speech', default='Welcome visitor number ', help='Speech synthesizer string, default = no speech synthesis')
    parser.add_argument('-vfd', '--toshiba_vfd', default='OpenCV Face Counter', help='String to be displayed on Toshiba VFD, default = OpenCV Face Counter')    
    args = parser.parse_args()

    # set parameters
    green = (0, 255, 0)
    red = (0, 0, 255)
    faces = []
    peoplecounter = int(args.start_value)
    max_age = int(args.tracker_age)
    mfactor = int(args.tracker_offset)
    if voice_active:
        voice_text = args.output_speech
    
    # open file, stdout is unbuffered
    if args.output == 'stdout':
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        output_file = sys.stdout
    else:
        output_file = open(args.output, 'a')    
    
    # open video and get cascade ready
    if str(args.input_source).isdigit():
        video_src = int(args.input_source)
    else:
        video_src = args.input_source
    cascade = cv2.CascadeClassifier(args.cascade)
    cam = cv2.VideoCapture(video_src)  
    if args.input_width > 0 and args.input_height > 0:
        cam.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, float(args.input_width))
        cam.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, float(args.input_height))
    if cam is None or not cam.isOpened():
        print("Warning: unable to open video source:" + video_src, file=sys.stderr)
    frame_width = int(cam.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH))
    
    # initial position of VLB
    if args.vlb_position == 0:
        vlb = int(cam.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT) / 2)
    else:
        vlb = args.vlb_position
        
    # create window and GUI
    cv2.namedWindow('Control Panel', 0)
    cv2.namedWindow('OpenCV People Counter', 0)
    cv2.createTrackbar('VLB position', 'Control Panel', vlb, int(cam.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)), nothing)
    
    # get VFD over serial port ready
    if display_active:
        display_text = args.toshiba_vfd
        if display_text != '':
            try:
                ser.write(vfd_line2 + vfd_cr + vfd_lf)
                ser.write(args.toshiba_vfd + vfd_cr + vfd_lf)
                ser.write('ready to count')
            except:
                print("No serial device found. Option -vfd ignored \n", file=sys.stderr)
          
    # main video processing loop
    while True:
        vlb = cv2.getTrackbarPos('VLB position', 'Control Panel')
        ret, img = cam.read()
        if ret == False:
            print("No more frames or capture device down - exiting.", file=sys.stderr)
            sys.exit(0)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        t = cv2.getTickCount() / cv2.getTickFrequency()
        rects = cascade.detectMultiScale(gray, scaleFactor=args.cascade_scale, minNeighbors=4, minSize=(30, 30), flags = cv.CV_HAAR_SCALE_IMAGE)
        if len(rects) == 0:
            rects = []
        else:
            rects[:,2:] += rects[:,:2]        
        vis = img.copy()
        for x1, y1, x2, y2 in rects:
            # Width and height of detected object
            w_x = x2 - x1
            h_y = y2 - y1
            # Center coordinates of detected object
            c_x = x1 + w_x/2
            c_y = y1 + h_y/2
            # Size of detected object
            c_s = w_x * h_y
            for idx, (a1, b1, a2, b2, det, upd, cnt) in enumerate(faces):
                # Garbage collection: Delete objects older than max_age seconds or not seen for 2 seconds
                if t - upd > 5 or t - det > max_age or b1 > vlb:
                    del faces[idx]
                    continue
                # Center coordinates of stored object
                c_a = a1 + (a2 - a1)/2
                c_b = b1 + (b2 - b1)/2
                if abs(c_x - c_a)/w_x < mfactor and abs(c_y - c_b)/h_y < mfactor:
                    if args.tracker_method == 'VLB':
                        if t - det > 0.5 and cnt == 0 and y1 > vlb:
                            peoplecounter += 1
                            counter_output(peoplecounter, c_s, c_x, c_y)
                            del faces[idx]
                            break
                        faces[idx] = (x1, y1, x2, y2, det, t, cnt)
                        break
                    else:
                        if t - det > 0.5 and cnt == 0 and y2 < vlb:
                            peoplecounter += 1
                            cnt = peoplecounter
                            counter_output(peoplecounter, c_s, c_x, c_y)
                        faces[idx] = (x1, y1, x2, y2, det, t, cnt)
                        cv2.putText(vis, str(cnt), (c_x, c_y), cv2.FONT_HERSHEY_PLAIN, 1.0, green, lineType=cv2.CV_AA)
                        break
            else:
                # Object not found in list means we add it to the list
                if y2 < vlb:                
                    faces.append([x1, y1, x2, y2, t, t, 0])
            if y2 < vlb:
                color = green
            else:
                color = red
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        cv2.putText(vis, "Visitors counted: " + str(peoplecounter), (21, 51), cv2.FONT_HERSHEY_PLAIN, 3.0, (0,0,0), thickness=2, lineType=cv2.CV_AA)
        cv2.putText(vis, "Visitors counted: " + str(peoplecounter), (20, 50), cv2.FONT_HERSHEY_PLAIN, 3.0, green, thickness=2, lineType=cv2.CV_AA)
        cv2.line(vis, (0, vlb + 1), (frame_width, vlb + 1), (0,0,0))        
        cv2.line(vis, (0, vlb), (frame_width, vlb), green)        
        cv2.imshow('OpenCV People Counter', vis)
        if 0xFF & cv2.waitKey(5) == 27:
            break
    cv2.destroyAllWindows()
