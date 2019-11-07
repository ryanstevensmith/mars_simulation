# -*- coding: utf-8 -*-
"""
Created on Sun Mar 24 16:20:52 2019
@author: Ryan Smith
"""

import numpy as np
import random

import colony_util as util
import colonists as col



# TODO: move to colony_utils.py
def arrivalFromEarth(arrivalDate, params):
    crew = []
    
    male_crew,female_crew = util.ratioCalculator(params.getSHIP_CAPACITY(), params.getCREW_RATIO())
    
    for x in range(0, male_crew):
        a = col.Astronaut("m", arrivalDate, params)
        crew.append(a)
    
    for y in range(0, female_crew):
        a = col.Astronaut("f", arrivalDate, params)
        crew.append(a)

    return crew

def simulation(params, label):
    colony = []
    sizes = []
    pregCounter = 0

    days = range(0, params.getSIM_LENGTH()) # creating an array of every day to put in a for loop

    for day in days:
        # check if a new martian year has started (26 months)
        if (day % (26*30) == 0):
            colony = colony + arrivalFromEarth(day, params)
                
        new_colonists = []
        for x in colony:
            # increase age of everybody by 1 if needsbe
            if (day % 365 == 0 and day > 0):
                x.incAge()
            
            # check if they will die
            #if (x.getAge() > params.getDEATH_THRESH()):
            if (random.random()<float(util.checkDeathProb(x.getAge()))):
                x.setDead()
                colony.remove(x)
            
            # model infant death?

            # check for and update pregnancies
            if (x.getSex() == "f"):
                
                # if 260 days have passed, check if a new colonist is born (logarithmic probabilty, see graph)
                if (x.getPregnant() >= params.getPREG_THRESH()):    # if it is positive then they are pregnant
                    #if util.checkBirthProb(x.getPregnant()):
                    if (random.random() < 0.05):
                        x.birth()
                        pregCounter = -1
                        new = col.Martian(day, params)
                        new_colonists = new_colonists + [new]
                elif (x.getPregnant() == -1 and (random.random() < float(util.checkBirthProb(x.getAge())))):       # not pregnant
                    x.startPregnant()
                elif (x.getPregnant() != -1):
                    x.incPregnant()
                
        # remove dead
        colony[:] = [x for x in colony if not x.isDead()]
            
            
        colony = colony + new_colonists
        sizes = sizes + [len(colony)]
        
        label.setText("Progress: " + str(day+1) + " of " + str(max(days)+1))

    for x in colony:
        print(x.getAge(), x.getSex(), x.getName())
        
    print(max(sizes))
    
    return colony, sizes
    '''
    x = Astronaut("m")
    y = Astronaut("f")
    a = Martian()
    b = Martian()
    c = Martian()
    print(x.getAge(), x.getSex(), x.getName())
    print(y.getAge(), y.getSex(), y.getName())
    print(a.getAge(), a.getSex(), a.isChild(), a.getName())
    print(b.getAge(), b.getSex(), b.isChild(), b.getName())
    print(c.getAge(), c.getSex(), c.isChild(), c.getName())
    '''