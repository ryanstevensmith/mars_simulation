# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 17:30:50 2019
@author: matej
"""

# Module gonverning the attributes of the colonists

import random
from random import randint

class Colonist:
    
    def __init__(self, age, sex, arrivalDate, params):
        self.age = age
        self.sex = sex
        self.pregnant = -1
        self.dead = False
        self.cooldown = 0
        self.arrivalDate = arrivalDate
        self.params = params
    
    # return the age
    def getAge(self):
        return self.age
    
    # return the sex
    def getSex(self):
        return self.sex
    
    # increase age by 1
    def incAge(self):
        self.age = self.age+1
    
    # increment pregnat value by 1 (how many days pregnant)
    def incPregnant(self):
        self.pregnant = self.pregnant+1
        
    # return pregnancy state    
    def getPregnant(self):
        return self.pregnant
    
    # start a pregnancy
    def startPregnant(self):
        self.pregnant = 0
    
    # give birth, reset internal counter
    def birth(self):
        self.pregnant = -1
        self.cooldown = self.params.getCOOLDOWN()
        
    # return bool whether it is below 18 (a child)
    def isChild(self):
        return self.age<18
    
    # set the person to dead
    def setDead(self):
        self.dead = True
    
    # returns mortality state
    def isDead(self):
        return self.dead
    
    def setCooldown(self, cool):
        self.cooldown = cool
    
    def getCooldown(self):
        return self.cooldown
    
    def decCooldown(self):
        self.cooldown = self.cooldown-1

    # set the date they arrived (or were born)
    def setArrivalDate(self, date):
        self.arrivalDate = date

    ## return the arrival date of the person
    def getArrivalDate(self):
        return self.arrivalDate

    
class Astronaut(Colonist):
    
    def __init__(self, sex, arrivalDate, params):
        Colonist.__init__(self, randint(25,45), sex, arrivalDate, params)
        
    def getName(self):
        return "Astronaut"
    
class Martian(Colonist):
    
    def __init__(self, arrivalDate, params):
        Colonist.__init__(self, 0, random.choice(["m", "f"]), arrivalDate, params)
        
    def getName(self):
        return "Martian"