#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon Web interface
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)



# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/bin")
import os, re, pymongo, time, locale, signal, subprocess, ConfigParser, traceback
import bottle
from bottle import Bottle, run, template, route, post, get, request
from optparse import OptionParser



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon status viewer.  This is a Web server which will display the status of the cluster."
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



            
            
# Get filesystem info
def filesystem_info(filesystem):
    info = subprocess.Popen(["/bin/df", "-P", filesystem], stdin=None, stdout=subprocess.PIPE, shell=False)
    out = info.communicate()[0]
                    
    for line in out.split(os.linesep):
        line = line.rstrip()
        
        if re.search("^Filesystem", line) is not None:
            continue
        
        return line.split()
        
        
        
        
        
# Read the config file
config = ConfigParser.ConfigParser()
config.read("/opt/sam/beomon/etc/beomon.conf")

main_config = dict(config.items("main"))

            
            
            

# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip("\n")
dbpasshandle.close()

    
    
# Open a DB connection
try:
    mongo_client = pymongo.MongoClient(main_config["mongo_host"])

    db = mongo_client.beomon
    
    db.authenticate("beomon", dbpass)
    
    del(dbpass)
    
except:
    fatal_error("Failed to connect to the Beomon database")
    
    
    
    
    
bottle.TEMPLATE_PATH.insert(0, "/opt/sam/beomon/html/views")
    
    
    
    

# Individual detail page for a compute node
@route("/node/<node>/")
@route("/node/<node>")
def show_node_page(node):
    # Did we get a proper node number?
    try:
        node = int(node)
        
    except ValueError:
        return "No such node: " + str(node)
    
    
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
        
        node_doc["state_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["state_time"]))
        
    except KeyError:
        return "Details missing for node " + str(node)
        
    
    
    # Make a pretty timestamp in the journal entries
    try:
        for entry in node_doc["journal"]:
            entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"]))
                                          
    except KeyError:
        node_doc["journal"] = []
        
    
    return bottle.template("node", node_doc=node_doc)





# Add a journal entry to a compute node
@post("/node/<node>/journal/")
@post("/node/<node>/journal")
def show_node_page(node):
    # Did we get a proper node number?
    try:
        node = int(node)
        
    except ValueError:
        return "No such node: " + str(node)
    
    entry = request.forms.get("entry")
    
    # Replace newlines and line feeds with HTML's <br>
    entry = entry.replace("\r\n", "<br>")
    
    db.compute.update(
        { "_id" : node },
        { "$push" : { "journal" : { "time" : time.time(), "entry" : entry } } }
    )


    
    return bottle.template("node_journal_success", node=node)

    
    
    
    
# Individual detail page for a head node
@route("/head/<head>/")
@route("/head/<head>")
def show_head_page(head):
    node_doc = db.head.find_one(
        {
            "_id" : head
        }
    )
    
    # Does the node exist?
    if node_doc is None:
        return "No such node"
    
    
    try:
        # Switch the processes to text rather than bool
        for process, value in node_doc["processes"].items():
            if value is True:
                node_doc["processes"][process] = "ok"
                
            else:
                node_doc["processes"][process] = "down"
                
                
        # Make things pretty...
        node_doc["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["last_check"]))
        
    except KeyError:
        return "Details missing for " + str(node)
    
    
    # Output a "pretty" string of node numbers (e.g. 0-4,20-24)
    def pretty_node_range(nodes):
        node_highest = sorted(nodes)[-1]
        new_node_chunk = True
        node_chunks = ""

        for num in xrange(0, 9999):
            # If we're already above the highest node number, stop
            if num > node_highest:
                break


            # Is the number one of the nodes?
            if num in nodes:
                if new_node_chunk == True:
                    new_node_chunk = False

                    if node_chunks == "":
                        node_chunks += str(num)

                    else:
                        node_chunks += "," + str(num)

                # Are we at the end of a chunk?
                elif num + 1 not in nodes:
                    node_chunks += "-" + str(num)

            # No?  Mark that the next node we find is the beginning of another chunk
            else:
                new_node_chunk = True

        return node_chunks
    
    
    # Switch the node lists into pretty strings
    node_doc["primary_of"] = pretty_node_range(node_doc["primary_of"])
    node_doc["secondary_of"] = pretty_node_range(node_doc["secondary_of"])
        
    
    
    #
    # Get any mismatched files
    #
    
    head0a_doc = db.head.find_one(
        {
            "_id" : "head0a"
        },
        {
            "file_hashes" : 1,
            "_id" : 0
        }
    )
    
    bad_files = []
    if head0a_doc is not None:
        for each_file in head0a_doc["file_hashes"]:
            try:
                if not head0a_doc["file_hashes"][each_file] == node_doc["file_hashes"][each_file]:
                    file_name_with_dots = re.sub(r"\[DOT\]", ".", each_file)
                    
                    bad_files.append(file_name_with_dots)
            
            except KeyError:
                pass
            
            

    # Do we have any zombies?        
    if node_doc.get("zombies") is None:
        node_doc["zombies"] = []
        
        
        
    # Make a pretty timestamp in the journal entries
    try:
        for entry in node_doc["journal"]:
            entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"]))
                                          
    except KeyError:
        node_doc["journal"] = []
    
    
    
    return bottle.template("head", node_doc=node_doc, bad_files=bad_files, zombies=node_doc["zombies"])





# Add a journal entry to a head node
@post("/head/<head>/journal/")
@post("/head/<head>/journal")
def show_head_page(head):
    entry = request.forms.get("entry")
    
    # Replace newlines and line feeds with HTML's <br>
    entry = entry.replace("\r\n", "<br>")
    
    db.head.update(
        { "_id" : head },
        { "$push" : { "journal" : { "time" : time.time(), "entry" : entry } } }
    )


    
    return bottle.template("head_journal_success", head=head)





# Individual detail page for a storage node
@route("/storage/<storage>/")
@route("/storage/<storage>")
def show_storage_page(storage):
    node_doc = db.storage.find_one(
        {
            "_id" : storage
        }
    )
    
    # Does the node exist?
    if node_doc is None:
        return "No such node"
    
    
    try:
        # Make things pretty...
        node_doc["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["last_check"]))
        
    except KeyError:
        return "Details missing for " + str(node)
    
    
    
    # Make a pretty timestamp in the journal entries
    try:
        for entry in node_doc["journal"]:
            entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"]))
                                          
    except KeyError:
        node_doc["journal"] = []
    
    
    
    return bottle.template("storage", node_doc=node_doc)





# Add a journal entry to a storage node
@post("/storage/<storage>/journal/")
@post("/storage/<storage>/journal")
def show_storage_page(storage):
    entry = request.forms.get("entry")
    
    # Replace newlines and line feeds with HTML's <br>
    entry = entry.replace("\r\n", "<br>")
    
    db.storage.update(
        { "_id" : storage },
        { "$push" : { "journal" : { "time" : time.time(), "entry" : entry } } }
    )


    
    return bottle.template("storage_journal_success", storage=storage)





@route("/")
def index():
    index_page = []
    
    locale.setlocale(locale.LC_ALL, 'en_US')
    
    # Main header
    index_page.append("""
    <html>
    <head>
        <title>Frank Cluster Status</title>
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">
        <script src="/static/jquery.min.js" type="text/javascript"></script>
    </head>
    <body>

    <div id="header" style="text-align:center; margin-left:auto; margin-right:auto;">
        <h2>Beomon</h2>
        <p>Node state (up, down, boot ...) is checked every 5 minutes.</p>
    </div>
    """)
    

    #
    # Summary tables
    #
    
    index_page.append("""
    <!-- Outer div to contain the summary tables -->
    <div id="summary_outer" style="text-align:center; margin-left:auto; margin-right:auto;display:block;width:500px;">
    """)
    
    
    #
    # Summary table: Compute summary
    #
    index_page.append("""
        <!-- Inner div containing the compute summary -->
        <div id="compute_summary" style="display:inline;float:left; width:45%;">
            <table>
                <thead>
                    <th colspan="2">Compute Summary</th>
                </thead>
                <tbody>
    """)
    
    index_page.append("""
    <tr>
        <td>Nodes Total</td>
        <td>""" + str(db.compute.count()) + """</td>
    </tr>
    """)
    
    
    index_page.append("""
    <tr>
        <td>Nodes Up</td>
        <td>""" + str(db.compute.find({ "state" : "up" }).count()) + """</td>
    </tr>
    """)
    
    
    index_page.append("    <tr><td>Nodes Down</td>\n")
    num_node_docs_down = db.compute.find({ "state" : "down" }).count()
    if num_node_docs_down == 0:
        index_page.append("        <td>0</td>\n    </tr>")
    else:
        index_page.append("        <td><span style='color:red'>" + str(num_node_docs_down) + "</td>\n    </tr>\n")
    
    
    index_page.append("    <tr><td>Nodes Error</td>\n")
    num_node_docs_error = db.compute.find({ "state" : "error" }).count()
    if num_node_docs_error == 0:
        index_page.append("        <td>0</td>\n    </tr>\n")
    else:
        index_page.append("        <td><span style='color:red'>" + str(num_node_docs_error) + "</td>\n    </tr>\n")
    
    
    index_page.append("    <tr>\n        <td>Nodes Booting</td>\n")
    num_node_docs_boot = db.compute.find({ "state" : "boot" }).count()
    if num_node_docs_boot == 0:
        index_page.append("        <td>0</td>\n    </tr>\n")
        
    else:
        index_page.append("        <td><span style='color:red'>" + str(num_node_docs_boot) + "</td>\n    </tr>\n")
        
    
    index_page.append("    <tr>\n        <td>Nodes Orphaned</td>\n")
    num_node_docs_orphan = db.compute.find({ "state" : "orphan" }).count()
    if num_node_docs_orphan == 0:
        index_page.append("        <td>0</td>\n    </tr>\n")
        
    else:
        index_page.append("        <td><span style='color:red'>" + str(num_node_docs_orphan) + "</td>\n    </tr>\n")
        
    
    cpu_total = 0
    for node_doc in db.compute.find({}, { "cpu" : 1}):
        try:
            cpu_total += node_doc["cpu"]["cpu_num"]
        
        except KeyError:
            pass

    index_page.append("    <tr>\n        <td>Total CPU Cores</td>\n")
    index_page.append("        <td>" + locale.format("%d", cpu_total, grouping=True) + "</td>\n    </tr>\n")
    
    
    gpu_cores_total = 0
    for node_doc in db.compute.find({}, { "gpu" : 1 }):
        try:
            gpu_cores_total += node_doc["gpu"]["num_cores"]
            
        except KeyError:
            pass
            
    index_page.append("    <tr>\n        <td>Total GPU Cores</td>\n")
    index_page.append("        <td>" + locale.format("%0.0f", gpu_cores_total, grouping=True) + "</td>\n    </tr>\n")
    
    
    ram_total = 0
    for node_doc in db.compute.find({}, { "ram" : 1 }):
        try:
            ram_total += node_doc["ram"]
            
        except KeyError:
            pass
            
    index_page.append("    <tr>\n        <td>Total System RAM</td>\n")
    index_page.append("        <td>" + locale.format("%0.2f", ram_total / float(1024), grouping=True) + " TB</td>\n    </tr>\n")
    
    
    gpu_ram_total = 0
    for node_doc in db.compute.find({}, { "gpu" : 1 }):
        try:
            gpu_ram_total += node_doc["gpu"]["ram_size"]
            
        except KeyError:
            pass
            
    index_page.append("    <tr>\n        <td>Total GPU RAM</td>\n")
    index_page.append("        <td>" + locale.format("%0.2f", gpu_ram_total, grouping=True) + " GB</td>\n    </tr>\n")
    
    
    scratch_total = 0
    for node_doc in db.compute.find().sort("_id", 1):
        try:
            scratch_total += node_doc["scratch_size"]
            
        except KeyError:
            pass
            
    index_page.append("    <tr>\n        <td>Total /scratch</td>\n")
    index_page.append("        <td>" + locale.format("%0.2f", scratch_total / float(1024), grouping=True) + " TB</td>\n    </tr>\n")
    
    
    # End of compute summary table
    index_page.append("""
                </tbody>
            </table>
        </div> <!-- compute_summary -->
    """)
    
    
    # Add space between the compute summary ad storage summary tables
    index_page.append("""
        <div id="summary_spacer" style="display:block;float:center; width:10%;">
        </div>
    """)
    
    
    
    #
    # Summary table: Storage summary
    #
    
    storage_totals = {
        "size" : 0,
        "used" : 0,
        "free" : 0,
    }
    
    
    index_page.append("""
        <!-- Inner div containing the storage summary -->
        <div id="storage_summary" style="display:inline;float:right; width:45%;">
            <table>
                <thead>
                    <tr>
                        <th colspan="3">Storage Summary</th>
                    </tr>
                    <tr>
                        <th>Mount</th>
                        <th>Size</th>
                        <th>% Used</th>
                </thead>
                <tbody>
    """)
    
    
    for mount_point in ["/home", "/home1", "/home2", "/gscratch1", "/gscratch2", "/pan", "/data/sam"]:
        if os.path.ismount(mount_point):
            fs_info = filesystem_info(mount_point)
            size_gb = round(float(fs_info[1]) / 1024 / 1024, 2)
            used_gb = round(float(fs_info[2]) / 1024 / 1024, 2)
            free_gb = round(float(fs_info[3]) / 1024 / 1024, 2)
            percent_used = fs_info[4]
            
            storage_totals["size"] += size_gb
            storage_totals["used"] += used_gb
            storage_totals["free"] += free_gb

            index_page.append("    <tr>\n        <td>" + mount_point + "</td>\n")
            
            index_page.append("        <td>" + str(round(size_gb / 1024, 2)) + " TB</td>\n")
            
            index_page.append("        <td style=\"text-align:center;\">" + percent_used + "</td>\n    </tr>\n")
            
        else:
            index_page.append("    <tr>\n        <td>" + mount_point + "</td>\n")
            index_page.append("        <td style=\"font-weight:bold;color:red;\">Unknown</td>\n")
            index_page.append("        <td style=\"font-weight:bold;color:red;\">Unknown</td>\n    </tr>\n")
            
    index_page.append("<tr><td style=\"text-align:center\">Total:</td>\n")
    index_page.append("<td>" + str(round(storage_totals["size"] / 1024, 2)) + " TB</td>\n")
    used_tb = storage_totals["used"] / 1024
    size_tb = storage_totals["size"] / 1024
    index_page.append("<td style=\"text-align:center;\">" + str(int(round(used_tb / size_tb * 100))) + "%</td></tr>")
                                                                          
        
        
    # End of storage summary table
    index_page.append("""
                </tbody>
            </table>
        </div> <!-- storage_summary -->
    """)
    
    
    # End of summary tables
    index_page.append("""
    </div> <!-- summary_outer -->
    """)
    
    
    
    #
    # Start of detail tables
    #
    index_page.append("""
    <!-- Outer div to contain the summary tables -->
    <div id="detail_outer" style="text-align:center; margin-left:auto; margin-right:auto;display:block;width:750px;clear:both;padding-top:25px;">
    """)
    
    
    
    #
    # Master node detail table
    #
    index_page.append("""
    <!-- Inner div containing the master node detail table -->
    <div id="master_detail" style="text-align:center; margin-left:auto; margin-right:auto; display:block;">
    <table id="master" style="text-align:center;">
        <thead>
            <tr>
                <th colspan="9">Master Node Details</th>
            </tr>
            <tr>
                <th scope="col">Node</th>
                <th scope="col">Processes</th>
                <th scope="col">Configs</th>
                <th scope="col">Load Average</th>
                <th scope="col">Nodes Up</th>
                <th scope="col">Nodes Down</th>
                <th scope="col">Nodes Error</th>
                <th scope="col">Nodes Booting</th>
                <th scope="col">Nodes Orphaned</th>
            </tr>
        </thead>
        <tbody>
    """)
    
    
    # Loop through each node in the DB
    for node_doc in db.head.find().sort("_id", 1):
        #
        # Node
        #
        
        index_page.append("<tr>\n<td><a href=\"/beomon/head/" + node_doc["_id"] +"\">" + node_doc["_id"] + "</a></td>\n")
        
        
        #
        # Processes
        #
        
        if "processes" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        else:
            processes_ok = True
            
            for process in node_doc["processes"]:
                if process is not True:
                    processes_ok == False
                    
            if processes_ok is True:
                index_page.append("<td>ok</td>\n")
            
            else:
                index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
                
                
        #
        # Configs
        #
        
        if "configs_ok" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        else:
            if node_doc["configs_ok"] is True:
                index_page.append("<td>ok</td>\n")
            
            else:
                index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
                
                
        #
        # Load average
        #
        index_page.append("<td>" + node_doc["loadavg"]["1"] + "<br>" + node_doc["loadavg"]["5"] + "<br>" + node_doc["loadavg"]["15"] + "</td>\n")
                
                
        #
        # Nodes state counts
        #
        
        index_page.append("<td>" + str(node_doc["num_state"]["up"]) + "</td>\n")
        index_page.append("<td>" + str(node_doc["num_state"]["down"]) + "</td>\n")
        index_page.append("<td>" + str(node_doc["num_state"]["error"]) + "</td>\n")
        index_page.append("<td>" + str(node_doc["num_state"]["boot"]) + "</td>\n")
        index_page.append("<td>" + str(node_doc["num_state"]["orphan"]) + "</td>\n")
    
    
    
    # End of master detail table
    index_page.append("""
        </tbody>
    </table>
    </div> <!-- master_detail -->
    """)
    
    
    
    
    
    #
    # Storage node detail table
    #
    index_page.append("""
    <!-- Inner div containing the storage node detail table -->
    <div id="storage_detail" style="text-align:center; margin-left:auto; margin-right:auto; display:block;padding-top:25px;">
    <table id="storage" style="text-align:center;">
        <thead>
            <tr>
                <th colspan="7">Storage Node Details</th>
            </tr>
            <tr>
                <th scope="col">Node</th>
                <th scope="col">Active Node?</th>
                <th scope="col">Filesystem Writable</th>
                <th scope="col">Load Average</th>
                <th scope="col">KB Read per Second (Last 10 Minutes)</th>
                <th scope="col">KB Written per Second (Last 10 Minutes)</th>
                <th scope="col">Transactions per Second (Last 10 Minutes)</th>
            </tr>
        </thead>
        <tbody>
    """)
    
    
    # Loop through each node in the DB
    for node_doc in db.storage.find().sort("_id", 1):
        #
        # Node
        #
        
        index_page.append("<tr>\n<td><a href=\"/beomon/storage/" + node_doc["_id"] +"\">" + node_doc["_id"] + "</a></td>\n")
        
        
        #
        # Active node?
        #
        if node_doc["active_node"] is True:
            index_page.append("<td>Yes</td>\n")
            
        else:
            index_page.append("<td>No</td>\n")
        
        
        #
        # Filesystem Writable
        #
        
        if "write_test" not in node_doc:
            index_page.append("<td style=\"font-weight:bold;color:red;\">unknown</td>\n")
            
        else:
            if node_doc["write_test"] is True:
                index_page.append("<td>ok</td>\n")
            
            else:
                index_page.append("<td style=\"font-weight:bold;color:red;\">down</td>\n")
                
                
        #
        # Load average
        #
        index_page.append("<td>" + node_doc["loadavg"]["1"] + "<br>" + node_doc["loadavg"]["5"] + "<br>" + node_doc["loadavg"]["15"] + "</td>\n")
        
        
        #
        # Disk IOPS
        #
        index_page.append("<td>" + str(node_doc["kilobytes_read_per_second"]) + "</td>")
        index_page.append("<td>" + str(node_doc["kilobytes_written_per_second"]) + "</td>")
        index_page.append("<td>" + str(node_doc["transactions_per_second"]) + "</td>")
                
                
    # End of storage detail table
    index_page.append("""
        </tbody>
    </table>
    </div> <!-- storage_detail -->
    """)
    




    #
    # Compute node detail table
    #

    # Compute node detail table header
    index_page.append("""
    <!-- Inner div containing the compute detail table -->
    <div id="compute_detail" style="text-align:center; margin-left:auto; margin-right:auto; display:block;padding-top:25px;">
    <table id="nodes" style="text-align:center;">
        <thead>
            <tr>
                <th colspan="6">Compute Node Details</th>
            </tr>
            <tr>
                <th scope="col">Node</th>
                <th scope="col">State</th>
                <th scope="col">PBS</th>
                <th scope="col">Moab</th>
                <th scope="col">Infiniband</th>
                <th scope="col">Filesystems</th>
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
            
            for _ in range(4): index_page.append("<td></td>")
            
            continue
        
        elif node_doc["state"] == "up":
            index_page.append("<td>up</td>\n")
            
        else:
            index_page.append("<td colspan='15'><span style='font-weight:bold;'>" + "In state '" + node_doc["state"] + "' since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(node_doc["state_time"])) + "</span></td>\n")
            
            continue
            
            
            
            
            
        #
        # Stale data?
        #
        
        try:
            if int(time.time()) - node_doc["last_check"] > 60 * 30:
                for _ in range(1): index_page.append("<td></td>\n")
                index_page.append("<td style=\"font-weight:bold;color:red;\">Stale data</td>\n")
                for _ in range(2): index_page.append("<td></td>\n")
                
                continue
        
        except KeyError:
            # We'll get here if the node never checked in but a master node added its rack location and state
            for _ in range(1): index_page.append("<td></td>\n")
            index_page.append("<td style=\"font-weight:bold;color:red;\">Missing data</td>\n")
            for _ in range(2): index_page.append("<td></td>\n")
            
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
        
        filesystems_all_good = True
        for filesystem, state in node_doc["filesystems"].items():
            if state is not True:
                filesystems_all_good = False
                
        if filesystems_all_good is True:
            index_page.append("<td>ok</td>\n")
            
        else:
            index_page.append("<td style=\"font-weight:bold;color:red;\">fail</td>\n")
            
            
            
        index_page.append("</tr>\n")
        
        
    # End of compute detail table
    index_page.append("""
        </tbody>
    </table>
    </div> <!-- compute_detail -->
    """)
    
    
        
    # End of detail tables
    index_page.append("""
    </div> <!-- detail_outer -->
    """)



    # Footer
    index_page.append("""
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