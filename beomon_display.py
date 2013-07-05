#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 3.1
# Last change: Removed IE detection, fixed the links to the CSS and JS files

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys, os, re, pymongo, time, locale, signal, subprocess, cgitb
from optparse import OptionParser



mongo_host = "clusman.frank.sam.pitt.edu"



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon status viewer.  This CGI program will display the status of compute nodes."
)

(options, args) = parser.parse_args()



            
            
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
    mongo_client = pymongo.MongoClient(mongo_host)

    db = mongo_client.beomon
    
    db.authenticate("beomon", dbpass)
    
    del(dbpass)
    
except Exception as err:
    sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
    sys.exit(1)
    
    
    
    
    
# Enable debugging
cgitb.enable()
    
    
    


# Main header
sys.stdout.write("""Content-type: text/html

<html>
<head>
<title>Frank Cluster Status</title>
<link href="../beomon-stuff/style.css" media="all" rel="stylesheet" type="text/css">
</head>
<body>

<script src="../beomon-stuff/jquery.min.js" type="text/javascript"></script>
""")





# Cluster summary
sys.stdout.write("""
<center>
    <h2>Beomon</h2>
    <p>Node state (up, down, boot ...) is checked every 5 minutes.</p>
</center>
    
<table id="summary" summary="Cluster Summary" width="65%" class="summary">
    <col width="15%">  <!--Compute summary-->
    <col width="10%">
    
    <col width="9%">  <!--Hidden column-->
    
    <col width="9%">  <!--Storage summary-->
    <col width="10%">
    <col width="4%">
    
    <col width="9%">  <!--Hidden column-->
    
    <col width="15%">  <!--Master summary-->
    <col width="8%">
    <thead>
        <tr>
            <th colspan="2">Compute Summary</th>
            <th style=\"background-color:#A4A4A4;\"></th>
            <th colspan="3">Storage Summary</th>
            <th style=\"background-color:#A4A4A4;\"></th>
            <th colspan="2">Master Summary</th>
        </tr>
    </thead>
    <tbody>
""")





locale.setlocale(locale.LC_ALL, 'en_US')
storage_totals = {
    "size" : 0,
    "used" : 0,
    "free" : 0,
}





# Print the storage detail columns
def storage_detail_cols(mount_point):
    if os.path.ismount(mount_point):
        fs_info = filesystem_info(mount_point)
        size_tb = round(float(fs_info[1]) / 1024 / 1024 / 1024, 2)
        used_tb = round(float(fs_info[2]) / 1024 / 1024 / 1024, 2)
        free_tb = round(float(fs_info[3]) / 1024 / 1024 / 1024, 2)
        percent_used = fs_info[4]
        
        storage_totals["size"] += size_tb
        storage_totals["used"] += used_tb
        storage_totals["free"] += free_tb

        sys.stdout.write("<td>" + mount_point + "</td>\n")
        
        sys.stdout.write("<td>" + str(size_tb) + " TB</td>\n")
        
        sys.stdout.write("<td style=\"text-align:center;\">" + percent_used + "</td>\n")
        
    else:
        sys.stdout.write("<td>" + mount_point + "</td>\n")
        sys.stdout.write("<td style=\"color:red;\">Unknown</td></td>\n")
        sys.stdout.write("<td style=\"color:red;\">Unknown</td></td>\n")




    
#
# Row 1
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Total </td>\n")
sys.stdout.write("<td>" + str(db.compute.count()) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Storage Summary
sys.stdout.write("<td style=\"text-align:center;font-weight:bold;background-color:silver\">Mount</td>\n")
sys.stdout.write("<td style=\"text-align:center;font-weight:bold;background-color:silver\">Size</td>\n")
sys.stdout.write("<td style=\"text-align:center;font-weight:bold;background-color:silver\">% Used</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td style=\"\"><span class='dropt'>Head0a<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head0a"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
    
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")

    

#
# Row 2
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Up </td>\n")
sys.stdout.write("<td>" + str(db.compute.find({ "state" : "up" }).count()) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/home")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head0b<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head0b"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")



#
# Row 3
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Down </td>\n")
num_node_docs_down = db.compute.find({ "state" : "down" }).count()
if num_node_docs_down == 0:
    sys.stdout.write("<td>0</td>\n")
else:
    downs = list()
    
    for node_doc in db.compute.find({ "state" : "down" }, { "_id" : 1 }):
        downs.append(node_doc["_id"])
    
    sys.stdout.write("<td><span style='color:red' class='dropt'>" + str(num_node_docs_down) + \
    "<span>" + str(sorted(downs)) + "</span></span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/home1")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head1a<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head1a"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")



#
# Row 4
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Error</td>\n")
num_node_docs_error = db.compute.find({ "state" : "error" }).count()
if num_node_docs_error == 0:
    sys.stdout.write("<td>0</td>\n")
else:
    erroreds = list()
    
    for node_doc in db.compute.find({ "state" : "error" }, { "_id" : 1 }):
        erroreds.append(node_doc["_id"])
    
    sys.stdout.write("<td><span style='color:red' class='dropt'>" + str(num_node_docs_error) + \
    "<span>" + str(sorted(erroreds)) + "</span></span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/home2")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head1b<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head1b"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")


    
#
# Row 5
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Booting </td>\n")
num_node_docs_boot = db.compute.find({ "state" : "boot" }).count()
if num_node_docs_boot == 0:
    sys.stdout.write("<td>0</td>\n")
    
else:
    bootings = list()
    
    for node_doc in db.compute.find({ "state" : "boot" }, { "_id" : 1 }):
        bootings.append(node_doc["_id"])
    
    sys.stdout.write("<td><span style='color:red' class='dropt'>" + str(num_node_docs_boot) + \
    "<span>" + str(sorted(bootings)) + "</span></span></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/gscratch1")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head2a<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head2a"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")


    
#
# Row 6
#

# Compute Summary
sys.stdout.write("<tr><td>Nodes Orphaned </td>\n")
num_node_docs_orphan = db.compute.find({ "state" : "orphan" }).count()
if num_node_docs_orphan == 0:
    sys.stdout.write("<td>0</td>\n")
    
else:
    orphans = list()
    
    for node_doc in db.compute.find({ "state" : "orphan" }, { "_id" : 1 }):
        orphans.append(node_doc["_id"])
    
    sys.stdout.write("<td><span style='color:red' class='dropt'>" + str(num_node_docs_orphan) + \
    "<span>" + str(sorted(orphans)) + "</span></span></td>\n")
    
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/gscratch2")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head2b<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head2b"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")


    
#
# Row 7
#

# Compute Summary
cpu_total = 0
for node_doc in db.compute.find({}, { "cpu" : 1}):
    try:
        cpu_total += node_doc["cpu"]["cpu_num"]
    
    except KeyError:
        pass

sys.stdout.write("<tr><td>Total CPU Cores </td>\n")
sys.stdout.write("<td>" + locale.format("%d", cpu_total, grouping=True) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/pan")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head3a<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head3a"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")


    
#
# Row 8
#

# Compute Summary
gpu_cores_total = 0
for node_doc in db.compute.find({}, { "gpu" : 1 }):
    try:
        gpu_cores_total += node_doc["gpu"]["num_cores"]
        
    except KeyError:
        pass
        
sys.stdout.write("<tr><td>Total GPU Cores:</td>\n")
sys.stdout.write("<td>" + locale.format("%0.0f", gpu_cores_total, grouping=True) + "</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
storage_detail_cols("/data/sam")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td><span class='dropt'>Head3b<span>\n")
master_info = db.head_clusman.find_one({"_id" : "head3b"})

if master_info is None:
    sys.stdout.write("<td style=\"color:red;\">Unknown</td></td></tr>\n\n")
    
else:
    sys.stdout.write(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
    sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

if master_info is not None:
    if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
    master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
        sys.stdout.write("<td>ok</td></tr>\n\n")
        
    else:
        sys.stdout.write("<td style=\"color:red\">Down</td></tr>\n\n")
        
        
        
#
# Row 9
#

# Compute Summary
ram_total = 0
for node_doc in db.compute.find({}, { "ram" : 1 }):
    try:
        ram_total += node_doc["ram"]
        
    except KeyError:
        pass
        
sys.stdout.write("<tr><td>Total RAM </td>\n")
sys.stdout.write("<td>" + locale.format("%0.2f", ram_total / float(1024), grouping=True) + " TB</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
sys.stdout.write("<td style=\"text-align:center\">Total:</td>\n")
sys.stdout.write("<td>" + str(storage_totals["size"]) + " TB</td>\n")
sys.stdout.write("<td style=\"text-align:center;\">" + str(int(round((storage_totals["used"] / storage_totals["size"]) * 100, 0))) + "%</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")



#
# Row 10
#

# Compute Summary
scratch_total = 0
for node_doc in db.compute.find().sort("_id", 1):
    try:
        scratch_total += node_doc["scratch_size"]
        
    except KeyError:
        pass
        
sys.stdout.write("<tr><td>Total /scratch</td>\n")
sys.stdout.write("<td>" + locale.format("%0.2f", scratch_total / float(1024), grouping=True) + " TB</td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")


# Storage Summary
sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")

sys.stdout.write("<td style=\"background-color:#A4A4A4\"></td>\n")


# Master Summary
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")
sys.stdout.write("<td style=\"background-color:#A4A4A4;\"></td>\n")



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
            <th scope="col">/data/pkg</th>
            <th scope="col">/data/sam</th>
            <th scope="col">/gscratch1</th>
            <th scope="col">/home</th>
            <th scope="col">/home1</th>
            <th scope="col">/home2</th>
            <th scope="col">/pan</th>
            <th scope="col">/scratch</th>
        </tr>
    </thead>
    <tbody>
""")



# Loop through each node in the DB
for node_doc in db.compute.find().sort("_id", 1):
    #
    # Node number
    #
    
    sys.stdout.write("<tr>\n<td><span class='dropt'>" + str(node_doc["_id"]) + "<span style=text-align:left>\n")
    
    # If it looks like we are missing information, note to skip the node_doc's details
    try:
        missing_info = False
        
        # The dropt data
        sys.stdout.write("CPU:<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Type: " + node_doc["cpu"]["cpu_type"] + "<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cores: " + str(node_doc["cpu"]["cpu_num"]) + "<br>\n")
        sys.stdout.write("GPU: " + "<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cards: " + str(node_doc["gpu"]["num_cards"]) + "<br>\n")
        
        if node_doc["gpu"]["num_cards"] != 0:
            sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total RAM Size: " + str(node_doc["gpu"]["ram_size"]) + " GB<br>\n")
            sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total GPU Cores: " + locale.format("%0.0f", node_doc["gpu"]["num_cores"], grouping=True) + "<br>\n")
            
        sys.stdout.write("IPs:<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;GigE IP: " + node_doc["ip"]["gige"] + "<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;BMC IP: " + node_doc["ip"]["bmc"] + "<br>\n")
        sys.stdout.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;IB IP: " + node_doc["ip"]["ib"] + "<br>\n")
        sys.stdout.write("RAM: " + str(node_doc["ram"]) + " GB<br>\n")
        sys.stdout.write("Scratch Size: " + str(node_doc["scratch_size"]) + " GB<br>\n")
        sys.stdout.write("Rack: " + node_doc["rack"] + "<br>\n")
        sys.stdout.write("Serial: " + node_doc["serial"] + "<br>\n")
        sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["last_check"])) + "<br>\n")
        sys.stdout.write("</span></span></td>\n")
        
    except KeyError:
        sys.stdout.write("</span></span></td>\n")
        
        missing_info = True
    
    
    
    
    
    #
    # State
    #
    if node_doc["_id"] == 242 and missing_info is False:
        sys.stdout.write("<td>up</td>\n")
        
    elif node_doc["_id"] == 242 and missing_info is True:
        sys.stdout.write("<td>up</td>\n")
        
        print "<td></td>\n" * 4
        print "<td style=\"color:red;\">Missing data</td>\n"
        print "<td></td>\n" * 6
        
        continue
        
    elif "state" not in node_doc:
        sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
        print "<td></td>" * 11
        
        continue
        
    elif node_doc["state"] == "up" and missing_info is False:
        sys.stdout.write("<td>up</td>\n")
        
    elif node_doc["state"] == "up" and missing_info is True:
        sys.stdout.write("<td>up</td>\n")
        
        print "<td></td>\n" * 4
        print "<td style=\"color:red;\">Missing data</td>\n"
        print "<td></td>\n" * 6
        
        continue
        
    else:
        sys.stdout.write("<td><span style='color:red' class='dropt'>" + node_doc["state"] + "<span>Since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["state_time"])) + "</span></span></td>\n")
        
        print "<td></td>" * 11
        
        continue
        
        
        
        
        
    #
    # Stale data?
    #
    
    if int(time.time()) - node_doc["last_check"] > 60 * 30:
        print "<td></td>\n" * 4
        print "<td style=\"color:red;\">Stale data</td>\n"
        print "<td></td>\n" * 6
        
        continue
        
    
    
    
    
    #    
    # PBS
    #
    
    if "pbs" not in node_doc:
        sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
    elif node_doc["pbs"] is True:
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td style=\"color:red;\">down</td>\n")
        
        
        
        
        
    #    
    # Moab
    #
    
    if "moab" not in node_doc:
        sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
    elif node_doc["moab"] is True:
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td style=\"color:red;\">down</td>\n")
        
        
        
        
        
    #    
    # Infiniband
    #
    
    if "infiniband" not in node_doc:
        sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
    elif node_doc["infiniband"] is True:
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td style=\"color:red;\">down</td>\n")



        
    
    #
    # Tempurature
    #
    
    #tempurature = compute_query("tempurature", node_doc)
    #if tempurature == None:
        #sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
    #else:
        #sys.stdout.write("<td>" + tempurature + "</td>\n")


        
        
        
    #
    # Filesystems
    #
    
    filesystems = [
        "datapkg",
        "datasam",
        "gscratch1",
        "home0",
        "home1",
        "home2",
        "panasas",
        "scratch",
    ]

    
    for filesystem in sorted(filesystems):
        if filesystem not in node_doc["filesystems"]:
            sys.stdout.write("<td style=\"color:red;\">unknown</td>\n")
        
        elif node_doc["filesystems"][filesystem] is True:
            sys.stdout.write("<td>ok</td>\n")
        
        else:
            sys.stdout.write("<td style=\"color:red;\">down</td>\n")
        
        
        
        
    sys.stdout.write("</tr>\n")





# Footer
sys.stdout.write("""    </tbody>
</table>
<br><br><br><br><br><br><br><br><br><br>
<script src="../beomon-stuff/jquery.stickytableheaders.js" type="text/javascript"></script> 

<script type="text/javascript">

                $(document).ready(function () {
                        $("table").stickyTableHeaders();
                });

</script>
</body>
</html>
""")
