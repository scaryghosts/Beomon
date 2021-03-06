#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon master agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)



# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
import os
import re
import pymongo
import subprocess
import time
import syslog
import paramiko
import signal
import hashlib
import ConfigParser
import datetime
import traceback
from optparse import OptionParser



red = "\033[31m"
endcolor = '\033[0m' # end color
nodes = ""
num_state = {
    "down" : 0,
    "boot" : 0,
    "error" : 0,
    "orphan" : 0,
    "up" : 0,
    "partnered" : 0,
    "pbs_offline" : 0
}



# How were we called?
parser = OptionParser("%prog [options] [nodes ...]\n" + 
    "Beomon master agent.  This program will check the status of \n" + 
    "the compute nodes given as an arg and update the Beomon database.\n" + 
    "The [nodes ...] parameter accepts bpstat's node syntax (e.g. 0-6,8-9)."
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
        
        



try:
    nodes = sys.argv[1]
    
except IndexError:
    sys.stderr.write("No nodes given, see --help\n")
    sys.exit(1)

    
    
hostname = os.uname()[1]



# Log our activities
log_file_handle = open("/opt/sam/beomon/log/" + hostname.split(".")[0] + ".log", "a+")

def log_self(message):
    log_file_handle.write(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S") + " : " + message + "\n")
    log_file_handle.flush()
    
    
    
log_self("- - - Run starting - - -")



# Prepare for subprocess timeouts
class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)

        
    
# Prepare syslog
syslog.openlog(os.path.basename(sys.argv[0]), syslog.LOG_NOWAIT, syslog.LOG_DAEMON)



# Read the config file
config = ConfigParser.ConfigParser()
config.read("/opt/sam/beomon/etc/beomon.conf")

main_config = dict(config.items("main"))
hash_files = dict(config.items("hash_files"))

    
    
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

    
    
    
    
#
# Check our own health
#

new_master_data = {}

# Get the current load average
load_avg_data = open("/proc/loadavg", "r").read()
new_master_data["loadavg"] = {}
new_master_data["loadavg"]["1"] = load_avg_data.split()[0]
new_master_data["loadavg"]["5"] = load_avg_data.split()[1]
new_master_data["loadavg"]["15"] = load_avg_data.split()[2]

print "Load average 1 minute: " + new_master_data["loadavg"]["1"]
print "Load average 5 minutes: " + new_master_data["loadavg"]["5"]
print "Load average 15 minutes: " + new_master_data["loadavg"]["15"]


# Get the list of current processes
processes = []
for pid in [pid for pid in os.listdir('/proc') if pid.isdigit()]:
    try:
        with open("/proc/" + pid + "/cmdline", "r") as procfile:
            process = procfile.read()
            
            if process == "":
                continue

            # Remove the unprintable character at the end of the string
            process = list(process)
            process.pop()
            process = "".join(process)
            
            processes.append(process)
            
    except IOError: # The process could have gone away, that's fine
        pass


# Are the processes we want alive?
for proc_name in ["beoserv", "bpmaster", "recvstats", "kickbackdaemon"]:
    if "/usr/sbin/" + proc_name in processes:
        new_master_data["processes." + proc_name] = True
        
    else:
        sys.stdout.write(red + "Process " + proc_name + " not found!\n" + endcolor)
        
        new_master_data["processes." + proc_name] = False
        

del processes




    
# Determine our partner and note what nodes we are responible for
if hostname == "head0a-dev.francis.sam.pitt.edu":
    partner = "head0b-dev.francis.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Foo"
    new_master_data["primary_of"] = range(0,3 + 1)
    new_master_data["secondary_of"] = range(4, 7 + 1)
    
elif hostname == "head0b-dev.francis.sam.pitt.edu":
    partner = "head0a-dev.francis.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Bar"
    new_master_data["primary_of"] = range(4, 7 + 1)
    new_master_data["secondary_of"] = range(0, 3 + 1)
    
elif hostname == "head0a.frank.sam.pitt.edu":
    partner = "head0b.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Original Frank and Fermi Penguin"
    new_master_data["primary_of"] = range(0, 112 + 1)
    new_master_data["primary_of"] += range(153, 158 + 1)
    new_master_data["secondary_of"] = range(113, 152 + 1)
    new_master_data["secondary_of"] += range(159, 176 + 1)
    
elif hostname == "head0b.frank.sam.pitt.edu":
    partner = "head0a.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Original Frank and Fermi Penguin"
    new_master_data["primary_of"] = range(113, 152 + 1)
    new_master_data["primary_of"] += range(159, 176 + 1)
    new_master_data["secondary_of"] = range(0, 112 + 1)
    new_master_data["secondary_of"] += range(153, 158 + 1)
    
elif hostname == "head1a.frank.sam.pitt.edu":
    partner = "head1b.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "IBM"
    new_master_data["primary_of"] = range(177, 223 + 1)
    new_master_data["secondary_of"] = range(224, 241 + 1)
    
elif hostname == "head1b.frank.sam.pitt.edu":
    partner = "head1a.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "IBM"
    new_master_data["primary_of"] = range(224, 241 + 1)
    new_master_data["secondary_of"] = range(177, 223 + 1)
    
elif hostname == "head2a.frank.sam.pitt.edu":
    partner = "head2b.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Intel Sandybridge"
    new_master_data["primary_of"] = range(242, 278 + 1)
    new_master_data["secondary_of"] = range(279, 324 + 1)
    
elif hostname == "head2b.frank.sam.pitt.edu":
    partner = "head2a.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "Intel Sandybridge"
    new_master_data["primary_of"] = range(279, 324 + 1)
    new_master_data["secondary_of"] = range(242, 278 + 1)
    
elif hostname == "head3a.frank.sam.pitt.edu":
    partner = "head3b.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "AMD Interlagos"
    new_master_data["primary_of"] = range(325, 350 + 1)
    new_master_data["secondary_of"] = range(351, 378 + 1)
    
elif hostname == "head3b.frank.sam.pitt.edu":
    partner = "head3a.frank.sam.pitt.edu"
    
    new_master_data["compute_node_class"] = "AMD Interlagos"
    new_master_data["primary_of"] = range(351, 378 + 1)
    new_master_data["secondary_of"] = range(325, 350 + 1)
    
    
    
    
    
#
# Check for files which are not the same as those on head0a
#

# Get head0a's config file hashes
head0a_doc = db.head.find_one(
    {
        "_id" : "head0a"
    },
    {
        "file_hashes" : 1,
        "_id" : 0,
    }
)

if head0a_doc is None:
    head0a_file_hashes = None
    
else:
    head0a_file_hashes = head0a_doc.get("file_hashes")


local_file_hashes = {}

# Loop through each file we need to hash
found_mismatched_file = False
for _, each_file in hash_files.items():
    try:
        each_file_handle = open(each_file, "rb")
        
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, None)
        
        sys.stderr.write(red + "Unable to open " + each_file + " for hashing\n" + endcolor)
        
        continue
    
    
    # MongoDB does not support dots in keys...
    each_file_nodot = re.sub(r"\.", "[DOT]", each_file)
        
        
    hash_obj = hashlib.sha512()
    
    
    while True:
        bytes = each_file_handle.read(4096)
        
        # Did we reach the end of the file?
        if not bytes:
            break
            
        hash_obj.update(bytes)
        
        
    local_digest = hash_obj.hexdigest()
    
    local_file_hashes[each_file_nodot] = local_digest
    
    
    # Does the local digest match head0a's?
    if head0a_file_hashes is not None and not hostname == "head0a.frank.sam.pitt.edu":
        try:
            if not head0a_file_hashes[each_file_nodot] == local_digest:
                sys.stderr.write(red + "Warning: File '" + each_file + "' does not match head0a\n" + endcolor)
                syslog.syslog(syslog.LOG_INFO, "File '" + each_file + "' does not match head0a")
                
                found_mismatched_file = True
            
        except KeyError:
            sys.stdout.write("No hash of file '" + each_file + "' found for head0a, cannot compare against local\n")
        
    
    each_file_handle.close()
    
    
new_master_data["file_hashes"] = local_file_hashes


if found_mismatched_file is True:
    new_master_data["configs_ok"] = False
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: One or more configuration files do not match head0a")
    
else:
    new_master_data["configs_ok"] = True


    


#
# Get the output of beostat and check each node
#
try:
    bpstat_proc = subprocess.Popen([main_config["bpstat"], "-l", nodes], stdout=subprocess.PIPE, shell=False)
    
    status = bpstat_proc.wait()
    
    if status != 0:
        raise Exception("Non-zero exit status: " + str(status) + "\n")
    
    bpstat_out = bpstat_proc.communicate()[0]
    
except:
    fatal_error("Call to bpstat failed")
    
    

# Loop through bpstat's output for each node
for line in bpstat_out.split(os.linesep):
    # Skip the header
    match_header = re.match("^Node", line)
    match_end = re.match("^$", line)
    if match_header is not None or match_end is not None:
        continue

        
    # Get the node number and state
    (node, status) = line.split()[0:3:2]
    node = int(node)
    
    
    # Get the node's details we care about
    node_db_info = db.compute.find_one(
        {
            "_id" : node
        },
        {
            "last_check" : 1,
            "state" : 1,
            "state_time" : 1,
            "_id" : 0,
        }
    )
    
    # Catch things that didn't exist in the document
    if node_db_info is None:
        node_db_info = {}
        
        node_db_info["last_check"] = None
        node_db_info["state"] = None
        node_db_info["state_time"] = None
        
    else:
        try:
            garbage = node_db_info["last_check"]
            
        except KeyError:
            node_db_info["last_check"] = None
            
        try:
            garbage = node_db_info["state"]
            
        except KeyError:
            node_db_info["state"] = None
            
        try:
            garbage = node_db_info["state_time"]
            
        except KeyError:
            node_db_info["state_time"] = None
            
    
    
    sys.stdout.write("Node: " + str(node) + "\n")
    
    
    
    state = ""
    new_compute_data = {}
    
    
    
    # Note the rack location
    if node in range(0, 4):
        new_compute_data["rack"] = "C-1-2"
        
    elif node in range(4, 14):
        new_compute_data["rack"] = "C-1-4"
        
    elif node in range(14, 53):
        new_compute_data["rack"] = "C-1-3"
        
    elif node in range(53, 59):
        new_compute_data["rack"] = "C-1-4"
        
    elif node in range(59, 113):
        new_compute_data["rack"] = "C-1-20"
        
    elif node in range(113, 173):
        new_compute_data["rack"] = "C-1-19"
        
    elif node in range(173, 177):
        new_compute_data["rack"] = "C-1-20"
        
    elif node in range(177, 211):
        new_compute_data["rack"] = "C-1-18"
        
    elif node in range(211, 242):
        new_compute_data["rack"] = "C-1-17"

    elif node == 242:
        new_compute_data["rack"] = "C-1-2"
        
    elif node in range(243, 284):
        new_compute_data["rack"] = "C-1-21"
        
    elif node in range(284, 325):
        new_compute_data["rack"] = "C-1-22"
        
    elif node in range(325, 351):
        new_compute_data["rack"] = "C-1-23"
        
    elif node in range(351, 379):
        new_compute_data["rack"] = "C-1-24"
        
    elif node in range(379, 386):
        new_compute_data["rack"] = "C-1-2"
        
    elif node in range(386, 409):
        new_compute_data["rack"] = "C-1-6"
        
    else:
        new_compute_data["rack"] = "unknown"
    
    
    
    if status == "up":
        state = "up"
        
        num_state["up"] += 1
        
        if node_db_info["state"] == "up":
            sys.stdout.write("State: up - known\n")
            log_self("Node " + str(node) + " is in state up")
            
        else:    
            sys.stdout.write("State: up - new\n")
            log_self("Node " + str(node) + " is in state up")
            
            # Add an entry to the journal for this node
            db.compute.update(
                { "_id" : node },
                { "$push" : { "journal" : { "time" : time.time(), "entry" : "Node state switched to 'up'.<br><br>-- Beomon Master Agent" } } }
            )
            
            try:
                ssh = paramiko.SSHClient()
                
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                ssh.connect(main_config["clusman_host"])
                channel = ssh.get_transport().open_session()
                
                stdin = channel.makefile("wb", 1024)
                stdout = channel.makefile("rb", 1024)
                stderr = channel.makefile_stderr("rb", 1024)
                
                channel.exec_command(main_config["pbsnodes"] + " -c n" + str(node) + "; exit $?")
                
                # Check for errors
                err = stderr.read()
                stderr.close()
                
                if err:
                    sys.stderr.write("Err: " + err)

                status = channel.recv_exit_status()
                    
                if status != 0:
                    raise Exception("Non-zero exit status: " + str(status))
                    
                stdin.close()
                stdout.close()
                
                # Done!
                channel.close()
                ssh.close()
                
            except Exception, err:
                sys.stderr.write(red + "Failed to online node with `pbsnodes` on " + main_config["clusman_host"] + ": " + str(err) + "\n" + endcolor)
                
            new_compute_data["state"] = "up"
            
            new_compute_data["state_time"] = int(time.time())
            
        
    elif status == "down": # Really could be orphan or partnered instead of down
        if node_db_info["last_check"] is None:
            node_db_info["last_check"] = 0

        
        # If our partner thinks the node is up, boot or error consider the node "partnered"
        
        # Connect to our partner and see what they think about this node
        found_partner_status = False
        
        try:
            ssh = paramiko.SSHClient()
            
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(partner)
            channel = ssh.get_transport().open_session()
            
            stdin = channel.makefile("wb", 1024)
            stdout = channel.makefile("rb", 1024)
            stderr = channel.makefile_stderr("rb", 1024)
            
            channel.exec_command(main_config["bpstat"] + " " + str(node) + "; exit $?")
            
            err = stderr.read()
            stderr.close()
            
            # Check the status
            if err:
                sys.stderr.write("Err: " + err)

            status = channel.recv_exit_status()
                
            if status != 0:
                raise Exception("Non-zero exit status: " + str(status))

            stdin.close()
            
            for line in stdout.read().split(os.linesep):
                line = line.rstrip()
                
                match = re.match("^\d", line)
                
                if not match:
                    continue
                
                partner_status = line.split()[1]
                
                if partner_status != "down":
                    found_partner_status = True
                    
                else:
                    found_partner_status = False
                    
            stdout.close()
            
            # Done!
            channel.close()
            ssh.close()
            
        except Exception, err:
            sys.stderr.write(red + "Failed to find partner's status: " + str(err) + endcolor + "\n")
        
            found_partner_status = False
        

        if found_partner_status == True:
            state = "partnered"
            
            num_state["partnered"] += 1

            sys.stdout.write("State: partnered\n")
            log_self("Node " + str(node) + " is in state partnered")
            
        
        # If the node checked in within the last 10 minutes, consider the node an orphan
        elif node_db_info["last_check"] > (int(time.time()) - (60 * 10)):
            state = "orphan"
            
            num_state["orphan"] += 1
            
            if node_db_info["state"] == "orphan":
                sys.stdout.write(red + "State: orphan - known\n" + endcolor)
                log_self("Node " + str(node) + " is in state orphan")
                
                # If the node has been an orphan more than 7 days, throw an alert
                if (int(time.time()) - node_db_info["state_time"]) >= 604800:
                    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " is not up, state: orphan (beyond 7 day limit)")
                
                
            else:
                sys.stdout.write(red + "State: orphan - new\n" + endcolor)
                log_self("Node " + str(node) + " is in state orphan")
                
                # Add an entry to the journal for this node
                db.compute.update(
                    { "_id" : node },
                    { "$push" : { "journal" : { "time" : time.time(), "entry" : "Node state switched to 'orphan'.<br><br>-- Beomon Master Agent" } } }
                )
                
                try:
                    ssh = paramiko.SSHClient()
                    
                    ssh.load_system_host_keys()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                    ssh.connect(main_config["clusman_host"])
                    channel = ssh.get_transport().open_session()
                    
                    stdin = channel.makefile("wb", 1024)
                    stdout = channel.makefile("rb", 1024)
                    stderr = channel.makefile_stderr("rb", 1024)
                    
                    channel.exec_command(main_config["pbsnodes"] + " -o n" + str(node) + "; exit $?")
                    
                    # Check for errors
                    err = stderr.read()
                    stderr.close()
                    
                    if err:
                        sys.stderr.write("Err: " + err)

                    status = channel.recv_exit_status()
                        
                    if status != 0:
                        raise Exception("Non-zero exit status: " + str(status))
                        
                    stdin.close()
                    stdout.close()
                    
                    # Done!
                    channel.close()
                    ssh.close()
                        
                except Exception, err:
                    sys.stderr.write(red + "Failed to offline node with `pbsnodes` on " + main_config["clusman_host"] + ": " + str(err) + endcolor + "\n")
                
                new_compute_data["state"] = "orphan"
                new_compute_data["state_time"] = int(time.time())
                
        
        # The node has not checked in within the last 10 minutes OR has been "down" as far
        # as the head node knows for less than 7 minutes, consider it down
        else:
            state = "down"
            
            num_state["down"] += 1
            
            if node_db_info["state"] == "down":
                sys.stdout.write(red + "State: down - known\n" + endcolor)
                log_self("Node " + str(node) + " is in state down")
                
                ## TODO: Add IPMI's 'chassis power cycle'
                
                ## If the node has been down for more than 30 minutes, throw an alert
                if (int(time.time()) - node_db_info["state_time"]) >= (60 * 30):
                    syslog.syslog(syslog.LOG_ERR, "Node " + str(node) + " is not up, state: down, rack: " + new_compute_data["rack"])
                   
                
            else:
                sys.stdout.write(red + "State: down - new\n" + endcolor)
                
                syslog.syslog(syslog.LOG_WARNING, "Node " + str(node) + " is not up, state: down")
                log_self("Node " + str(node) + " is in state down")
                
                # Add an entry to the journal for this node
                db.compute.update(
                    { "_id" : node },
                    { "$push" : { "journal" : { "time" : time.time(), "entry" : "Node state switched to 'down'.<br><br>-- Beomon Master Agent" } } }
                )
                
                new_compute_data["state"] = "down"
                new_compute_data["state_time"] = int(time.time())
                
            
    elif status == "boot":
        state = "boot"
        
        num_state["boot"] += 1
        
        if node_db_info["state"] == "boot":
            sys.stdout.write("State: boot - known\n")
            log_self("Node " + str(node) + " is in state boot")
            
            # If the node has been in boot state for more than 2 hours, log an alert
            if int(time.time()) - node_db_info["state_time"] >= (60 * 60 * 2):
                syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " is not up, state: boot")
            
        else:
            sys.stdout.write("State: boot - new\n")
            log_self("Node " + str(node) + " is in state boot")
            
            # Add an entry to the journal for this node
            db.compute.update(
                { "_id" : node },
                { "$push" : { "journal" : { "time" : time.time(), "entry" : "Node state switched to 'boot'.<br><br>-- Beomon Master Agent" } } }
            )
            
            new_compute_data["state"] = "boot"
            new_compute_data["state_time"] = int(time.time())
            
        
    elif status == "error":
        state = "error"
        
        num_state["error"] += 1
        
        if node_db_info["state"] == "error":
            sys.stdout.write(red + "State: error - known\n" + endcolor)
            log_self("Node " + str(node) + " is in state error")
            
        else:
            sys.stdout.write(red + "State: error - new\n" + endcolor)
            log_self("Node " + str(node) + " is in state error")
            
            # Add an entry to the journal for this node
            db.compute.update(
                { "_id" : node },
                { "$push" : { "journal" : { "time" : time.time(), "entry" : "Node state switched to 'error'.<br><br>-- Beomon Master Agent" } } }
            )
            
            new_compute_data["state"] = "error"
            new_compute_data["state_time"] = int(time.time())
            
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " is not up, state: error")

        
    
    #
    # Check the PBS state
    #
    if state == "up":
        try:
            ssh = paramiko.SSHClient()
            
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(main_config["clusman_host"])
            channel = ssh.get_transport().open_session()
            
            stdin = channel.makefile("wb", 1024)
            stdout = channel.makefile("rb", 1024)
            stderr = channel.makefile_stderr("rb", 1024)
            
            channel.exec_command(main_config["pbsnodes"] + " -q n" + str(node) + "; exit $?")
            
            # Check for errors
            err = stderr.read()
            stderr.close()
            
            if err:
                sys.stderr.write(err)

            status = channel.recv_exit_status()
                
            if status != 0:
                raise Exception("Non-zero exit status: " + str(status))
                
            stdin.close()
            
            for line in stdout.read().split(os.linesep):
                line = line.rstrip()
                
                match = re.match("^\s+state", line)
                
                if not match:
                    continue
                
                pbs = line.split()[2]
                
                if pbs == "offline":
                    sys.stdout.write(red + "PBS: Offline" + endcolor + "\n")
                    
                    num_state["pbs_offline"] += 1
                    
                    new_compute_data["pbs"] = False
                    
                elif pbs == "down":
                    sys.stdout.write(red + "PBS: Down" + endcolor + "\n")
                    
                    new_compute_data["pbs"] = False
                    
                else:
                    sys.stdout.write("PBS: OK\n")
                    
                    new_compute_data["pbs"] = True
                    
            stdout.close()
            
            # Done!
            channel.close()
            ssh.close()
            
        except Exception, err:
            sys.stderr.write("Failed to check PBS state node with `pbsnodes` on " + main_config["clusman_host"] + ": " + str(err) + "\n")

            syslog.syslog(syslog.LOG_WARNING, "Failed to check PBS state node with `pbsnodes` on " + main_config["clusman_host"] + " for node: " + str(node))
            
            new_compute_data["pbs"] = False
            
    
    
    #
    # Verify that the node is still checking in if it is up
    #    
    if state == "up":
        if node_db_info["last_check"] is None:
            sys.stderr.write(red + "Node " + str(node) + " last check in time is NULL" + endcolor + "\n")
        
        else:
            checkin_seconds_diff = int(time.time()) - node_db_info["last_check"]
        
            if checkin_seconds_diff >= 60 * 30:
                sys.stderr.write(red + "Node " + str(node) + " last check in time is stale (last checked in " + str(checkin_seconds_diff) + " seconds ago)" + endcolor + "\n")
            
                syslog.syslog(syslog.LOG_WARNING, "Node " + str(node) + " last check in time is stale (last checked in " + str(checkin_seconds_diff) + " seconds ago)")
    
    
    
    # Update the compute collection
    db.compute.update(
        {
            "_id" : node
        },
        {
            "$set" : new_compute_data
        },
        upsert = True,
    )
    
 
 
    sys.stdout.write("\n")
    
    

# Check if we have too many nodes not up

if num_state["down"] >= 10:
    sys.stdout.write(red + "WARNING: " + str(num_state["down"]) + " nodes in state 'down'!" + endcolor + "\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'down'")
    
elif num_state["down"] > 0:
    sys.stdout.write(str(num_state["down"]) + " nodes in state 'down'\n")
    

if num_state["orphan"] >= 10:
    sys.stdout.write(red + "WARNING: " + str(num_state["orphan"]) + " nodes in state 'orphan'!" + endcolor + "\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'orphan'")
    
elif num_state["orphan"] > 0:
    sys.stdout.write(str(num_state["orphan"]) + " nodes in state 'orphan'\n")
    
    
if num_state["error"] >= 10:
    sys.stdout.write(red + "WARNING: " + str(num_state["error"]) + " nodes in state 'error'!" + endcolor + "\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'error'")
    
elif num_state["error"] > 0:
    sys.stdout.write(str(num_state["error"]) + " nodes in state 'error'\n")
    
    
if num_state["pbs_offline"] >= 10:
    sys.stdout.write(red + "WARNING: " + str(num_state["pbs_offline"]) + " nodes PBS state 'offline'!" + endcolor + "\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes with PBS state 'offline'")
    
elif num_state["pbs_offline"] > 0:
    sys.stdout.write(str(num_state["pbs_offline"]) + " nodes with PBS state 'offline'\n")
    

sys.stdout.write(str(num_state["partnered"]) + " nodes in state 'partnered'\n")
    
sys.stdout.write(str(num_state["up"]) + " nodes in state 'up'\n")



# Add the number of nodes in each state to our doc
new_master_data["num_state"] = num_state



# Report that we've now checked ourself
new_master_data["last_check"] = int(time.time())
    
    
    
# Update the master collection
db.head.update(
    {
        "_id" : hostname.split(".")[0]
    },
    {
        "$set" : new_master_data
    },
    upsert = True,
)

del(new_master_data)



log_self("- - - Run completed - - -")



# Close the DB and logs, we're done with them
syslog.closelog()
log_file_handle.close()
mongo_client.close()
