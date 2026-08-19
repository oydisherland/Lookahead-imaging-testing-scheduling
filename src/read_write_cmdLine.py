import datetime
from .get_target import GT, getGroundTargetObjectsFromJsonFile
from .objects import OT


def makecmdLineIntoDict(cmdLine: str) -> dict:
    """ Convert a command line string into a dictionary of its components
    Output:
    - cmdDict: dictionary with command flags as keys and their values as values
    """
    cmds = cmdLine.split(" ")
    cmds = [cmd for cmd in cmds if cmd != '']

    cmdDict = {}
    for i, cmd in enumerate(cmds[:-1]):

        cmdNext = cmds[i+1]
        
        # If cmd is a flag it starts with "-"
        if cmd.startswith("-"):

            if cmdNext.startswith("-"):
                try:
                    float(cmdNext)
                except ValueError:
                    # If the next command is not a number, skip it
                    continue

            cmdDict[cmd] = cmdNext
    
    return cmdDict


# Function that format schedule data into campaign planner commands
def createCaptureCmdLine(groundTarget: GT, hypsoNr: int, quaternions: dict, captureStart: datetime.datetime, captureEnd: datetime.datetime, predictedCloudCover: float) -> str: 
    """ Create the command line for capturing an observation task
    Output:
    - cmd_string: one command line string that Hypso can parse
    """
    if hypsoNr not in [1, 2]:
        print("Invalid hypsoNr")
        return None
    observationMiddleTime = captureStart + datetime.timedelta(seconds=(captureEnd - captureStart).seconds / 2)

    row = {}
    # Unix time
    row['-u'] = int(observationMiddleTime.timestamp())
    # DontKnow
    row['-s'] = None
    # DontKnow - Duration of buffering could be calculated based on image size
    row['-d'] = 2442 if hypsoNr == 1 else 975
    # Radio band
    row['-o'] = 0 if hypsoNr == 1 else 'auto2' 
    # Hypso number
    row['-hypso'] = hypsoNr
    # DontKnow
    row['-a'] = None
    # Geometry of capture
    row['-p'] = groundTarget.captureMode
    # Target name
    row['-n'] = groundTarget.id
    # Latitude
    row['-lat'] = float(groundTarget.lat)
    # Longitude
    row['-lon'] = float(groundTarget.long)
    # Elevation angle with sun
    row['--sunZenith'] = 45
    # Exposure time - get from targets.csv
    row['-e'] = float(groundTarget.exposureTime)
    # Quaternion r
    row['-r'] = quaternions['r']
    # Quaternion l
    row['-l'] = quaternions['l']
    # Quaternion j
    row['-j'] = quaternions['j']
    # Quaternion k
    row['-k'] = quaternions['k']
    # Capture mode
    row['--capture'] = None
    # Comment
    row['%'] = observationMiddleTime
    # Cloud cover 
    row['Predicted Cloud cover:'] = predictedCloudCover

    cmd_string = (
        f"-u {row['-u']}  -s -d {row['-d']:4d} -o {row['-o']:5} -hypso {row['-hypso']} -a -p {row['-p']:11}{'':2}"
        f" -n {row['-n']:20} -lat {round(row['-lat'], 4):8.4f} -lon {round(row['-lon'], 4):9.4f} --sunZenith {round((row['--sunZenith']),2):8.4f} {'           '}"
        f" -e {row['-e']:6.2f} -r {row['-r']:20.17f}  -l {row['-l']:20.17f}  -j {row['-j']:20.17f}  -k {row['-k']:20.17f}"
        f" {'':24} {'--capture':9} {'':9}"
        f" % {str(observationMiddleTime)} - Predicted Cloud cover: {row['Predicted Cloud cover:']:5.1f}\n"
    )

    return cmd_string

def createBufferCmdLine(bufferTime: datetime.datetime) -> str:
    return (
        f"-u {int(bufferTime.timestamp())} -d  975 -o auto2 -hypso 2 -a --buffertimestamp % {bufferTime.strftime('%Y-%m-%d %H:%M:%S.%f%z')}\n"
    )
## TODO: create a function that fixes all buffertimes in the cmdLineFile. Inserting and deleting depending on the capture tasks. 
def insertCmdLineIntoSchedule(captureUnixTime: int, newCmdLine: str, inputSchedule_filePath: str, outputSchedule_filepath: str, importantTargetIds_list: list) -> bool:
    """ Insert a command line into an existing schedule file, at the right place based on the capture time
    Output:
    - None, but the cmdLine is inserted into the file at the right place
    """
    

    with open(inputSchedule_filePath, 'r') as f:
        cmdLines = f.readlines()
    
    # Find the right place to insert the cmdLine based on captureUnixTime
    skipInsertion = False
    hasACaptureBeenRemoved = False
    spaceWeatherLinePassed = False
    
    for i, line in enumerate(cmdLines.copy()):

        # create a dictionary of cmd line
        current_cmdDict = makecmdLineIntoDict(line)

        # See if we have passed the spaceweather end line,
        if not spaceWeatherLinePassed and '--spaceweather_end' in line:
            # This line was the spaceweather end line, new cmdLines can be insterted after this one
            spaceWeatherLinePassed = True
            continue
        elif not spaceWeatherLinePassed:
            # Have not passed spaceweather end line yet, continue iterating
            continue
    

        # See if the new cmd should be inserted at this index, before current line
        minDurationBetweenTasks = current_cmdDict.get('-d', 975) # about 16 minutes
        timeBufferForLookaheadCapture = 260 # HARDCODED
        

        if line.startswith("-u"):
            lineUnixTime = int(line.split(" ")[1])
            
            if captureUnixTime - lineUnixTime < int(minDurationBetweenTasks) + timeBufferForLookaheadCapture and captureUnixTime - lineUnixTime > 0:
                # Time between current command and capture to insert is too close
                if "--buffertimestamp" in line:
                    # Remove buffer commands that are too close to the capture time
                    cmdLines.pop(cmdLines.index(line))
                    continue
                elif "--capture" in line:
                    # Colliding with capture, check if it can be removed
                    if current_cmdDict['-n'] in importantTargetIds_list:
                        # Current capture is important, cannot remove
                        break
                    else:
                        # Current capture is not as important, can remove
                        hasACaptureBeenRemoved = True
                        cmdLines.pop(cmdLines.index(line))
                        continue
            if lineUnixTime >= captureUnixTime:
                # Current command happends after capture to insert
                currentIndex = cmdLines.index(line)
                # Check if current command is too close to the capture time, if so, remove it
                if "--buffertimestamp" in line:
                    if lineUnixTime - captureUnixTime < int(minDurationBetweenTasks):
                        cmdLines.pop(currentIndex)
                elif "--capture" in line:
                    # Colliding with capture, check if it can be removed
                    if current_cmdDict['-n'] in importantTargetIds_list:
                        # Current capture is important, cannot remove
                        skipInsertion = True
                        break
                    else:
                        # Current capture is not as important, can remove
                        hasACaptureBeenRemoved = True
                        cmdLines.pop(currentIndex)
                cmdLines.insert(currentIndex, newCmdLine)
                
                if not hasACaptureBeenRemoved:
                    # Remove another capture that is close in time to newCmdLine, to make sure we are within downlink budget
                    maxInteration = len(cmdLines)
                    removeIndex = currentIndex
                    for _ in range(maxInteration):
                        if removeIndex + 1 < len(cmdLines):
                            # try to remove the next capture
                            removeIndex = removeIndex + 1
                            nextRemoveIndex = removeIndex + 1
                        elif removeIndex - 1 >= 0:
                            # try to remove the previous pass
                            removeIndex = removeIndex - 1
                            nextRemoveIndex = removeIndex - 1
                        else:
                            # No more captures to remove, cannot insert new cmdLine without colliding with important targets,
                            break
                        removeCandidate_line = cmdLines[removeIndex]
                        if "--capture" in removeCandidate_line:
                            # Try to remove this capture cmd
                            removeCandidate_cmdDict = makecmdLineIntoDict(removeCandidate_line)
                            if removeCandidate_cmdDict['-n'] in importantTargetIds_list:
                                # This capture is important, cannot remove, try another one
                                removeIndex = nextRemoveIndex
                                continue
                            else:
                                # This capture is not important, can remove
                                cmdLines.pop(removeIndex)
                                # insert new buffertask instead at same timeslot
                                middletime = int(removeCandidate_cmdDict['-u'])
                                newBufferCmd = createBufferCmdLine(datetime.datetime.fromtimestamp(middletime, tz=datetime.timezone.utc))
                                cmdLines.insert(removeIndex, newBufferCmd)
                                break
                break

    if skipInsertion:
        # New cmdLine could not be inserted bue to collinging high priority target
        return False

    # Write the updated cmdLines back to the file
    with open(outputSchedule_filepath, 'w') as f:
        f.writelines(cmdLines)
    return True
# test if this works somehow

# Functions to read command lines and recreate schedule data from them
def getObservationTaskFromCmdLine(targetFilePath: str, cmdLine: str, captureDurationSec: int = 60):
    """ Takes in a command line string and returns an OT object representing the same cmd and the type of command
    Output:
    - observationTask: OT object created from the command line
    - commandType: 'Capture', 'Buffer' or 'Unknown'
    """
    cmds = cmdLine.split(" ")
    cmds = [cmd for cmd in cmds if cmd != '']

    cmdDict = {}
    for i, cmd in enumerate(cmds[:-1]):

        cmdNext = cmds[i+1]
        
        # If cmd is a flag it starts with "-"
        if cmd.startswith("-"):

            if cmdNext.startswith("-"):
                try:
                    float(cmdNext)
                except ValueError:
                    # If the next command is not a number, skip it
                    continue

            cmdDict[cmd] = cmdNext
    
    # Recreate target data object to find objectiveValue
    #targetIdPriorityDict = getTargetIdPriorityDictFromJson(targetFilePath)
    allGTs = getGroundTargetObjectsFromJsonFile(targetFilePath)
    targetGT = None
    for gt in allGTs:
        if gt.id == cmdDict['-n']:
            targetGT = gt
            break
    # gt = GT(
    #         id=cmdDict['-n'],
    #         lat=cmdDict['-lat'],
    #         long=cmdDict['-lon'],
    #         priority=targetIdPriorityDict.get(cmdDict['-n'], 0),
    #         cloudCoverage=0,
    #         exposureTime=cmdDict['-e'],
    #         captureMode=cmdDict['-p']
    #     )
    if '--capture' in cmdDict:
        # convert start and end time to relative time
        timestamp = datetime.datetime.fromtimestamp(int(cmdDict['-u']), tz=datetime.timezone.utc)
        captureStart = timestamp - datetime.timedelta(seconds=captureDurationSec//2)
        captureEnd = timestamp + datetime.timedelta(seconds=captureDurationSec//2)

        observationTask = OT(
            GT = targetGT,
            start = captureStart,
            end = captureEnd
        )
        return observationTask
    else:
        return None

def recreateScheduleFromCmdLineFile(cmdLinesFilePath: str, targetFilePath: str, captureDurationSec: int = 60 ) -> list:
    """ Takes in a file path to a file containing command lines, and returns a list of OT objects representing the same schedule
    Output:
    - observationTasks: list of OT objects created from the command lines
    """
    observationTasks = []
    with open(cmdLinesFilePath, 'r') as f:
        cmdLines = f.readlines()
    
    for cmdLine in cmdLines:
        observationTask = getObservationTaskFromCmdLine(targetFilePath, cmdLine, captureDurationSec)
        if observationTask is not None:
            observationTasks.append(observationTask)

    return observationTasks