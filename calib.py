#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May  2 18:38:39 2020

@author: guth
"""
#from time import sleep
import csv

import os 


os.chdir(os.path.dirname(__file__))
import gvar
import HIS

if not os.path.exists("/home/pi/.HIS"):
    os.makedirs("/home/pi/.HIS")


x = input("Set watersensor on water tank w/o water, then press enter. write >n< to skip measurements")
if not x == "n":
    avDistanceE = 0.0
    for i in range (10):
        distance = HIS.measureUS()
        avDistanceE += distance/10

    y = input("Fill WaterTank, then press Enter")
    
    avDistanceF = 0.0
    for i in range (10):
        distance = HIS.measureUS()
        avDistanceF += distance/10
        
    with open(gvar.pathUS, 'w') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',quotechar='"', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(["Empty:"]+[avDistanceE])
            spamwriter.writerow(["Full :"]+[avDistanceF])
    print("values saved")
    
    
    
    
    