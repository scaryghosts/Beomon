#!/usr/bin/env python
# Description: Beomon master agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.2.2
# Last change: Syslog is no longer closed early

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, MySQLdb, subprocess, time, syslog, paramiko
from optparse import OptionParser



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

    
    
# Query MySQL for a given column of a given node
def do_sql_query(column, node):
        cursor.execute("SELECT " + column + " FROM beomon WHERE node_id=" + node)
        
        results = cursor.fetchone()
        
        return results[0]

        
    
# Prepare syslog
syslog.openlog(os.path.basename(sys.argv[0]), syslog.LOG_NOWAIT, syslog.LOG_DAEMON)

    
    
# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip()
dbpasshandle.close()

    
    
# Open a DB connection
try:
    db = MySQLdb.connect(
        host="clusman0-dev.francis.sam.pitt.edu", user="beomon",
        passwd=dbpass, db="beomon"
    )
                                             
    cursor = db.cursor()
    
except MySQLError as err:
    sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
    sys.exit(1)

    
    
# Determine our partner
hostname = os.uname()[1]
    
if hostname == "head0a-dev.francis.sam.pitt.edu":
    partner = "head0b-dev.francis.sam.pitt.edu"

elif hostname == "head0b-dev.francis.sam.pitt.edu":
    partner = "head0a-dev.francis.sam.pitt.edu"
    
    
    
# Get the output of beostat
try:
    bpstat = subprocess.Popen(["/usr/bin/bpstat" ,"-l", nodes], stdout=subprocess.PIPE, shell=False)
    
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
    if cursor.execute("SELECT node_id FROM beomon WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO beomon (node_id) VALUES (" + node + ")")

        
    sys.stdout.write("Node: " + node + "\n")
    
    state = ""
    
    
    if status == "up":
        state = "up"
        
        num_state["up"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = do_sql_query("state", node)
        
        if last_state == "up":
            sys.stdout.write("State: up - known\n")
            
        else:    
            sys.stdout.write("State: up - new\n")
            
            try:
                ssh = paramiko.SSHClient()
                
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                ssh.connect("clusman0-dev.francis.sam.pitt.edu")
                channel = ssh.get_transport().open_session()
                
                stdin = channel.makefile("wb", 1024)
                stdout = channel.makefile("rb", 1024)
                stderr = channel.makefile_stderr("rb", 1024)
                
                channel.exec_command("/usr/bin/pbsnodes -c n" + node + "; exit $?")
                
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
                sys.stderr.write("Failed to online node with `pbsnodes` on clusman0-dev.francis.sam.pitt.edu: " + str(err) + "\n")
            
            cursor.execute("UPDATE beomon SET state='up', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        
    elif status == "down": # Really could be orphan or partnered instead of down
        
        # Get the last state and times
        last_state = do_sql_query("state", node)
        last_check = do_sql_query("last_check", node)
        state_time = do_sql_query("state_time", node)
        
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
            
            channel.exec_command("/usr/bin/bpstat " + node + "; exit $?")
            
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

                    ssh.connect("clusman0-dev.francis.sam.pitt.edu")
                    channel = ssh.get_transport().open_session()
                    
                    stdin = channel.makefile("wb", 1024)
                    stdout = channel.makefile("rb", 1024)
                    stderr = channel.makefile_stderr("rb", 1024)
                    
                    channel.exec_command("/usr/bin/pbsnodes -o n" + node + "; exit $?")
                    
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
                    sys.stderr.write("Failed to offline node with `pbsnodes` on clusman0-dev.francis.sam.pitt.edu: " + str(err) + "\n")
                
                cursor.execute("UPDATE beomon SET state='orphan', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        
        # The node has not checked in within the last 10 minutes, it's down
        else:
            state = "down"
            
            num_state["down"] += 1
            
            if last_state == "down":
                sys.stdout.write("State: down - known\n")
                
                ## TODO: Add IPMI's 'chassis power cycle'
                
                ## If the node has been down for more than 30 minutes, throw an alert
                #if (int(time.time()) - int(state_time)) >= 1800:
                    #syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: down")
                
                
            else:
                sys.stdout.write("State: down - new\n")
                
                cursor.execute("UPDATE beomon SET state='down', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
                
            
    elif status == "boot":
        state = "boot"
        
        num_state["boot"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = do_sql_query("state", node)
        
        if last_state == "boot":
            sys.stdout.write("State: boot - known\n")
            
        else:
            sys.stdout.write("State: boot - new\n")
            
            cursor.execute("UPDATE beomon SET state='boot', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
            
        # If the node has been in boot state for more than 120 minutes, log an alert
        time_diff = int(time.time()) - int(do_sql_query("state_time", node))
        
        if time_diff >= 7200:
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: boot")
        
        
    elif status == "error":
        state = "error"
        
        num_state["error"] += 1
        
        # Get the last state and see if it matches the current state
        last_state = do_sql_query("state", node)
        
        if last_state == "error":
            sys.stdout.write("State: error - known\n")
            
        else:
            sys.stdout.write("State: error - new\n")
            
            cursor.execute("UPDATE beomon SET state='error', state_time=" + str(int(time.time())) + " WHERE node_id=" + node)
            
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " is not up, state: error")

        
    
    #
    # Check the PBS state
    #
    if state == "up":
        try:
            ssh = paramiko.SSHClient()
            
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect("clusman0-dev.francis.sam.pitt.edu")
            channel = ssh.get_transport().open_session()
            
            stdin = channel.makefile("wb", 1024)
            stdout = channel.makefile("rb", 1024)
            stderr = channel.makefile_stderr("rb", 1024)
            
            channel.exec_command("/usr/bin/pbsnodes -q n" + node + "; exit $?")
            
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
                    sys.stderr.write("PBS: Offline\n")
                    
                    num_state["pbs_offline"] += 1
                    
                    cursor.execute("UPDATE beomon SET pbs_state='offline' WHERE node_id=" + node)
                    
                elif pbs_state == "down":
                    sys.stderr.write("PBS: Down\n")
                    
                    cursor.execute("UPDATE beomon SET pbs_state='down' WHERE node_id=" + node)
                    
                else:
                    sys.stderr.write("PBS: OK\n")
                    
                    cursor.execute("UPDATE beomon SET pbs_state='ok' WHERE node_id=" + node)
                    
            stdout.close()
            
            # Done!
            channel.close()
            ssh.close()
            
        except Exception, err:
            sys.stderr.write("Failed to check PBS state node with `pbsnodes` on clusman0-dev.francis.sam.pitt.edu: " + str(err) + "\n")

            syslog.syslog(syslog.LOG_WARNING, "Failed to check PBS state node with `pbsnodes` on clusman0-dev.francis.sam.pitt.edu for node: " + node)
            
            cursor.execute("UPDATE beomon SET pbs_state=NULL WHERE node_id=" + node)
    
    
    
    #
    # Verify that the node is still checking in if it is up
    #    
    if state == "up":
        last_check = do_sql_query("last_check", node)
        
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
