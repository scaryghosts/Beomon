#!/usr/bin/env python
# Description: Beomon master agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.3
# Last change: Switched compute node SQL table name to 'compute', added process checks 
# to check the master's health

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, MySQLdb, subprocess, time, syslog, paramiko, signal
from optparse import OptionParser



mysql_host = "clusman.frank.sam.pitt.edu"
clusman_host = "clusman.frank.sam.pitt.edu"
pbsnodes = "/usr/bin/pbsnodes"
bpstat = "/usr/bin/bpstat"



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
parser = OptionParser("%prog [options] $nodes\n" + 
    "Beomon master agent.  This program will check the status of \n" + 
    "the compute nodes given as an arg and update the Beomon database.\n" + 
    "The $nodes parameter accepts bpstat's node syntax (e.g. 0-6,8-9)."
)

(options, args) = parser.parse_args()


try:
    nodes = sys.argv[1]
    
except IndexError:
    sys.stderr.write("No nodes given, see --help\n")
    sys.exit(1)

    
    
hostname = os.uname()[1]


    
# Query MySQL for a given column of a given node
def compute_query(column, node):
        cursor.execute("SELECT " + column + " FROM compute WHERE node_id=" + node)
        
        results = cursor.fetchone()
        
        return results[0]



# Prepare for subprocess timeouts
class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)

        
    
# Prepare syslog
syslog.openlog(os.path.basename(sys.argv[0]), syslog.LOG_NOWAIT, syslog.LOG_DAEMON)

    
    
# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip()
dbpasshandle.close()

    
    
# Open a DB connection
try:
    db = MySQLdb.connect(
        host=mysql_host, user="beomon",
        passwd=dbpass, db="beomon"
    )
                                             
    cursor = db.cursor()
    
except MySQLError as err:
    sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
    sys.exit(1)

    
    
    
    
#
# Check our own health
#

# Add a row for ourself if one does not exist.
if cursor.execute("SELECT node_id FROM cluster_health WHERE node_id='" + hostname.split(".")[0] + "'") == 0:
    cursor.execute("INSERT INTO cluster_health (node_id) VALUES ('" + hostname.split(".")[0] + "')")

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
        sys.stdout.write("Process " + proc_name + " found\n")
        
        cursor.execute("UPDATE cluster_health SET " + proc_name + "=1 WHERE node_id='" + hostname.split(".")[0] + "'")
        
    else:
        sys.stdout.write("Process " + proc_name + " not found!\n")
        
        cursor.execute("UPDATE cluster_health SET " + proc_name + "=0 WHERE node_id='" + hostname.split(".")[0] + "'")
        
        
# Report that we've now checked ourself
cursor.execute("UPDATE cluster_health SET last_check=" + str(int(time.time())) + " WHERE node_id='" + hostname.split(".")[0] + "'")
        
del processes




    
# Determine our partner
if hostname == "head0a.frank.sam.pitt.edu":
    partner = "head0b.frank.sam.pitt.edu"

elif hostname == "head0b.frank.sam.pitt.edu":
    partner = "head0a.frank.sam.pitt.edu"
    
elif hostname == "head1a.frank.sam.pitt.edu":
    partner = "head1b.frank.sam.pitt.edu"
    
elif hostname == "head1b.frank.sam.pitt.edu":
    partner = "head1a.frank.sam.pitt.edu"
    
elif hostname == "head2a.frank.sam.pitt.edu":
    partner = "head2b.frank.sam.pitt.edu"
    
elif hostname == "head2b.frank.sam.pitt.edu":
    partner = "head2a.frank.sam.pitt.edu"
    
elif hostname == "head3a.frank.sam.pitt.edu":
    partner = "head3b.frank.sam.pitt.edu"
    
elif hostname == "head3b.frank.sam.pitt.edu":
    partner = "head3a.frank.sam.pitt.edu"
    
    
    
    

#
# Get the output of beostat and check each node
#
try:
    bpstat = subprocess.Popen([bpstat, "-l", nodes], stdout=subprocess.PIPE, shell=False)
    
    status = bpstat.wait()
    
    if status != 0:
        raise Exception("Non-zero exit status: " + str(status) + "\n")
    
    bpstat_out = bpstat.communicate()[0]
    
except Exception as err:
    sys.stderr.write("Call to bpstat failed: " + str(err))
    sys.exit(1)
    
    

# Loop through bpstat's output for each node
for line in bpstat_out.split(os.linesep):
    # Skip the header
    match_header = re.match("^Node", line)
    match_end = re.match("^$", line)
    if match_header is not None or match_end is not None:
        continue

        
    # Get the node number and state
    (node, status) = line.split()[0:3:2]

    
    # Add a row for the node if one does not exist.
    if cursor.execute("SELECT node_id FROM compute WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO compute (node_id) VALUES (" + node + ")")

        
    sys.stdout.write("Node: " + node + "\n")
    
    state = ""
    
    
    if status == "up":
        state = "up"
        
        num_state["up"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = compute_query("state", node)
        
        if last_state == "up":
            sys.stdout.write("State: up - known\n")
            
        else:    
            sys.stdout.write("State: up - new\n")
            
            try:
                ssh = paramiko.SSHClient()
                
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                ssh.connect(clusman_host)
                channel = ssh.get_transport().open_session()
                
                stdin = channel.makefile("wb", 1024)
                stdout = channel.makefile("rb", 1024)
                stderr = channel.makefile_stderr("rb", 1024)
                
                channel.exec_command(pbsnodes + " -c n" + node + "; exit $?")
                
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
                sys.stderr.write("Failed to online node with `pbsnodes` on " + clusman_host + ": " + str(err) + "\n")
            
            cursor.execute("UPDATE compute SET state='up', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        
    elif status == "down": # Really could be orphan or partnered instead of down
        
        # Get the last state and times
        last_state = compute_query("state", node)
        last_check = compute_query("last_check", node)
        state_time = compute_query("state_time", node)
        
        if last_check is None: last_check = 0

        
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
            
            channel.exec_command(bpstat + node + "; exit $?")
            
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
            sys.stderr.write("Failed to find partner's status: " + str(err) + "\n")
        
            found_partner_status = False
        

        if found_partner_status == True:
            state = "partnered"
            
            num_state["partnered"] += 1

            sys.stdout.write("State: partnered\n")
            
        
        # If the node checked in within the last 10 minutes, consider it an orphan
        elif last_check > (int(time.time()) - 600):
            state = "orphan"
            
            num_state["orphan"] += 1
            
            if last_state == "orphan":
                sys.stdout.write("State: orphan - known\n")
                
                # If the node has been an orphan more than 7 days, throw an alert
                if (int(time.time()) - int(state_time)) >= 604800:
                    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: orphan (beyond 7 day limit)")
                
                
            else:
                sys.stdout.write("State: orphan - new\n")
                
                try:
                    ssh = paramiko.SSHClient()
                    
                    ssh.load_system_host_keys()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                    ssh.connect(clusman_host)
                    channel = ssh.get_transport().open_session()
                    
                    stdin = channel.makefile("wb", 1024)
                    stdout = channel.makefile("rb", 1024)
                    stderr = channel.makefile_stderr("rb", 1024)
                    
                    channel.exec_command(pbsnodes + " -o n" + node + "; exit $?")
                    
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
                    sys.stderr.write("Failed to offline node with `pbsnodes` on " + clusman_host + ": " + str(err) + "\n")
                
                cursor.execute("UPDATE compute SET state='orphan', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        
        # The node has not checked in within the last 10 minutes, it's down
        else:
            state = "down"
            
            num_state["down"] += 1
            
            if last_state == "down":
                sys.stdout.write("State: down - known\n")
                
                ## TODO: Add IPMI's 'chassis power cycle'
                
                ## If the node has been down for more than 30 minutes, throw an alert
                if (int(time.time()) - int(state_time)) >= 1800:
                   syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: down")
                   
                
            else:
                sys.stdout.write("State: down - new\n")
                
                syslog.syslog(syslog.LOG_WARNING, "Node " + node + " is not up, state: down")
                
                cursor.execute("UPDATE compute SET state='down', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
                
            
    elif status == "boot":
        state = "boot"
        
        num_state["boot"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = compute_query("state", node)
        
        if last_state == "boot":
            sys.stdout.write("State: boot - known\n")
            
        else:
            sys.stdout.write("State: boot - new\n")
            
            cursor.execute("UPDATE compute SET state='boot', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
            
        # If the node has been in boot state for more than 120 minutes, log an alert
        time_diff = int(time.time()) - int(compute_query("state_time", node))
        
        if time_diff >= 7200:
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: boot")
        
        
    elif status == "error":
        state = "error"
        
        num_state["error"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = compute_query("state", node)
        
        if last_state == "error":
            sys.stdout.write("State: error - known\n")
            
        else:
            sys.stdout.write("State: error - new\n")
            
            cursor.execute("UPDATE compute SET state='error', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
            
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: error")

        
    
    #
    # Check the PBS state
    #
    if state == "up":
        try:
            ssh = paramiko.SSHClient()
            
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(clusman_host)
            channel = ssh.get_transport().open_session()
            
            stdin = channel.makefile("wb", 1024)
            stdout = channel.makefile("rb", 1024)
            stderr = channel.makefile_stderr("rb", 1024)
            
            channel.exec_command(pbsnodes + " -q n" + node + "; exit $?")
            
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
                
                pbs_state = line.split()[2]
                
                if pbs_state == "offline":
                    sys.stdout.write("PBS: Offline\n")
                    
                    num_state["pbs_offline"] += 1
                    
                    cursor.execute("UPDATE compute SET pbs_state='offline' WHERE node_id=" + node)
                    
                elif pbs_state == "down":
                    sys.stdout.write("PBS: Down\n")
                    
                    cursor.execute("UPDATE compute SET pbs_state='down' WHERE node_id=" + node)
                    
                else:
                    sys.stdout.write("PBS: OK\n")
                    
                    cursor.execute("UPDATE compute SET pbs_state='ok' WHERE node_id=" + node)
                    
            stdout.close()
            
            # Done!
            channel.close()
            ssh.close()
            
        except Exception, err:
            sys.stderr.write("Failed to check PBS state node with `pbsnodes` on " + clusman_host + ": " + str(err) + "\n")

            syslog.syslog(syslog.LOG_WARNING, "Failed to check PBS state node with `pbsnodes` on " + clusman_host + " for node: " + node)
            
            cursor.execute("UPDATE compute SET pbs_state=NULL WHERE node_id=" + node)
    
    
    
    #
    # Verify that the node is still checking in if it is up
    #    
    if state == "up":
        last_check = compute_query("last_check", node)
        
        if last_check is None:
            sys.stderr.write("Node " + str(node) + " last check in time is NULL\n")
        
        else:
            checkin_seconds_diff = int(time.time()) - int(last_check)
        
            if checkin_seconds_diff >= 3600: # 1 hour
                sys.stderr.write("Node " + str(node) + " last check in time is stale (last checked in " + str(checkin_seconds_diff) + " seconds ago)\n")
            
                syslog.syslog(syslog.LOG_WARNING, "Node " + str(node) + " last check in time is stale (last checked in " + str(checkin_seconds_diff) + " seconds ago)")
    
    
    
    sys.stdout.write("\n")
    
    

# Check if we have too many nodes not up

if num_state["down"] >= 10:
    sys.stdout.write("WARNING: " + str(num_state["down"]) + " nodes in state 'down'!\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'down'")
    
elif num_state["down"] > 0:
    sys.stdout.write(str(num_state["down"]) + " nodes in state 'down'\n")
    

if num_state["orphan"] >= 10:
    sys.stdout.write("WARNING: " + str(num_state["orphan"]) + " nodes in state 'orphan'!\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'orphan'")
    
elif num_state["orphan"] > 0:
    sys.stdout.write(str(num_state["orphan"]) + " nodes in state 'orphan'\n")
    
    
if num_state["error"] >= 10:
    sys.stdout.write("WARNING: " + str(num_state["error"]) + " nodes in state 'error'!\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes in state 'error'")
    
elif num_state["error"] > 0:
    sys.stdout.write(str(num_state["error"]) + " nodes in state 'error'\n")
    
    
if num_state["pbs_offline"] >= 10:
    sys.stdout.write("WARNING: " + str(num_state["pbs_offline"]) + " nodes PBS state 'offline'!\n")
    
    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: 10 or more nodes with PBS state 'offline'")
    
elif num_state["pbs_offline"] > 0:
    sys.stdout.write(str(num_state["pbs_offline"]) + " nodes with PBS state 'offline'\n")
    

sys.stdout.write(str(num_state["partnered"]) + " nodes in state 'partnered'\n")
    
sys.stdout.write(str(num_state["up"]) + " nodes in state 'up'\n")



# Close the DB, we're done with it
syslog.closelog()
db.close()
