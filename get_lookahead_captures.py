from orbital_calculations import findIllumminationPeriods, findSatelliteTargetPasses, updateTLE, calculateQuaternions, findSatelliteTargetElevation
from get_target import getGroundTargetObjectsFromJsonFile, GT
from extract_coud_data import getCloudData
from read_write_cmdLine import createCaptureCmdLine, recreateScheduleFromCmdLineFile
import json
from collections import defaultdict
from bisect import bisect_left
import datetime
import os
from dataclasses import dataclass

@dataclass
class TargetPass:
    groundTarget: GT
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

def getLookaheadCaptureCandidates(planningStartTime: datetime.datetime, planningEndTime: datetime.datetime, hypsoNr: int, lookaheadTargets_jsonfilepath: str) -> list:
    """
    Input:
    - planningStartTime: datetime object representing the start time of the planning horizon
    - planningEndTime: datetime object representing the end time of the planning horizon
    - hypsoNr: int representing the HYPSO satellite number (1 or 2)
    - lookaheadTargets_jsonfilepath: str representing the file path to the lookahead target list
    Output:
    Creates a file "lookahead_candidates.txt" containing cmd lines for lookahead captures, sorted by difference in cloud level between the two passes, and contining information about the cloud levels, elevation and number of orbits between the passes.
    """

    updateTLE(hypsoNr)
    # Find a good candidate for t1 and t2, based on orbits starting at end of ground station pass
    t1 = planningStartTime
    t2 = planningEndTime

    # Define an orbit starting at groundstation, and ending at ground station
    groundStation = {}
    groundStation['lat'] = 78.2208
    groundStation['long'] = 15.4260
    groundStation['elevation'] = 0

    orbit_startTimes, orbit_endTimes = getStartAndEndTimeOfPasses(groundStation['lat'], groundStation['long'], groundStation['elevation'], t1, t2, hypsoNr, twMaxSeconds=3600)
    orbits = [(orbit_endTimes[i], orbit_startTimes[i + 1]) for i in range(len(orbit_startTimes) - 1)]

    # Get target data from JSON file
    GT_list = getGroundTargetObjectsFromJsonFile(lookaheadTargets_jsonfilepath)

    ### Get all daylight passes for every target between t1 and t2 ####
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
                    groundTarget=gt,
                    orbitIndex=i,
                    startTime=st,
                    endTime=et,
                    cloudLevel=cloudData[closestTime]
                )
                targetPasses[gt.id].append(newTargetPass)

    ##### Find pass pairs of consecutive orbits ####
    passPairs = []
    conecutiveOrbit_pairs = []

    for targetId, passes in targetPasses.items():
        if len(passes) <= 1:
            continue
            
        for i, targetPass in enumerate(passes[:-1]):
            
            nextPass = passes[i + 1]
            passPairs.append((targetPass, nextPass))

            if targetPass.orbitIndex == nextPass.orbitIndex:
                print(f"Same orbit pair for target {targetId}: \nOrbit {targetPass.orbitIndex} with cl {targetPass.cloudLevel} and start time {targetPass.startTime} \nOrbit {nextPass.orbitIndex} with cl {nextPass.cloudLevel} and start time {nextPass.startTime} \nDifference in cloud level: {nextPass.cloudLevel - targetPass.cloudLevel}\n")

            if nextPass.orbitIndex == targetPass.orbitIndex + 1:
                conecutiveOrbit_pairs.append((targetPass, nextPass))
                elevDeg1 = findSatelliteTargetElevation(float(targetPass.groundTarget.lat), float(targetPass.groundTarget.long), targetPass.startTime, hypsoNr)
                elevDeg2 = findSatelliteTargetElevation(float(nextPass.groundTarget.lat), float(nextPass.groundTarget.long), nextPass.startTime, hypsoNr)
                print(f"Consecutive orbit pair for target {targetId}: \nOrbit {targetPass.orbitIndex} with cl {targetPass.cloudLevel} and elevation {elevDeg1} \nOrbit {nextPass.orbitIndex} with cl {nextPass.cloudLevel} and elevation {elevDeg2} \nDifference in cloud level: {nextPass.cloudLevel - targetPass.cloudLevel}\n")

    print(f"Found {len(passPairs)} pass pairs of consecutive orbits for all targets")
    print(f"Found {len(conecutiveOrbit_pairs)} consecutive orbit pairs for all targets")


    # Sort 
    scored_passPairs = [
        (pass1, pass2, (pass1.cloudLevel - pass2.cloudLevel))
        for pass1, pass2 in passPairs
    ]


    sorted_passPairs_by_diff = sorted(scored_passPairs, key=lambda x: x[2], reverse=True)

    ## Sort out the top 5 pass pairs with the largest difference in cloud level
    lookaheadCmdLines = []

    for pass1, pass2, cloudsDiff in sorted_passPairs_by_diff:

        
        # print(f"Target {pass1.groundTarget.id} has cloud level {pass1.cloudLevel} in pass 1 (orbit {pass1.orbitIndex}), and cloud level {pass2.cloudLevel} in pass 2 (orbit {pass2.orbitIndex}), with a difference of {cloudsDiff}")
        # Calculate quaternians and create cmdLine for pass 1 and pass 2
        quaternions_pass1 = calculateQuaternions(hypsoNr, pass1.groundTarget, pass1.startTime)
        quaternions_pass2 = calculateQuaternions(hypsoNr, pass2.groundTarget, pass2.startTime)

        cmdLine_pass1 = createCaptureCmdLine(pass1.groundTarget, hypsoNr, quaternions_pass1, pass1.startTime, pass1.endTime, pass1.cloudLevel)
        cmdLine_pass2 = createCaptureCmdLine(pass2.groundTarget, hypsoNr, quaternions_pass2, pass2.startTime, pass2.endTime, pass2.cloudLevel)
        # print(f"CmdLine for pass 1: {cmdLine_pass1}")
        # print(f"CmdLine for pass 2: {cmdLine_pass2}")
        elevationpass1 = findSatelliteTargetElevation(float(pass1.groundTarget.lat), float(pass1.groundTarget.long), pass1.startTime, hypsoNr)
        elevationpass2 = findSatelliteTargetElevation(float(pass2.groundTarget.lat), float(pass2.groundTarget.long), pass2.startTime, hypsoNr)
        passinfo = f"Passses are {pass2.orbitIndex - pass1.orbitIndex} orbits appart, cloud level pass 1: {pass1.cloudLevel}, Cloud level pass 2: {pass2.cloudLevel}, Difference: {round(cloudsDiff, 2)}, Elevation pass 1: {round(elevationpass1, 2)}, Elevation pass 2: {round(elevationpass2, 2)} \n"
        lookaheadCmdLines.append((cmdLine_pass1, cmdLine_pass2, passinfo))

    ## See if it can be inserted into the schedule without overlap, and if so, insert it
    inputSchedule_FilePath = os.path.join(os.path.dirname(__file__), "campaign_scripts_h2_2026-05-28.txt")
    inputSchedule_otList = recreateScheduleFromCmdLineFile(inputSchedule_FilePath, lookaheadTargets_jsonfilepath, captureDurationSec = 60)

    # for cmdLine_pass1, cmdLine_pass2 in lookaheadCmdLines:
    #     # Look for colliding OTs in the schedule for pass 1 and pass 2
    #     ot_pass1 = getObservationTaskFromCmdLine(lookaheadTargets_jsonfilepath, cmdLine_pass1)
    #     ot_pass2 = getObservationTaskFromCmdLine(lookaheadTargets_jsonfilepath, cmdLine_pass2)   
    #     # Finish this

    ### Savet the output to files ###
    outputCmdLinesFilePath = os.path.join(os.path.dirname(__file__), "lookahead_candidates.txt")
    with open(outputCmdLinesFilePath, 'w') as f:    
        for cmdLine_pass1, cmdLine_pass2, passinfo in lookaheadCmdLines:
            f.write(cmdLine_pass1)
            f.write(cmdLine_pass2)
            f.write(passinfo + "\n")


### Run script ###
""""
Example run:

startTime = datetime.datetime.now((datetime.timezone.utc))
endTime = startTime + datetime.timedelta(hours=48)
hypsoNr = 2
targetFilePath = os.path.join(os.path.dirname(__file__), "lookahead_targets.json")

getLookaheadCaptureCandidates(startTime, endTime, hypsoNr, targetFilePath)

"""


