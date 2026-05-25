from orbital_calculations import findIllumminationPeriods, findSatelliteTargetPasses, updateTLE
from get_target import getGroundTargetObjectsFromJsonFile, GT
from extract_coud_data import getCloudData
import json
from collections import defaultdict
from bisect import bisect_left
import datetime
import os
from dataclasses import dataclass

@dataclass
class TargetPass:
    targetId: str
    orbitIndex: int
    startTime: datetime.datetime
    endTime: datetime.datetime
    cloudLevel: float

def getStartAndEndTimeOfPasses(targetLat: float, targetLong: float, targetElevation: float, startTime: datetime.datetime, endTime: datetime.datetime, hypsoNr: int, twMaxSeconds = 500) -> tuple:
    """ Get the start and end time of a list of passes
    Input: list of passes, where each pass is a tuple of (time, event)
    Output: tuple of (startTimes, endTimes), where startTimes and endTimes are lists of datetime objects
    """
    passes = findSatelliteTargetPasses(targetLat, targetLong, targetElevation, startTime, endTime, hypsoNr)

    if not passes:
        return [], []

    # define start and end time of pass
    startTimes = []
    endTimes = []
    captureTimeSeconds = 60
    for i in range(len(passes) - 2):
        if passes[i][1] == 'rise' and passes[i + 1][1] == 'culminate' and passes[i + 2][1] == 'set':
            # The pass i -> i+2 corresponds to a time window

            time_diff = (passes[i + 2][0] - passes[i][0]).total_seconds()
            if time_diff < captureTimeSeconds or time_diff > twMaxSeconds:
                # Time window too short or too long
                continue

            # Add tw to start and end times
            startTimes.append(passes[i][0])
            endTimes.append(passes[i + 2][0])

    
    # If all start times are removed by time constraints, go to next target
    if len(startTimes) == 0:
        return [], []

    # Check that number of start times is equal number of end times
    if len(startTimes) != len(endTimes):
        print(f"len passes: {len(passes)}, firstpass: {passes[0][1]}, lastpass: {passes[-1][1]}, len startTimes: {len(startTimes)}, len endTimes: {len(endTimes)}")
        for p in passes:
            print(p)
        raise ValueError("The length of start times and end times are not equal")
    
    return startTimes, endTimes



hypsoNr = 2

updateTLE(hypsoNr)
# Find a good candidate for t1 and t2, based on orbits starting at end of ground station pass
t1 = datetime.datetime.now((datetime.timezone.utc))
t2 = t1 + datetime.timedelta(hours=48)

# Define an orbit starting at groundstation, and ending at ground station
groundStation = {}
groundStation['lat'] = 78.2208
groundStation['long'] = 15.4260
groundStation['elevation'] = 12

orbit_startTimes, orbit_endTimes = getStartAndEndTimeOfPasses(groundStation['lat'], groundStation['long'], groundStation['elevation'], t1, t2, hypsoNr, twMaxSeconds=3600)
orbits = [(orbit_endTimes[i], orbit_startTimes[i + 1]) for i in range(len(orbit_startTimes) - 1)]

# Get target data from JSON file
GT_list = getGroundTargetObjectsFromJsonFile(os.path.join(os.path.dirname(__file__), "targets.json"))

#### Get all daylight passes for every target between t1 and t2 ####
targetPasses = defaultdict(list)
for gt in GT_list:      
    startTimes, endTimes = getStartAndEndTimeOfPasses(gt.lat, gt.long, gt.elevation, t1, t2, hypsoNr)
    
    ### Remove non daylight passes ###
    daylightPeriods = findIllumminationPeriods(float(gt.lat), float(gt.long), t1, t2)
    index_startTimes = 0
    for  st in startTimes:
        illuminated = False
        for sunRise, sunSet in daylightPeriods:
            if sunRise <= st <= sunSet:
                illuminated = True
                break
        if not illuminated:
            startTimes.pop(index_startTimes)
            endTimes.pop(index_startTimes)
        else:
            index_startTimes += 1
    
    if len(startTimes) == 0:
        continue
    
    ### Find cloud level for each pass ###
    cloudData = getCloudData(gt.lat, gt.long, t1, t2)
    if cloudData is None or len(cloudData) == 0:
        raise ValueError("No cloud data available for the given pass")

    # Get the cloud level at the time of the pass
    predictionTimes = sorted(cloudData.keys()) 

    ### Find orbit index corresponding to the target passes ###
    for st, et in zip(startTimes, endTimes):
        for i, (orbitStart, orbitEnd) in enumerate(orbits):
            
            if st <= orbitStart or et >= orbitEnd:
                # pass is not within this orbit
                continue

            # Find which predictiontime is closest to the starttime of the pass
            pos = bisect_left(predictionTimes, st)
            if pos == 0:
                closestTime = predictionTimes[0]
            elif pos == len(predictionTimes):
                closestTime = predictionTimes[-1]
            else:
                before = predictionTimes[pos - 1]
                after = predictionTimes[pos]
                if abs((after - st).total_seconds()) < abs((st - before).total_seconds()):
                    closestTime = after
                else:
                    closestTime = before

            # Add targetpass data to list of passes
            newTargetPass = TargetPass(
                targetId=gt.id,
                orbitIndex=i,
                startTime=st,
                endTime=et,
                cloudLevel=cloudData[closestTime]
            )
            targetPasses[gt.id].append(newTargetPass)

##### Find pass pairs of consecutive orbits ####
passPairs = []

for targetId, passes in targetPasses.items():
    if len(passes) <= 1:
        continue
        
    for i, targetPass in enumerate(passes[:-1]):
        
        nextPass = passes[i + 1]
        passPairs.append((targetPass, nextPass))

print(f"Found {len(passPairs)} pass pairs of consecutive orbits for all targets")


# Sort 
scored_passPairs = [
    (pass1, pass2, (pass1.cloudLevel - pass2.cloudLevel))
    for pass1, pass2 in passPairs
]


sorted_passPairs_by_diff = sorted(scored_passPairs, key=lambda x: x[2], reverse=True)

for pass1, pass2, cloudsDiff in sorted_passPairs_by_diff:
    if cloudsDiff < 0:
        # We only want pairs where the cloud level is better in the second pass
        break
    print(f"Target {pass1.targetId} has cloud level {pass1.cloudLevel} in pass 1 (orbit {pass1.orbitIndex}), and cloud level {pass2.cloudLevel} in pass 2 (orbit {pass2.orbitIndex}), with a difference of {cloudsDiff}")
    



# Create cmdLine for a given pass-pair 


