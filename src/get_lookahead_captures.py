from .orbital_calculations import findIllumminationPeriods, findSatelliteTargetPasses, updateTLE, calculateQuaternions, findSatelliteTargetElevation
from .get_target import getGroundTargetObjectsFromJsonFile, GT
from .objects import OT
from .extract_coud_data import getCloudData
from .read_write_cmdLine import createCaptureCmdLine, insertCmdLineIntoSchedule, makecmdLineIntoDict
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
    elevation: float

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

def getLookaheadCaptureCandidates(planningStartTime: datetime.datetime, planningEndTime: datetime.datetime, hypsoNr: int, lookaheadTargets_jsonfilepath: str, inputSchedule_filePath: str) -> list:
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
                    cloudLevel=cloudData[closestTime],
                    elevation=findSatelliteTargetElevation(float(gt.lat), float(gt.long), st + (et - st) / 2, hypsoNr)
                )
                targetPasses[gt.id].append(newTargetPass)

    ##### Find pass pairs of consecutive orbits ####
    passPairs = []
    conecutiveOrbit_pairs = []

    for targetId, passes in targetPasses.items():
        if len(passes) <= 1:
            # only one pass for this target, dont add to pass pairs list
            continue
            
        for i, targetPass in enumerate(passes[:-1]):
            
            nextPass = passes[i + 1]
            passPairs.append((targetPass, nextPass))

            if targetPass.orbitIndex == nextPass.orbitIndex:
                print(f"Same orbit pair for target {targetId}: \nOrbit {targetPass.orbitIndex} with cl {targetPass.cloudLevel} and start time {targetPass.startTime} \nOrbit {nextPass.orbitIndex} with cl {nextPass.cloudLevel} and start time {nextPass.startTime} \nDifference in cloud level: {nextPass.cloudLevel - targetPass.cloudLevel}\n")

            if nextPass.orbitIndex == targetPass.orbitIndex + 1:
                conecutiveOrbit_pairs.append((targetPass, nextPass))
                # elevDeg1 = targetPass.elevation
                # elevDeg2 = nextPass.elevation
               # print(f"Consecutive orbit pair for target {targetId}: \nOrbit {targetPass.orbitIndex} with cl {targetPass.cloudLevel} and elevation {elevDeg1} \nOrbit {nextPass.orbitIndex} with cl {nextPass.cloudLevel} and elevation {elevDeg2} \nDifference in cloud level: {nextPass.cloudLevel - targetPass.cloudLevel}\n")

    print(f"Found {len(passPairs)} pass pairs of for all targets in lookahead target list")


    # Sort the list after decreasing differnce in cloud level and increasing cloud level
    passPairs_cloudDiff = [
        (pass1, pass2)
        for pass1, pass2 in passPairs
    ]
    # Sort list after decreasing difference in cloud level between 1st and second pass 
    cloudDiffSorted_passPairs = sorted(passPairs_cloudDiff, key=lambda x: (x[0].cloudLevel - x[1].cloudLevel), reverse=True)
    
    passPairs_cloudLevel = [
        (pass1, pass2)
        for pass1, pass2 in passPairs
    ]
    # Sort list after increasing cloud coverage of first pass
    cloudLevelSorted_passPairs = sorted(passPairs_cloudLevel, key=lambda x: x[0].cloudLevel, reverse=False)

    # Combine the two soreted lists
    sorted_passPairs = []
    for cloudDiffPair, cloudLevelPair in zip(cloudDiffSorted_passPairs, cloudLevelSorted_passPairs):
        if cloudDiffPair not in sorted_passPairs:
            sorted_passPairs.append(cloudDiffPair)
        if cloudLevelPair not in sorted_passPairs:
            sorted_passPairs.append(cloudLevelPair) 

    ## Sort out the top 5 pass pairs with the largest difference in cloud level
    lookaheadCmdLines = []
    outputSchedule_filepath = os.path.join(os.path.dirname(__file__), "..", "example_input", "campaign_scripts_h2_2026-05-28_updated.txt")
    inputOverloded_filepath = os.path.join(inputSchedule_filePath.rsplit(".", 1)[0] + "_overloaded.txt")
    importantGT_ids= [gt.id for gt in getGroundTargetObjectsFromJsonFile(os.path.join(os.path.dirname(__file__), "..","important_targets.json"))]

    maxInsertions = 5   # Hardcoded

    for pass1, pass2 in sorted_passPairs:
        cloudsDiff = pass1.cloudLevel - pass2.cloudLevel

        
        # print(f"Target {pass1.groundTarget.id} has cloud level {pass1.cloudLevel} in pass 1 (orbit {pass1.orbitIndex}), and cloud level {pass2.cloudLevel} in pass 2 (orbit {pass2.orbitIndex}), with a difference of {cloudsDiff}")
        # Calculate quaternians and create cmdLine for pass 1 and pass 2
        quaternions_pass1 = calculateQuaternions(hypsoNr, pass1.groundTarget, pass1.startTime)
        quaternions_pass2 = calculateQuaternions(hypsoNr, pass2.groundTarget, pass2.startTime)

        cmdLine_pass1 = createCaptureCmdLine(pass1.groundTarget, hypsoNr, quaternions_pass1, pass1.startTime, pass1.endTime, pass1.cloudLevel)
        cmdLine_pass2 = createCaptureCmdLine(pass2.groundTarget, hypsoNr, quaternions_pass2, pass2.startTime, pass2.endTime, pass2.cloudLevel)
        # print(f"CmdLine for pass 1: {cmdLine_pass1}")
        # print(f"CmdLine for pass 2: {cmdLine_pass2}")
        elevationpass1 = pass1.elevation
        elevationpass2 = pass2.elevation
        passinfo = f"Passses are {pass2.orbitIndex - pass1.orbitIndex} orbits appart, cloud level pass 1: {pass1.cloudLevel}, Cloud level pass 2: {pass2.cloudLevel}, Difference: {round(cloudsDiff, 2)}, Elevation pass 1: {round(elevationpass1, 2)}, Elevation pass 2: {round(elevationpass2, 2)} \n"
        lookaheadCmdLines.append((cmdLine_pass1, cmdLine_pass2, passinfo))

        if maxInsertions <= 0:
            break
        

        # try to insert pass 1 into schedule
        middletime = pass1.startTime + (pass1.endTime - pass1.startTime) / 2
        couldInsertImage = insertCmdLineIntoSchedule(int(middletime.timestamp()), cmdLine_pass1, inputSchedule_filePath, outputSchedule_filepath, importantGT_ids)
        if not couldInsertImage:
            print(f"Could not insert cmdLine for target {pass1.groundTarget.id} into schedule file {inputSchedule_filePath} without overlap with important targets")
            continue
        # try to insert pass 2 into schedule
        middletime = pass2.startTime + (pass2.endTime - pass2.startTime) / 2
        couldInsertImage = insertCmdLineIntoSchedule(int(middletime.timestamp()), cmdLine_pass2, outputSchedule_filepath, inputOverloded_filepath, importantGT_ids)
        if not couldInsertImage:
            print(f"Could not insert cmdLine for target {pass2.groundTarget.id} into schedule file {inputSchedule_filePath} without overlap with important targets")
            continue    
        maxInsertions -= 1
        # write the updated schedule to file
        with open(inputOverloded_filepath, 'r') as f:
            cmdLines = f.readlines()
        with open(inputSchedule_filePath, 'w') as f:
            
            for line in cmdLines:
                cmdDict = makecmdLineIntoDict(line)
                if cmdDict["-u"] == int((pass2.startTime + (pass2.endTime - pass2.startTime) / 2).timestamp()):
                    # this is the line we just inserted, so we skip it since we will add the updated version of it with the new cmdLine
                    print(f"Skipping line with time {cmdDict['-u']} since this is the line we just inserted, and we will add the updated version of it with the new cmdLine")
                    continue
                f.write(line)
            #f.writelines(cmdLines)
        # remove the temporary updated schedule file
        if os.path.exists(outputSchedule_filepath):
            os.remove(outputSchedule_filepath)

    # Save the recreateCandidates to file ###
    outputCmdLinesFilePath = os.path.join(os.path.dirname(__file__), "..","lookahead_candidates.txt")
    with open(outputCmdLinesFilePath, 'w') as f:    
        for cmdLine_pass1, cmdLine_pass2, passinfo in lookaheadCmdLines:
            f.write(cmdLine_pass1)
            f.write(cmdLine_pass2)
            f.write(passinfo + "\n")

    print(f"- Created cmdLines for {5 - maxInsertions} lookahead capture candidates\n",
          "- Inserted first pass into {inputSchedule_filePath}\n",
          "- Inserted pass1 and pass 2 into {inputOverloded_filepath}\n",
          "- Only the inserted cmdlines are in file {outputCmdLinesFilePath}")

### Run script ###
""""
Example run:

startTime = datetime.datetime.now((datetime.timezone.utc))
endTime = startTime + datetime.timedelta(hours=48)
# or
startTime = datetime.datetime(2026, 6, 2, 8, 0, 0, tzinfo=datetime.timezone.utc)
endTime = startTime + datetime.timedelta(hours=24)

hypsoNr = 2
targetFilePath = os.path.join(os.path.dirname(__file__), "lookahead_targets.json")
inputSchedule_filePath = os.path.join(os.path.dirname(__file__), "campaign_scripts_h2_2026-05-28.txt")

getLookaheadCaptureCandidates(startTime, endTime, hypsoNr, targetFilePath, inputSchedule_filePath)

"""
