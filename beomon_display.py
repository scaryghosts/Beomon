#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 4
# Last change: Migrated to the Bottle module, added node detail page for each node

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/bin")
import os, re, pymongo, time, locale, signal, subprocess
import bottle
from bottle import Bottle, run, template, route
from optparse import OptionParser



mongo_host = "clusman.frank.sam.pitt.edu"



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon status viewer.  This is a Web server which will display the status of the cluster."
)

(options, args) = parser.parse_args()



            
            
# Get filesystem info
def filesystem_info(filesystem):
    info = subprocess.Popen(["/bin/df", "-P", filesystem], stdin=None, stdout=subprocess.PIPE, shell=False)
    out = info.communicate()[0]
                    
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
    
    
    
    
    
bottle.TEMPLATE_PATH.insert(0, "/opt/sam/beomon/html/views")
    
    
    
    

# Individual detail page for a node    
@route("/node/<node>")
def show_node_page(node):
    # Did we get a proper node number?
    try:
        node = int(node)
        
    except ValueError:
        return "No such node: " + node
    
    
    node_doc = db.compute.find_one(
        {
            "_id" : node
        },
    )
    
    # Does the node exist?
    if node_doc is None:
        return "No such node: " + str(node)
        
        
    # Make things pretty...
    try:
        if node_doc["gpu"]["num_cards"] != 0:
            node_doc["gpu"]["num_cores"] = locale.format("%0.0f", node_doc["gpu"]["num_cores"], grouping=True)
            
        node_doc["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["last_check"]))
        
    except KeyError:
        return "Details missing for node " + str(node)
        
    
    
    #
    # Build the outage information
    #
    
    outages = []
    
    down_times = node_doc.get("down_times")
    up_times = node_doc.get("up_times")
            

    if down_times is not None or up_times is not None:
        while True:
            outage_details = {}
            
            
            # Get the lowest times
            try:
                min_down = min(down_times)
                
            except:
                down_times = None
                min_down = None
                
            try:
                min_up = min(up_times)
                
            except:
                up_times = None
                min_up = None
                
                

            # Do we have anything to look at this iteration?
            if down_times is None and up_times is None:
                break
                
                
                
            # Handle the down time
            if min_down is None:
                outage_details["down"] = "Unknown"
            
            elif min_up is None:
                outage_details["down"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_down)) + ""
                down_times.remove(min_down)
            
            elif min_down < min_up:
                outage_details["down"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_down)) + ""
                down_times.remove(min_down)
                
            else:
                outage_details["down"] = "Unknown"
                
                
                
            # Handle the up time
            if min_up is None:
                outage_details["up"] = "Unknown"
            
            elif min_down is None:
                outage_details["up"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_up)) + ""
                up_times.remove(min_up)
            
            elif min_down < min_up:
                outage_details["up"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_up)) + ""
                up_times.remove(min_up)
                
            else:
                outage_details["up"] = "Unknown"
                
                
                
            # Handle the outage duration
            if min_down is not None and min_up is not None and min_down < min_up:
                diff = min_up - min_down
                
                days = diff / (60 * 60 * 24)
                
                remaining_seconds = diff - days
                
                outage_details["outage"] = str(days) + ":" + time.strftime('%H:%M:%S', time.gmtime(remaining_seconds)) + ""
                
            else:
                outage_details["outage"] = "Unknown"
                
                
            outages.append(outage_details)
        
    
    return bottle.template("node", node_doc=node_doc, outages=outages)





@route("/")
def index():
    index_page = []
    
    # Main header
    index_page.append("""
    <html>
    <head>
    <title>Frank Cluster Status</title>
    <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">
    </head>
    <body>

    <script src="/static/jquery.min.js" type="text/javascript"></script>
    """)





    # Cluster summary
    index_page.append("""
    <center>
        <h2>Beomon</h2>
        <p>Node state (up, down, boot ...) is checked every 5 minutes.</p>
    </center>
        
    <table id="summary" summary="Cluster Summary" class="summary">
        <col width="15%">  <!--Compute summary-->
        <col width="10%">
        
        <col>  <!--Hidden column-->
        
        <col width="9%">  <!--Storage summary-->
        <col width="10%">
        <col width="4%">
        
        <col>  <!--Hidden column-->
        
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

            index_page.append("<td>" + mount_point + "</td>\n")
            
            index_page.append("<td>" + str(size_tb) + " TB</td>\n")
            
            index_page.append("<td style=\"text-align:center;\">" + percent_used + "</td>\n")
            
        else:
            index_page.append("<td>" + mount_point + "</td>\n")
            index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td>\n")
            index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td>\n")




        
    #
    # Row 1
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Total </td>\n")
    index_page.append("<td>" + str(db.compute.count()) + "</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Storage Summary
    index_page.append("<td style=\"text-align:center;font-weight:bold;background-color:silver\">Mount</td>\n")
    index_page.append("<td style=\"text-align:center;font-weight:bold;background-color:silver\">Size</td>\n")
    index_page.append("<td style=\"text-align:center;font-weight:bold;background-color:silver\">% Used</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td style=\"\"><span class='dropt'>Head0a<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head0a"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
        
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")

        

    #
    # Row 2
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Up </td>\n")
    index_page.append("<td>" + str(db.compute.find({ "state" : "up" }).count()) + "</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/home")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head0b<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head0b"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")



    #
    # Row 3
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Down </td>\n")
    num_node_docs_down = db.compute.find({ "state" : "down" }).count()
    if num_node_docs_down == 0:
        index_page.append("<td>0</td>\n")
    else:
        downs = list()
        
        for node_doc in db.compute.find({ "state" : "down" }, { "_id" : 1 }):
            downs.append(node_doc["_id"])
        
        index_page.append("<td><span style='color:red' class='dropt'>" + str(num_node_docs_down) + \
        "<span>" + str(sorted(downs)) + "</span></span></td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/home1")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head1a<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head1a"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")



    #
    # Row 4
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Error</td>\n")
    num_node_docs_error = db.compute.find({ "state" : "error" }).count()
    if num_node_docs_error == 0:
        index_page.append("<td>0</td>\n")
    else:
        erroreds = list()
        
        for node_doc in db.compute.find({ "state" : "error" }, { "_id" : 1 }):
            erroreds.append(node_doc["_id"])
        
        index_page.append("<td><span style='color:red' class='dropt'>" + str(num_node_docs_error) + \
        "<span>" + str(sorted(erroreds)) + "</span></span></td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/home2")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head1b<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head1b"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")


        
    #
    # Row 5
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Booting </td>\n")
    num_node_docs_boot = db.compute.find({ "state" : "boot" }).count()
    if num_node_docs_boot == 0:
        index_page.append("<td>0</td>\n")
        
    else:
        bootings = list()
        
        for node_doc in db.compute.find({ "state" : "boot" }, { "_id" : 1 }):
            bootings.append(node_doc["_id"])
        
        index_page.append("<td><span style='color:red' class='dropt'>" + str(num_node_docs_boot) + \
        "<span>" + str(sorted(bootings)) + "</span></span></td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/gscratch1")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head2a<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head2a"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")


        
    #
    # Row 6
    #

    # Compute Summary
    index_page.append("<tr><td>Nodes Orphaned </td>\n")
    num_node_docs_orphan = db.compute.find({ "state" : "orphan" }).count()
    if num_node_docs_orphan == 0:
        index_page.append("<td>0</td>\n")
        
    else:
        orphans = list()
        
        for node_doc in db.compute.find({ "state" : "orphan" }, { "_id" : 1 }):
            orphans.append(node_doc["_id"])
        
        index_page.append("<td><span style='color:red' class='dropt'>" + str(num_node_docs_orphan) + \
        "<span>" + str(sorted(orphans)) + "</span></span></td>\n")
        
    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/gscratch2")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head2b<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head2b"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")


        
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

    index_page.append("<tr><td>Total CPU Cores </td>\n")
    index_page.append("<td>" + locale.format("%d", cpu_total, grouping=True) + "</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/pan")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head3a<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head3a"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")


        
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
            
    index_page.append("<tr><td>Total GPU Cores:</td>\n")
    index_page.append("<td>" + locale.format("%0.0f", gpu_cores_total, grouping=True) + "</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    storage_detail_cols("/data/sam")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td><span class='dropt'>Head3b<span>\n")
    master_info = db.head_clusman.find_one({"_id" : "head3b"})

    if master_info is None:
        index_page.append("<td style=\"font-weight:bold;color:red;\">Unknown</td></td></tr>\n\n")
        
    else:
        index_page.append(master_info["compute_node_class"] + "<br>\nPrimary: " + master_info["primary_of"] + "<br>\nSecondary: " + master_info["secondary_of"] + "<br>\n")
        index_page.append("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(master_info["last_check"])) + "</span></span></td>\n")

    if master_info is not None:
        if master_info["processes"]["beoserv"] is True and master_info["processes"]["kickbackdaemon"] is True and\
        master_info["processes"]["bpmaster"] is True and master_info["processes"]["recvstats"] is True:
            index_page.append("<td>ok</td></tr>\n\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red\">Down</td></tr>\n\n")
            
            
            
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
            
    index_page.append("<tr><td>Total RAM </td>\n")
    index_page.append("<td>" + locale.format("%0.2f", ram_total / float(1024), grouping=True) + " TB</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    index_page.append("<td style=\"text-align:center\">Total:</td>\n")
    index_page.append("<td>" + str(storage_totals["size"]) + " TB</td>\n")
    index_page.append("<td style=\"text-align:center;\">" + str(int(round((storage_totals["used"] / storage_totals["size"]) * 100, 0))) + "%</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")
    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")



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
            
    index_page.append("<tr><td>Total /scratch</td>\n")
    index_page.append("<td>" + locale.format("%0.2f", scratch_total / float(1024), grouping=True) + " TB</td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")


    # Storage Summary
    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")
    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")
    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")

    index_page.append("<td style=\"background-color:#A4A4A4\"></td>\n")


    # Master Summary
    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")
    index_page.append("<td style=\"background-color:#A4A4A4;\"></td>\n")



    index_page.append("""
        </tbody>
    </table>
    <br>
    <br>
    """)





    # Node table header
    index_page.append("""
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
        
        if "state" in node_doc and (node_doc["state"] == "down" or node_doc["state"] == "error"):
            index_page.append("<tr style=\"background-color:red\">\n<td><a href=\"/beomon/node/" + str(node_doc["_id"]) + "\">" + str(node_doc["_id"]) + "</a></td>\n")
            
        else:
            index_page.append("<tr>\n<td><a href=\"/beomon/node/" + str(node_doc["_id"]) + "\">" + str(node_doc["_id"]) + "</a></td>\n")

            
            
            
        
        #
        # State
        #
        if node_doc["_id"] == 242:
            index_page.append("<td>up</td>\n")
            
        elif "state" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
            for _ in range(11): index_page.append("<td></td>")
            
            continue
        
        elif node_doc["state"] == "up":
            index_page.append("<td>up</td>\n")
            
        else:
            index_page.append("<td><span style='font-weight:bold;' class='dropt'>" + node_doc["state"] + "<span>Since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["state_time"])) + "</span></span></td>\n")
            
            for _ in range(11): index_page.append("<td></td>")
            
            continue
            
            
            
            
            
        #
        # Stale data?
        #
        
        if int(time.time()) - node_doc["last_check"] > 60 * 30:
            for _ in range(4): index_page.append("<td></td>\n")
            index_page.append("<td style=\"font-weight:bold;color:red;\">Stale data</td>\n")
            for _ in range(6): index_page.append("<td></td>\n")
            
            continue
            
        
        
        
        
        #    
        # PBS
        #
        
        if "pbs" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        elif node_doc["pbs"] is True:
            index_page.append("<td>ok</td>\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
            
            
            
            
            
        #    
        # Moab
        #
        
        if "moab" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        elif node_doc["moab"] is True:
            index_page.append("<td>ok</td>\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
            
            
            
            
            
        #    
        # Infiniband
        #
        
        if "infiniband" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        elif node_doc["infiniband"] is True:
            index_page.append("<td>ok</td>\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")



            
        
        #
        # Tempurature
        #
        
        #tempurature = compute_query("tempurature", node_doc)
        #if tempurature == None:
            #index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        #else:
            #index_page.append("<td>" + tempurature + "</td>\n")


            
            
            
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
                index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
            elif node_doc["filesystems"][filesystem] is True:
                index_page.append("<td>ok</td>\n")
            
            else:
                index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
            
            
            
            
        index_page.append("</tr>\n")





    # Footer
    index_page.append("""    </tbody>
    </table>
    <br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>
    <script src="/static/jquery.stickytableheaders.js" type="text/javascript"></script> 

    <script type="text/javascript">

                    $(document).ready(function () {
                            $("table").stickyTableHeaders();
                    });

    </script>
    </body>
    </html>
    """)
    
    
    
    return index_page

    
    
    

# Run the server
#run(host="0.0.0.0", port=8080, debug=True)
application = bottle.app() 