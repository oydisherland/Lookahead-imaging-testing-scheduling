import json
import os
from dataclasses import dataclass
from collections import namedtuple

#Ground target
GT = namedtuple("GT", ["id", "lat", "long", "elevation", "priority", "cloudCoverage" ,"exposureTime", "captureMode"])

@dataclass
class TargetData:
    name: str
    lat: float
    lon: float
    elev: float
    cc: float
    exp: float
    mode: str
    night: int
    t0: str
    t1: str


def parseTargetJson(json_obj):
    """
    Parse a JSON object into a TargetData object
    Only include keys that are defined in the TargetData dataclass
    """
    valid_keys = {field.name for field in TargetData.__dataclass_fields__.values()}
    filtered = {k: v for k, v in json_obj.items() if k in valid_keys}
    return TargetData(**filtered)



def getTargetDataFromJsonFile(targetsJsonFile: str):
    """ 
    Get the target data from a JSON file
    Input: path to the JSON file
    Output: List of TargetData objects 
    """

    with open(targetsJsonFile, 'r') as f:
        targets_json = json.load(f)
    targets = [parseTargetJson(target) for target in targets_json]
    return targets

def getGroundTargetObjectsFromJsonFile(targetsJsonFile: str) -> list:
    allGTs = []
    
    with open(targetsJsonFile, 'r') as f:
        targets_text = f.read().strip()

    if not targets_text:
        return allGTs

    targets_json = json.loads(targets_text)
    
    for index, jsonObj in enumerate(targets_json):
        target = parseTargetJson(jsonObj)
        targetId = target.name.strip()  # Remove any whitespace
        targetPriority = len(targets_json) - index
        
        gt = GT(
            id=targetId,
            lat=target.lat,
            long=target.lon,
            elevation=target.elev,
            priority=targetPriority,
            cloudCoverage=target.cc,
            exposureTime=target.exp,
            captureMode=target.mode
        )
        allGTs.append(gt)

    return allGTs

def getTargetIdPriorityDictFromJson(targetsJsonFile: str) -> dict:
    """ 
    Get a dictionary mapping target IDs to their priorities from a JSON file
    Input: path to the JSON file
    Output: Dictionary with target ID as key and priority as value
    """
    if not os.path.exists(targetsJsonFile):
        raise FileNotFoundError(f"File not found: {targetsJsonFile}")
    
    with open(targetsJsonFile, 'r') as f:
        targets = json.load(f)
    
    priorityIdDict = {}
    for index, target in enumerate(targets):
        targetId = target['name'].strip()  # Remove any whitespace
        targetPriority = len(targets) - index
        
        priorityIdDict[targetId] = targetPriority
    return priorityIdDict

