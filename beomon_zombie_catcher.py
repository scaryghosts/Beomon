#!/usr/bin/env python
# Description: Beomon zombie catcher, catch vagrant processes on compute nodes
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.1
# Last change: Changed binary paths to variables

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys, os, re, subprocess, syslog, signal
import xml.etree.ElementTree as ET
from optparse import OptionParser



qstat = "/opt/sam/torque/3.0.5/bin/qstat"
bpstat = "/usr/bin/bpstat"
ps = "/bin/ps"



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon zombie catcher.  This program will attempt to find processes \n" + 
    "on compute nodes which are not from a running job (zombies).\n" + 
    "Note 'zombie' in this sense is not a Unix-style zombie process but\n" +
    "a running process left over from a previous job.\n"
)

(options, args) = parser.parse_args()





# Prepare for subprocess timeouts
class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)




#
# Get the current queue status
#
job_data = {}
signal.alarm(60)

try:
    qstat_info = subprocess.Popen([qstat, "-x"], stdin=None, stdout=subprocess.PIPE)
    qstat_out = qstat_info.communicate()[0]
    
    signal.alarm(0)

except Alarm:
    sys.stdout.write("Zombie process check failed: Timeout on qstat\n")
    
    syslog.syslog(syslog.LOG_INFO, "Zombie process check timed out on qstat")
        
except Exception as err:
    sys.stderr.write("Failed to check for zombie processes on qstat: " + str(err) + "\n")
    
    syslog.syslog(syslog.LOG_INFO, "Failed to check for zombie processes on qstat: " + str(err))
    
    sys.exit(1)


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
    ps_info = subprocess.Popen([ps, "-e", "-o", "pid,euser,comm"], stdin=None, stdout=subprocess.PIPE)
        
    bpstat_info = subprocess.Popen([bpstat, "-P"], stdin=ps_info.stdout, stdout=subprocess.PIPE)
    ps_info.stdout.close()
    bpstat_out = bpstat_info.communicate()[0]
        
    signal.alarm(0)
        
except Alarm:
    sys.stdout.write("Zombie process check failed: Timeout\n")
    
    syslog.syslog(syslog.LOG_INFO, "Zombie process check timed out")
        
except Exception as err:
    sys.stderr.write("Failed to check for zombie processes: " + str(err) + "\n")
    
    syslog.syslog(syslog.LOG_INFO, "Failed to check for zombie processes: " + str(err))
    
    sys.exit(1)
    
    
    
#
# Find the zombies
#
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
            sys.stdout.write("Zombie " + pid + " (" + command + ") of user " + user + " found on node " + node_num + "\n")
            
            syslog.syslog(syslog.LOG_INFO, "Zombie " + pid + " (" + command + ") of user " + user + " found on node " + node_num)
        
    except KeyError: # We need this in case the node has no jobs on it so is not in the dict
        sys.stdout.write("Zombie " + pid + " (" + command + ") of user " + user + " found on node " + node_num + "\n")
        
        syslog.syslog(syslog.LOG_INFO, "Zombie " + pid + " (" + command + ") of user " + user + " found on node " + node_num)
        
        
sys.stdout.write("Done!\n")
