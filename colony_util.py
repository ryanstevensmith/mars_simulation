import random
import numpy as np
import csv

# Functions used to calculate probabilities
def checkDeathProb(age):
    
    ##################### old code ##########################
    # See the shape of the function here (logarithmic):
    # https://www.desmos.com/calculator/8keivyyfqk
    #k = 1/25 #  vertical strech of function - larger denominator = larger strech
    #a = 95 # translation - x at which probability = 1
    #prob = np.log(k*(age-a) + np.e)
    
    # draw a random decimal between 0 and 1
    # return true if smaller than the resulting probability
    #return random.random() < prob

    ###################### new code ##########################
    probabilities = []

    with open('death_prob.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        linecount=0
        for row in csv_reader:
            probabilities.append(row[1])
            linecount+=1

        #print(*probabilities, sep = ", ")  
    #print (probabilities[age-1])    

    return probabilities[age-1]

def checkBirthProb(age):
    # return probabillity that the person is pregnant

    ###################### Old code ###########################
    # See the shape of the function here (logarithmic):
    #https://www.desmos.com/calculator/1jpwftgju8
    #k = 1/35 #  vertical strech of function - larger denominator = larger strech
    #a = 295 # translation - x at which probability = 1
    #prob = np.log(k*(preg-a) + np.e)
    
    # draw a random decimal between 0 and 1
    # return true if smaller than the resulting probability
    #return random.random() < prob

    ###################### new code ############################
    # a list of probabilities
    probabilities = []

    with open('preg_prob.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        linecount=0
        for row in csv_reader:
            probabilities.append(row[1])
            linecount+=1

        #print(*probabilities, sep = ", ")  
    #print (probabilities[age])    

    return probabilities[age-1]
    
def ratioCalculator(capacity, ratio):

    male_crew = int((ratio/(ratio + 1)) * capacity)
    female_crew = capacity - male_crew
    
    return male_crew, female_crew
    