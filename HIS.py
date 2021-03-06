#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: guth
"""


import RPi.GPIO as GPIO
import time
from time import sleep

import os
from apscheduler.schedulers.background import BackgroundScheduler

import csv
import paho.mqtt.client as mqtt
import gvar

os.chdir(os.path.dirname(__file__))


##### Remove if no serial required    
import serial
serialArray = [0,1]


# GPIO setup
GPIO.cleanup()
GPIO.setmode(GPIO.BCM) # GPIO Numbers instead of board numbers

pumpPin = 14

USTriggerPin = 24
USEchoPin = 23
    
GPIO.setup(pumpPin, GPIO.OUT) # GPIO Assign mode
GPIO.output(pumpPin, GPIO.LOW) #


GPIO.setup(USTriggerPin,GPIO.OUT)
GPIO.setup(USEchoPin,GPIO.IN)
GPIO.output(USTriggerPin, False)




#Setup MQTT:
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    if rc == 0:
        print("-> This means we connected successfully")
        log("Connection to server successfull",2)
    else:
        print("Major connection error")
        raise SystemExit

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    
    client.subscribe("HIS/Plant/Pump/setOn")
    client.subscribe("HIS/Plant/WaterTarget/setIncrease")
    client.subscribe("HIS/Plant/WaterTarget/setDecrease")
    client.subscribe("HIS/enableAutomaticWatering/setOn")


def resetHomeBridgeButtons():
    gvar.runnerTimeSinceCheck += gvar.timeUntilRefresh
    log("Refeshing Homekit",3)
    log("Time since last CheckAndWater: "+str(gvar.runnerTimeSinceCheck)+ " min",3)
    client.publish("HIS/Plant/WaterTarget/getIncrease", "false")
    client.publish("HIS/Plant/WaterTarget/getDecrease", "false")
    client.publish("HIS/Plant/WaterTarget/currentValue", gvar.targetMoisture)
    if gvar.enableAutomaticWatering:
        client.publish("HIS/enableAutomaticWatering/getOn", "true")
    else:
        client.publish("HIS/enableAutomaticWatering/getOn", "false")
        
    client.publish("HIS/Plant/currentMoisture", gvar.currentmoisture)
    client.publish("HIS/Reservoir/Percentage", gvar.currentTank)
    

def on_message(client, userdata, msg):
    messageText = str(msg.payload, 'utf-8')
    print(msg.topic+" "+str(msg.payload))
    log(msg.topic+" "+ messageText,4)
    #CHECK FOR PLANT SPECIFIC MESSAGES
    if msg.topic == "HIS/Plant/Pump/setOn":
        if messageText == "true":
            client.publish("HIS/Plant/Pump/getOn", "true")
            log("Turned on water on Plant via MQTT",2)
            forceWaterPlant(gvar.runPumpSec)
            client.publish("HIS/Plant/Pump/getOn", "false")
        if messageText == "false":
            client.publish("HIS/Plant/Pump/getOn", "false")
            stopPump()

    if msg.topic == "HIS/Plant/WaterTarget/setIncrease":
        gvar.targetMoisture +=1
        client.publish("HIS/Plant/WaterTarget/currentValue", gvar.targetMoisture)
        #writeNewTargetMoistures()
    if msg.topic == "HIS/Plant/WaterTarget/setDecrease":
        gvar.targetMoisture -= 1
        client.publish("HIS/Plant/WaterTarget/currentValue", gvar.targetMoisture)
        #writeNewTargetMoistures()
            
    if msg.topic == "HIS/enableAutomaticWatering/setOn":
        if messageText == "true":
            client.publish("HIS/enableAutomaticWatering/getOn", "true")
            gvar.enableAutomaticWatering = True
            log("Tried turning on enableAutomaticWatering, new State: " + str (gvar.enableAutomaticWatering),2)
        if messageText == "false":
            client.publish("HIS/enableAutomaticWatering/getOn", "false")
            gvar.enableAutomaticWatering = False
            log("tried turning off enableAutomaticWatering, new State: " + str (gvar.enableAutomaticWatering),2)


def log(text, level):
    if level <= gvar.debuglevel:
        print(gvar.debugStr[level]+text)
        client.publish("HIS/Log", gvar.debugStr[level]+text)       
        

def forceWaterPlant(time):
    runPump(time)

def stopPump():
    GPIO.output(pumpPin, GPIO.LOW)
    log("Stopping Pump",2)

def runPump(time):
    log("Starting Pump",2)
    client.publish("HIS/MotionSensor/Watering", "true")
    GPIO.output(pumpPin, GPIO.HIGH)
    sleep(time)
    GPIO.output(pumpPin, GPIO.LOW)
    log("Stopping Pump",2)
    client.publish("HIS/MotionSensor/Watering", "false")



##### Remove if no serial required    
    
def readMoistureSerial(devNum):
    hasRead = False
    try:
        with serial.Serial("/dev/ttyACM"+str(devNum), 115200, timeout=2) as ser:
            line = ser.readline()
            hasRead = True
    
        if hasRead:
            print(line)
            string = str(line, 'utf-8')
            a = string.split(",")
            return  [float(a[2]),float(a[3])]
        else:
            print("No input")
            return [-1,-1]
    except:
        print("Sensor "+str(devNum)+" not connected")
        return [-2,-2]


def getWaterPerc():
     #fist check if water in tank:
    log("Getting Waterlevel now",3)
    percTank = getPercFullTank()
    log("Tank " + str(percTank) + "% full",2)
    if percTank >100:
        percTank = 100
    if percTank <0:
        percTank = 0
    client.publish("HIS/Reservoir/Percentage", int(percTank))
    if percTank <= 5:
        gvar.alarmTankEmpty = True
        log("Tank empty, sending alarm soon, trying to water anyway",1)
    else:
        gvar.alarmTankEmpty = False
        
    gvar.currentTank = int(percTank)

def checkAndWater():
    log("Starting CheckAndWater",3)
   

    sensorDataT=[]
    averageMoisture=0
    averageTemp=0
    sensorDataM=[]
    for i in serialArray:        
            sensorArray = readMoistureSerial(devNum = serialArray[i])
            if sensorArray[1] >= 0:
                sensorDataM.append(sensorArray[1])
                sensorDataT.append(sensorArray[0])
                log("S"+ str(serialArray[i]) + ": Temperature: " + str(sensorArray[0]) + ", Moisture: " + str(sensorArray[1]*100)+"%", 2)

    for i in sensorDataM:
            averageMoisture+=i/len(sensorDataM)

    for i in sensorDataT:
            averageTemp+=i/len(sensorDataT)  

    time.sleep(0.5)
    log("Moisture: "+str(averageMoisture),0)
    log("Temp: "+str(averageTemp),0)

    client.publish("HIS/Plant/currentMoisture", int(averageMoisture*100))
    client.publish("HIS/Plant/currentTemp", int(averageTemp))
    
    gvar.currentmoisture = int(averageMoisture*100)
    
    gvar.runnerTimeSinceCheck = 0
    
    if averageMoisture*100 < gvar.targetMoisture:
        log("Watering needed!", 2)
        if gvar.enableAutomaticWatering:   
            log("Automatic Watering enabled",2)
            if not gvar.alarmTankEmpty or gvar.waterEmptyTank:
                log("Tank filled! Watering now!",2)
                runPump(gvar.runPumpSec)
            else:
                log("Tank empty! Aborting Watering!",2)
        else:
            log("Automatic Watering disabled",1)
            log("Will therefore not water!!!",1)
    

    
    #ALARMS
    if gvar.alarmTankEmpty and gvar.alarmTankEmptyDidAlarm == False:
        client.publish("HIS/MotionSensor/Alarm/Water", "true")
        time.sleep(3)
        client.publish("HIS/MotionSensor/Alarm/Water", "false")
        gvar.alarmTankEmptyDidAlarm = True
 
    if gvar.alarmMoistureLow and gvar.alarmMoistureLowDidAlarm == False:
        sleep(10)
        client.publish("HIS/MotionSensor/Alarm/Moisture", "true")
        time.sleep(3)
        client.publish("HIS/MotionSensor/Alarm/Moisture", "false")
        gvar.alarmTankEmptyDidAlarm = True
    
        
def measureUS():
    GPIO.output(USTriggerPin, True)

    sleep(0.00001)

    GPIO.output(USTriggerPin, False)
    while GPIO.input(USEchoPin)==0:

        pulse_start = time.time()

    while GPIO.input(USEchoPin)==1:

        pulse_end = time.time() 

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    distance = round(distance, 2)
    return distance

def getPercFullTank():
    distanceA = []
    log("Measuring Waterlevel (should be between " +str(gvar.distanceEmpty)+" and "+str(gvar.distanceFull)+"cm )",2)
    for i in range(10):
        distance = measureUS()
        log("Measured Distance " + str(distance)+ "cm",4)
        distanceA.append(distance)
        sleep(1)
    if max(distanceA)-min(distanceA)>3:
        log("Discard " + str(max(distanceA)) + " and " + str(min(distanceA)),3)
        distanceA.remove(max(distanceA))
        distanceA.remove(min(distanceA))
    averageDist = 0
    for a in distanceA:
        averageDist += a/len(distanceA)
    log("Average distance is " + str(averageDist)+ "cm",2)
        
    return int(gvar.distanceEmpty - averageDist)*100/(gvar.distanceEmpty-gvar.distanceFull)

def writeNewTargetMoistures():
    try:
        with open(gvar.pathMoisture, 'w') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=',',quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerow(["Moisture"]+gvar.targetMoisture)
            log("values saved",2)
    except:
        log("Couldn't save values",1)

def resetAlarmSuppression():
    gvar.alarmTankEmptyDidAlarm = False
    gvar.alarmMoistureLowDidAlarm = False
    

def readSettingFiles():
    try:
        with open(gvar.pathMoisture) as csvDataFile:
            log("Setting Moisture Target Values",2)
            csvReader = csv.reader(csvDataFile)
            for row in csvReader:
                    log("SensTarget: "+ str(int(row[1])),3)
                    gvar.targetMoisture = int(row[1])
    except:
        log("Unable to get Moisture Setting File",1)
        if not os.path.isfile(gvar.pathMoisture):
            writeNewTargetMoistures()
            
        

    try:
        with open(gvar.pathUS) as csvDataFile:
            log("Setting Distance Values for US",2)
            csvReader = csv.reader(csvDataFile)
            i=0
            for row in csvReader:
                if i == 0:
                    gvar.distanceEmpty = float(row[1])
                    log("Empty: " + row[1],3)
                else:
                    gvar.distanceFull = float(row[1])
                    log("Full: " + row[1],3)

                i += 1                  
    except:
        log("Unable to read US Settings File. Did you run calib.py? Starting with default values: 5cm full, 50cm empty",1)


if __name__ == "__main__":
    time.sleep(10.0) # wait for everything to connect (Wifi, etc)
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("10.0.0.16", 1883, 60)
    client.loop_start()
    sleep(2)
    log("MQTT Started",2)
    log("Waiting For Everything To Settle",2)
    sleep (5)
    readSettingFiles()
    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.


    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(checkAndWater, 'interval', minutes=11)
    scheduler.add_job(resetHomeBridgeButtons, 'interval', minutes=gvar.timeUntilRefresh)
    scheduler.add_job(resetAlarmSuppression, 'cron', hour=18, minute=0, second=0)
    scheduler.add_job(getWaterPerc, 'interval', minutes=30)

    
    try: 
        checkAndWater()
        while True:
            time.sleep(10.0)
                

    except KeyboardInterrupt:  
        print ("Exiting program" )

  
    finally:  
        stopPump()
        GPIO.cleanup()
        print ("done")
