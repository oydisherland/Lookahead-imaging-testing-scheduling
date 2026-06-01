import datetime
from get_target import GT, getGroundTargetObjectsFromJsonFile, getTargetIdPriorityDictFromJson
from objects import OT



#### FUNCTIONS TO CREATE CAMPAIGN PLANNER COMMAND LINES ####

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
    row['-d'] = 2442 if hypsoNr == 1 else 1509
    # Radio band
    row['-o'] = 0 if hypsoNr == 1 else 'xband' 
    # Hypso number
    row['-hypso'] = hypsoNr
    # DontKnow, maby registernumber where it is buffered, should probably be sat otherwise then, blir endret senere
    row['-b'] = 19
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

    cmd_string = f'-u {row['-u']} -s -d {row['-d']:4d} -o {row['-o']:5} -hypso {row['-hypso']} -b {row['-b']} -a -p {row['-p']:11}{"":2}'\
                 f' -n {row['-n']:20} -lat {round(row['-lat'], 4):8.4f} -lon {round(row['-lon'], 4):9.4f} --sunZenith {round((row['--sunZenith']),2):8.4f} {"           "}'\
                 f' -e {row['-e']:6.2f} -r {row['-r']:20.17f}  -l {row['-l']:20.17f}  -j {row['-j']:20.17f}  -k {row['-k']:20.17f}'\
                 f' {"":24} {"--capture":9} {"":9}'\
                 f' % {observationMiddleTime} - Predicted Cloud cover: {row['Predicted Cloud cover:']:5.1f} % Estimated downlink complete: \n'

    return cmd_string

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
            GT = gt,
            start = captureStart,
            end = captureEnd
        )
        return observationTask,
    elif '--buffer' in cmdDict:
        # Buffer command, we can ignore for now
        return None,
    else:
        raise Exception("Unknown command type in command line")

def recreateScheduleFromCmdLineFile(cmdLinesFilePath: str, targetFilePath: str, captureDurationSec: int = 60 ) -> list:
    """ Takes in a file path to a file containing command lines, and returns a list of OT objects representing the same schedule
    Output:
    - observationTasks: list of OT objects created from the command lines
    """
    observationTasks = []
    with open(cmdLinesFilePath, 'r') as f:
        cmdLines = f.readlines()
    
    for cmdLine in cmdLines:
        observationTask, = getObservationTaskFromCmdLine(targetFilePath, cmdLine, captureDurationSec)
        if observationTask is not None:
            observationTasks.append(observationTask)

    return observationTasks