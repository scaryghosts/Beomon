#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon zombie catcher, catch vagrant processes on compute nodes
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.2.2
# Last change:
# * Adding missing traceback module



# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys, os, re, subprocess, syslog, signal, ConfigParser, pymongo, traceback
import xml.etree.ElementTree as ET
from optparse import OptionParser



red = "\033[31m"
endcolor = '\033[0m'



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon zombie catcher.  This program will attempt to find processes \n" + 
    "on compute nodes which are not from a running job (zombies).\n" + 
    "Note 'zombie' in this sense is not a Unix-style zombie process but\n" +
    "a running process left over from a previous job.\n"
)

(options, args) = parser.parse_args()





# Preint a stack trace, exception, and an error string to STDERR
# then exit with the exit status given (default: 1) or don't exit
# if passed NoneType
def fatal_error(error_string, exit_status=1):
    red = "\033[31m"
    endcolor = "\033[0m"

    exc_type, exc_value, exc_traceback = sys.exc_info()

    traceback.print_exception(exc_type, exc_value, exc_traceback)

    sys.stderr.write("\n" + red + str(error_string) + endcolor + "\n")
    
    if exit_status is not None:
        sys.exit(int(exit_status))





# Prepare for subprocess timeouts
class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)





# Read the config file
config = ConfigParser.ConfigParser()
config.read("/opt/sam/beomon/etc/beomon.conf")

main_config = dict(config.items("main"))





# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip()
dbpasshandle.close()

    
    
# Open a DB connection
try:
    mongo_client = pymongo.MongoClient(main_config["mongo_host"])

    db = mongo_client.beomon
    
    db.authenticate("beomon", dbpass)
    
    del(dbpass)
    
except:
    fatal_error("Failed to connect to the Beomon database")
    
    
    
    
    
hostname = os.uname()[1]





#
# Get the current queue status
#
job_data = {}
signal.alarm(60)

try:
    qstat_info = subprocess.Popen([main_config["qstat"], "-x"], stdin=None, stdout=subprocess.PIPE)
    qstat_out = qstat_info.communicate()[0]
    
    signal.alarm(0)

except Alarm:
    sys.stdout.write("Zombie process check failed: Timeout on qstat\n")
    
    syslog.syslog(syslog.LOG_INFO, "Zombie process check timed out on qstat")
        
except:
    syslog.syslog(syslog.LOG_INFO, "Failed to check for zombie processes on qstat: " + str(err))
    
    fatal_error("Failed to check for zombie processes on qstat")


root = ET.fromstring(qstat_out)
    
    
# Loop through each job ...
for job in root.getiterator("Job"):
    job_state = job.find("./job_state").text

    # Skip non-running jobs
    if job_state != "R":
        continue
    
    job_id = job.find("./Job_Id").text
    
    try:
        user = job.find("./euser").text
        
    except AttributeError:
        user = job.find("./Job_Owner").text
        
        user = re.sub("@.*$", "", user)
        
    exec_host = job.find("./exec_host").text
    
    nodes = re.findall("n(\d+)/", exec_host)
        
    for node in set(nodes):
        # Add the node to the dict if needed
        try:
            if job_data[node]:
                pass
            
        except KeyError:
            job_data[node] = []
        
        # Add the user to the node if they aren't already
        if user not in job_data[node]:
            job_data[node].append(user)
        


#
# Get a list of all running processes
#
signal.alarm(60)

try:
    ps_info = subprocess.Popen(["ps", "-e", "-o", "pid,euser,comm"], stdin=None, stdout=subprocess.PIPE)
        
    bpstat_info = subprocess.Popen(["bpstat", "-P"], stdin=ps_info.stdout, stdout=subprocess.PIPE)
    ps_info.stdout.close()
    bpstat_out = bpstat_info.communicate()[0]
        
    signal.alarm(0)
        
except Alarm:
    sys.stdout.write("Zombie process check failed: Timeout\n")
    
    syslog.syslog(syslog.LOG_INFO, "Zombie process check timed out")
        
except:
    syslog.syslog(syslog.LOG_INFO, "Failed to check for zombie processes: " + str(err))
    
    fatal_error("Failed to check for zombie processes (bpstat or ps failed)")
    
    
    
#
# Find the zombies
#
zombie_dicts = []

for line in bpstat_out.split(os.linesep):
    line = line.rstrip()
    
    # Skip the header
    if re.search("^NODE", line):
        continue
    
    out_data = line.split()
    
    # If there are not 4 fields, it's a master node process
    if len(out_data) != 4:
        continue
    
    node_num = out_data[0]
    pid = out_data[1]
    user = out_data[2]
    command = out_data[3]
    
    # Catch actual Unix-style zombie processes
    if command == "<defunct>":
        continue

    
    # Skip non-regular users
    if user == "root" or user == "nscd" or user == "rpc" or user == "rpcuser" or user == "defusco" or user == "jaw171" or user == "jar7" or user == "kimwong" or user == "akila" or user == "15234":
        continue
        

    # Should the user's process be here?
    try:
        if user not in job_data[node_num]:
            sys.stdout.write("Zombie " + pid + " (" + command + ") of user " + user + " found from node " + node_num + "\n")
            
            syslog.syslog(syslog.LOG_INFO, "Zombie " + pid + " (" + command + ") of user " + user + " found from node " + node_num)
            
            zombie_dicts.append(
                {
                    "command" : command,
                    "user" : user,
                    "PID" : pid,
                    "node" : node_num,
                }
            )
            
    except KeyError: # We need this in case the node has no jobs on it so is not in the dict
        sys.stdout.write("Zombie " + pid + " (" + command + ") of user " + user + " found from node " + node_num + "\n")
        
        syslog.syslog(syslog.LOG_INFO, "Zombie " + pid + " (" + command + ") of user " + user + " found from node " + node_num)
        
        zombie_dicts.append(
                {
                    "command" : command,
                    "user" : user,
                    "PID" : pid,
                    "node" : node_num,
                }
            )

        
        
        
        
# Add the info to the DB
db.head_clusman.update(
    {
        "_id" : hostname.split(".")[0]
    },
    {
        "$set" : {
            "zombies" : zombie_dicts
        }
    },
    upsert = True,
)
        
        
        
        
        
sys.stdout.write("Done!\n")
