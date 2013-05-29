#!/usr/bin/env python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 2
# Last change: Removed chong mount points, added storage, head and compute summary/health tables, 
# switched compute node SQL table name to 'compute'

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, MySQLdb, time, locale, signal, subprocess
from optparse import OptionParser



mysql_host = "clusman.frank.sam.pitt.edu"
#mysql_host = "headnode1.frank.sam.pitt.edu"
nodes = ""



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon status viewer.  This CGI program will display the status of compute nodes."
)

(options, args) = parser.parse_args()



# Query MySQL for a given column of a given node
def compute_query(column, node):
    cursor.execute("SELECT " + column + " FROM compute WHERE node_id=" + node)
        
    results = cursor.fetchone()
        
    if results is None:
        return False
        
    else:       
        return results[0]
    
    
def cluster_health_query(column, node):
    cursor.execute("SELECT " + column + " FROM cluster_health WHERE node_id='" + node + "'")
        
    results = cursor.fetchone()
    
    if results is None:
        return False
        
    else:       
        return results[0]
            
            
            
# Prepare for subprocess timeouts
class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)



# Get filesystem info
def filesystem_info(filesystem):
    signal.alarm(30)
            
    info = subprocess.Popen(["/bin/df", "-P", filesystem], stdin=None, stdout=subprocess.PIPE, shell=False)
    out = info.communicate()[0]
                    
    signal.alarm(0)
    
    for line in out.split(os.linesep):
        line = line.rstrip()
        
        if re.search("^Filesystem", line) is not None:
            continue
        
        return line.split()

            

# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip("\n")
dbpasshandle.close()

    
    
# Open a DB connection
try:
    db = MySQLdb.connect(
        host=mysql_host, user="beomon",
        passwd=dbpass, db="beomon"
    )
                                             
    cursor = db.cursor()
    
except Exception as err:
    sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
    sys.exit(1)
    


# Main header
sys.stdout.write("""Content-type: text/html

<html>
<head>
<title>Frank Compute Node Status</title>
<link href="beomon-stuff/style.css" media="all" rel="stylesheet" type="text/css">
</head>
<body>

<script src="beomon-stuff/jquery.min.js" type="text/javascript"></script>

<script type="text/javascript">
  // IE feature detection
  if(!jQuery.support.htmlSerialize){
    document.write("<center><p><span style='color:red;background-color:black;font-size:150%'>WARNING: You appear to be unsing an usupported browser.  Please use Firefox, Chromium or Chrome instead.</span></p></center>");
  }
</script>
""")





# Cluster summary
sys.stdout.write("""
<center>
    <h2>Beomon</h2>
    <p>Node state (up, down, boot ...) is checked every 5 minutes.</p>
</center>
    
<table id="summary" summary="Cluster Summary" width="65%" class="summary">
    <col width="15%">
    <col width="8%">
    <col width="10%">
    <col width="15%">
    <col width="8%">
    <col width="10%">
    <col width="15%">
    <col width="8%">
    <thead>
        <tr>
            <th colspan="2">Compute Summary</th>
            <th style=\"background-color:#A4A4A4;\"></th>
            <th colspan="2">Storage Summary</th>
            <th style=\"background-color:#A4A4A4;\"></th>
            <th colspan="2">Master Summary</th>
        </tr>
    </thead>
    <tbody>
""")



cluster_summary = {
    "nodes_total" : 0,
    "nodes_up" : 0,
    "nodes_down_error" : 0,
    "nodes_boot" : 0,
    "nodes_orphaned" : 0,
    "cpu_total" : 0,
    "ram_total" : 0.0,
    "scratch_total" : 0.0,
}



# Loop through each node in the DB
cursor.execute("SELECT state, cpu_num, ram, scratch_size FROM compute")

for row in sorted(cursor.fetchall()):
    [state, cpu_num, ram, scratch_size] = row
    
    cluster_summary["nodes_total"] += 1
    
    if state is not None:
        if state == "up":
            cluster_summary["nodes_up"] += 1

        elif state == "down" or state == "error":
            cluster_summary["nodes_down_error"] += 1

        elif state == "boot":
            cluster_summary["nodes_boot"] += 1
            
        elif state == "orphaned":
            cluster_summary["nodes_orphaned"] += 1

    if cpu_num is not None:
        cluster_summary["cpu_total"] += cpu_num
        
    if ram is not None:
        cluster_summary["ram_total"] += float(ram)
        
    if scratch_size is not None:
        cluster_summary["scratch_total"] += float(scratch_size)


        
#locale.setlocale(locale.LC_ALL, '')
# Row 1
sys.stdout.write("<tr><td>Nodes Total </td>\n")
sys.stdout.write("<td>" + str(cluster_summary["nodes_total"]) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

if os.path.ismount("/home"):
    fs_info = filesystem_info("/home")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/home<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/home </td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head0a<span>\n")
sys.stdout.write("Original Frank and Fermi Penguin<br>\nPrimary: 0-88<br>\nSecondary: 89-176<br>\n")
last_check = cluster_health_query("last_check", "head0a")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head0a'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")

    

# Row 2
sys.stdout.write("<tr><td>Nodes Up </td>\n")
sys.stdout.write("<td>" + str(cluster_summary["nodes_up"]) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

if os.path.ismount("/home1"):
    fs_info = filesystem_info("/home1")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/home1<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/home1</td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head0b <span>\n")
sys.stdout.write("Original Frank and Fermi Penguin<br>\nPrimary: 89-176<br>\nSecondary: 1-88<br>\n")
last_check = cluster_health_query("last_check", "head0b")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head0b'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 3
sys.stdout.write("<tr><td>Nodes Down/Error </td>\n")
sys.stdout.write("<td>" + str(cluster_summary["nodes_down_error"]) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

if os.path.ismount("/home2"):
    fs_info = filesystem_info("/home2")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/home2<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/home2</td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head1a <span>\n")
sys.stdout.write("IBM<br>\nPrimary: 177-209<br>\nSecondary: 210-241<br>\n")
last_check = cluster_health_query("last_check", "head1a")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head1a'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 4
sys.stdout.write("<tr><td>Nodes Booting </td>\n")
sys.stdout.write("<td>" + str(cluster_summary["nodes_boot"]) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

if os.path.ismount("/gscratch1"):
    fs_info = filesystem_info("/gscratch1")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/gscratch1<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/gscratch1</td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head1b <span>\n")
sys.stdout.write("IBM<br>\nPrimary: 210-241<br>\nSecondary: 177-209<br>\n")
last_check = cluster_health_query("last_check", "head1b")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head1b'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 5
sys.stdout.write("<tr><td>Nodes Orphaned </td>\n")
sys.stdout.write("<td>" + str(cluster_summary["nodes_orphaned"]) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

if os.path.ismount("/pan"):
    fs_info = filesystem_info("/pan")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/pan<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/pan</td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head2a <span>\n")
sys.stdout.write("Sandybridge<br>\nPrimary: 242-284<br>\nSecondary: 285-324<br>\n")
last_check = cluster_health_query("last_check", "head2a")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head2a'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 6
sys.stdout.write("<tr><td>Total CPUs </td>\n")
sys.stdout.write("<td>" + locale.format('%d',cluster_summary["cpu_total"], 1) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

if os.path.ismount("/data/sam"):
    fs_info = filesystem_info("/data/sam")
    size_tb = str(round(float(fs_info[1]) / 1024 / 1024 / 1024, 2))
    used_tb = str(round(float(fs_info[2]) / 1024 / 1024 / 1024, 2))
    free_tb = str(round(float(fs_info[3]) / 1024 / 1024 / 1024, 2))
    percent_used = fs_info[4]

    sys.stdout.write("<td><span align='left' class='dropt'>/data/sam<span>\n")
    sys.stdout.write("Size: " + size_tb + " TB<br>\nUsed: " + used_tb + " TB<br>\nFree: " + free_tb + " TB<br>\n</span></span></td>\n")
    
    sys.stdout.write("<td>" + percent_used + " used</td>\n")
    
else:
    sys.stdout.write("<td>/data/sam</td>\n")
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head2b <span>\n")
sys.stdout.write("Sandybridge<br>\nPrimary: 285-324<br>\nSecondary: 242-284<br>\n")
last_check = cluster_health_query("last_check", "head2b")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head2b'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 7
sys.stdout.write("<tr><td>Total RAM </td>\n")
sys.stdout.write("<td>" + str(round(cluster_summary["ram_total"] / 1024, 2)) + " TB</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head3a <span>\n")
sys.stdout.write("Interlagos<br>\nPrimary: 325-350<br>\nSecondary: 351-378<br>\n")
last_check = cluster_health_query("last_check", "head3a")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head3a'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


    
# Row 8
sys.stdout.write("<tr><td>Total /scratch</td>\n")
sys.stdout.write("<td>" + str(round(cluster_summary["scratch_total"] / 1024, 2)) + " TB</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td><span align='left' class='dropt'>Head3b <span>\n")
sys.stdout.write("Interlagos<br>\nPrimary: 351-378<br>\nSecondary: 325-350<br>\n")
last_check = cluster_health_query("last_check", "head3b")
sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "</span></span></td>\n")

cursor.execute("SELECT beoserv, bpmaster, recvstats, kickbackdaemon FROM cluster_health WHERE node_id='head3b'")
results = cursor.fetchone()
if results is None:
    sys.stdout.write("<td><span style='color:red'>Unknown</span></td></tr>\n\n")
    
elif results == (1, 1, 1, 1):
    sys.stdout.write("<td>OK</td></tr>\n\n")
    
else:
    sys.stdout.write("<td><span style='color:red'>Down</span></td></tr>\n\n")


sys.stdout.write("""
    </tbody>
</table>
<br>
<br>
""")





# Node table header
sys.stdout.write("""
<table id="nodes" summary="Node status" class="compute_nodes">
    <thead>
        <tr>
            <th scope="col">Node</th>
            <th scope="col">State</th>
            <th scope="col">PBS</th>
            <th scope="col">Moab</th>
            <th scope="col">Infiniband</th>
            <th scope="col">/scratch</th>
            <th scope="col">/data/pkg</th>
            <th scope="col">/data/sam</th>
            <th scope="col">/gscratch1</th>
            <th scope="col">/home</th>
            <th scope="col">/home1</th>
            <th scope="col">/home2</th>
            <th scope="col">/pan</th>
        </tr>
    </thead>
    <tbody>
""")



# Loop through each node in the DB
cursor.execute("SELECT node_id FROM compute")

nodes = cursor.fetchall()

for node in nodes:
    node = str(node[0])
    
    
    sys.stdout.write("<tr>\n<td><span align='left' class='dropt'>" + node + "<span>\n")
    
    
    cpu_type = compute_query("cpu_type", node)
    if cpu_type: sys.stdout.write("CPU Type: " + cpu_type + "<br>\n")
    
    
    cpu_num = compute_query("cpu_num", node)
    if cpu_num: sys.stdout.write("Number of CPUs: " + str(cpu_num) + "<br>\n")
    
    
    ram = compute_query("ram", node)
    if ram: sys.stdout.write("RAM: " + str(ram) + " GB<br>\n")
    
    
    scratch_size = compute_query("scratch_size", node)
    if scratch_size: sys.stdout.write("Scratch Size: " + str(scratch_size) + " GB<br>\n")
    
    
    ib = compute_query("infiniband", node)
    if ib == "n/a":
        sys.stdout.write("Infiniband?: No" + "<br>\n")
        
    elif ib:
        sys.stdout.write("Infiniband?: Yes" + "<br>\n")
    
    
    gpu = compute_query("gpu", node)
    #sys.stdout.write("GPU?: " + gpu + "<br>")
    if gpu == 0:
        sys.stdout.write("GPU?: No" + "<br>\n")
        
    elif gpu == 1:
        sys.stdout.write("GPU?: Yes" + "<br>\n")
    
    
    last_check = compute_query("last_check", node)
    if last_check: sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "<br>\n")
    
    
    sys.stdout.write("</span></span></td>\n")
    
    
    
    # State
    state = compute_query("state", node)
    if state == None:
        sys.stdout.write("<td><span style='color:red'><span>unknown</span></span></td>\n")
        
        print "<td></td>" * 11
        
        continue
        
    elif state == "up":
        sys.stdout.write("<td>up\n")
        
    else:
        state_time = compute_query("state_time", node)
        
        sys.stdout.write("<td><span style='color:red' class='dropt'>" + state + "<span>Since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state_time)) + "</span></span></td>\n")
        
        print "<td></td>" * 11
        
        continue
        
        
        
    # PBS
    pbs_state = compute_query("pbs_state", node)
    if pbs_state == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif pbs_state == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + pbs_state + "</span></td>\n")
        
        
        
    # Moab
    moab = compute_query("moab", node)
    if moab == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif moab == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + moab + "</span></td>\n")
        
        
        
    # Infiniband
    infiniband = compute_query("infiniband", node)
    if infiniband == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif infiniband == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    elif infiniband == "n/a":
        sys.stdout.write("<td>n/a</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + infiniband + "</span></td>\n")



    ### Tempurature
    ##tempurature = compute_query("tempurature", node)
    ##if tempurature == None:
        ##sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    ##else:
        ##sys.stdout.write("<td>" + tempurature + "</td>\n")


        
    # /scratch
    scratch = compute_query("scratch", node)
    if scratch == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif scratch == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + scratch + "</span></td>\n")

        
        
    # Filesystems to check
    filesystems = {
        "/data/pkg" : "datapkg",
        "/data/sam" : "datasam",
        "/gscratch1" : "gscratch1",
        "/home" : "home0",
        "/home1" : "home1",
        "/home2" : "home2",
        "/pan" : "panasas",
    }

    
    for mount_point in sorted(filesystems.iterkeys()):
        mount_status = compute_query(filesystems[mount_point], node)
        
        if mount_status == None:
            sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
        elif mount_status == "ok":
            sys.stdout.write("<td>ok</td>\n")
        
        else:
            sys.stdout.write("<td><span style='color:red'>" + mount_status + "</span></td>\n")
        
        
        
    sys.stdout.write("</tr>\n")



# Close the DB, we're done with it
db.close()



# Footer
sys.stdout.write("""    </tbody>
</table>
<br><br><br><br><br><br><br>
<script src="beomon-stuff/jquery.stickytableheaders.js" type="text/javascript"></script> 

<script type="text/javascript">

                $(document).ready(function () {
                        $("table").stickyTableHeaders();
                });

</script>
</body>
</html>
""")
