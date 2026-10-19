# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 17:30:50 2019
@author: matej
"""

# Module governing the attributes of the colonists

DAYS_PER_YEAR = 365


class Colonist:
    __slots__ = ("sex", "birth_day", "arrival_date", "pregnant_days", "cooldown_until", "uid", "home")

    def __init__(self, age, sex, arrival_date):
        self.sex = sex
        # age is derived from the day number, so everyone has their own birthday
        self.birth_day = arrival_date - age * DAYS_PER_YEAR
        self.arrival_date = arrival_date
        self.pregnant_days = None   # None = not pregnant, else days pregnant so far
        self.cooldown_until = 0     # first day a new pregnancy may start
        self.uid = -1               # unique id, assigned by the simulation
        self.home = 0               # index of the ship (habitat module) they live in

    def getAge(self, day):
        """Age in whole years on the given simulation day."""
        return (day - self.birth_day) // DAYS_PER_YEAR

    def getSex(self):
        return self.sex

    def getArrivalDate(self):
        return self.arrival_date

    def isPregnant(self):
        return self.pregnant_days is not None

    def startPregnant(self):
        self.pregnant_days = 0

    def incPregnant(self):
        self.pregnant_days += 1

    def birth(self, day, cooldown):
        """End the pregnancy and block a new one for `cooldown` days."""
        self.pregnant_days = None
        self.cooldown_until = day + cooldown


class Astronaut(Colonist):

    def __init__(self, sex, arrival_date, rng):
        Colonist.__init__(self, rng.randint(25, 45), sex, arrival_date)

    def getName(self):
        return "Astronaut"


class Martian(Colonist):

    def __init__(self, arrival_date, rng):
        Colonist.__init__(self, 0, rng.choice(["m", "f"]), arrival_date)

    def getName(self):
        return "Martian"
