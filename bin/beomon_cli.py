#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon command line interface
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
import time
import ConfigParser
import locale
import traceback
from optparse import OptionParser



red = "\033[31m"
endcolor = '\033[0m' # end color
locale.setlocale(locale.LC_ALL, 'en_US')



# How were we called?
parser = OptionParser("%prog [options] [node1] [node2] ...\n" +
    "\nBeomon command line interface.\n" + \
    "This program displays the status of the cluster in plain text.  When ran \n" + \
    "with no arguements an overall status is printed.  With an arguement of a node \n" + \
    "name (e.g. 'head0a' or 'n17' or '17') the status of that node is printed."
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





# If we have no arguements, print an summary of the cluster status
if len(sys.argv) == 1:
    print "Total nodes: " + str(db.compute.count())



    print "Nodes up: " + str(db.compute.find({ "state" : "up" }).count())



    nodes_down = []

    for node in db.compute.find({ "state" : "down" }, { "_id" : 1} ):
        nodes_down.append(node["_id"])

    if len(nodes_down) == 0:
        print "Nodes down: 0"

    else:
        print "Nodes down: " + str(len(nodes_down)) + " " + str(sorted(nodes_down))



    nodes_orphan = []

    for node in db.compute.find({ "state" : "orphan" }, { "_id" : 1} ):
        nodes_orphan.append(node["_id"])

    if len(nodes_orphan) == 0:
        print "Nodes orphan: 0"

    else:
        print "Nodes orphan: " + str(len(nodes_orphan)) + " " + str(sorted(nodes_orphan))



    nodes_error = []

    for node in db.compute.find({ "state" : "error" }, { "_id" : 1} ):
        nodes_error.append(node["_id"])

    if len(nodes_error) == 0:
        print "Nodes error: 0"

    else:
        print "Nodes error: " + str(len(nodes_error)) + " " + str(sorted(nodes_error))



    nodes_boot = []

    for node in db.compute.find({ "state" : "boot" }, { "_id" : 1} ):
        nodes_boot.append(node["_id"])

    if len(nodes_boot) == 0:
        print "Nodes boot: 0"

    else:
        print "Nodes boot: " + str(len(nodes_boot)) + " " + str(sorted(nodes_boot))


    print ""



    cpu_total = 0
    for node_doc in db.compute.find( { "cpu" : { "$exists" : True} }, { "cpu" : 1} ):
        cpu_total += node_doc["cpu"]["cpu_num"]

    print "Total CPU Cores: " + locale.format("%d", cpu_total, grouping=True)



    gpu_cores_total = 0
    for node_doc in db.compute.find( { "gpu.num_cores" : { "$exists" : True} }, { "gpu" : 1 } ):
        gpu_cores_total += node_doc["gpu"]["num_cores"]

    print "Total GPU cores: " + locale.format("%d", gpu_cores_total, grouping=True)



    ram_total = 0
    for node_doc in db.compute.find( { "ram" : { "$exists" : True} }, { "ram" : 1 } ):
        ram_total += node_doc["ram"]

    print "Total System RAM: " + locale.format("%d", ram_total, grouping=True) + " GB"



    gpu_ram_total = 0
    for node_doc in db.compute.find( { "gpu.ram_size" : { "$exists" : True} }, { "gpu" : 1 } ):
        gpu_ram_total += node_doc["gpu"]["ram_size"]

    print "Total GPU RAM: " + locale.format("%d", gpu_ram_total, grouping=True) + " GB"


else: # Node status
    for node in sys.argv[1::]:
        print "-----     -----     -----"

        # If we were given n0 (or whatever number), convert it to just 0
        if re.search("^n\d+$", node) is not None:
            node = re.sub("^n", "", node)


        # Figure out which collection we will query and do the query
        if re.search("^\d+$", node) is not None:
            doc = db.compute.find_one(
                {
                    "_id" : int(node)
                }
            )
        else:
            doc = db.head.find_one(
                {
                    "_id" : node
                }
            )


        # Did the query work?
        if doc is None:
            print "No such node: " + node

            sys.exit(0)


        # Do we have a compute node or a head node?
        if re.search("^\d+$", node) is not None: # Compute node
            print "Node: " + node

            #
            # Print the health information
            #

            if doc["state"] == "up":
                print "State: " + doc["state"] + " (since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(doc["state_time"])) + ")"

            else:
                print red + "State: " + doc["state"] + " (since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(doc["state_time"])) + ")" + endcolor


            if doc["pbs"] is True:
                print "PBS: ok"

            else:
                print red + "PBS: fail" + endcolor


            if doc["moab"] is True:
                print "MOAB: ok"

            else:
                print red + "MOAB: fail" + endcolor


            if doc["infiniband"] is True:
                print "Infiniband: ok"

            else:
                print red + "Infiniband: fail" + endcolor


            filesystems_all_good = True
            for filesystem, state in doc["filesystems"].items():
                if state is not True:
                    filesystems_all_good = False

                    print red + filesystem + ": fail" + endcolor

            if filesystems_all_good is True:
                print "Filesystems: ok"


            print ""



            #
            # Print the basic information of the node
            #

            print "CPU:"
            print "     Type: " + doc["cpu"]["cpu_type"]
            print "     Cores: " + str(doc["cpu"]["cpu_num"])

            if doc["gpu"]["num_cards"] != 0:
                print "GPU:"
                print "     GPU Type: " + doc["gpu"]["gpu_type"]
                print "     Cards: " + str(doc["gpu"]["num_cards"])
                print "     Total RAM Size: " + str(doc["gpu"]["ram_size"]) + " GB"
                print "     Total GPU Cores: " + locale.format("%d", doc["gpu"]["num_cores"], grouping=True)

            print "IPs:"
            print "     GigE IP: " + doc["ip"]["gige"]
            print "     BMC IP: " + doc["ip"]["bmc"]
            print "     IB IP: " + doc["ip"]["ib"]

            print "RAM: " + str(doc["ram"]) + " GB"
            print "Scratch Size: " + locale.format("%d", doc["scratch_size"], grouping=True) + " GB"
            print "Rack: " + doc["rack"]
            print "Serial: " + doc["serial"]
            print "Last Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(doc["last_check"]))


            #
            # Print the node's journal
            #

            print "\nJournal:"

            if "journal" in doc and len(doc["journal"]) > 0:
                for entry in doc["journal"]:
                    print time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"])) + ":"
                    print re.sub("<br>", "\n", entry["entry"])
                    print "----------------------------------"

            else:
                print "No journal entries"



        else: # Head node
            print "Node: " + node

            #
            # Determine if the node is ok
            #

            processes_all_good = True
            for process, state in doc["processes"].items():
                if state is False:
                    processes_all_good = False

                    print red + "     " + process + ": fail"

            if processes_all_good is True:
                print "State: ok"

            else:
                print red + "State: fail" + endcolor


            # Display the load average
            print "Load average 1 minute: " + doc["loadavg"]["1"]
            print "Load average 5 minutes: " + doc["loadavg"]["5"]
            print "Load average 15 minutes: " + doc["loadavg"]["15"]


            #
            # Print the basic information of the node
            #

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
            doc["primary_of"] = pretty_node_range(doc["primary_of"])
            doc["secondary_of"] = pretty_node_range(doc["secondary_of"])


            print "Compute class: " + doc["compute_node_class"]
            print "Primary of: " + doc["primary_of"]
            print "Secondary of: " + doc["secondary_of"]
            print "Last check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(doc["last_check"]))


            #
            # Get any mismatched files
            #

            print ""

            head0a_doc = db.head.find_one(
                {
                    "_id" : "head0a"
                },
                {
                    "file_hashes" : 1,
                    "_id" : 0
                }
            )

            found_bad_files = False

            if head0a_doc is not None:
                for each_file in head0a_doc["file_hashes"]:
                    try:
                        if not head0a_doc["file_hashes"][each_file] == doc["file_hashes"][each_file]:
                            file_name_with_dots = re.sub(r"\[DOT\]", ".", each_file)

                            found_bad_files = True

                            print red + "     " + file_name_with_dots + " differs from head0a" + endcolor

                    except KeyError:
                        pass

            if found_bad_files is False:
                print "File mismatch check: ok"


            #
            # Print the node's journal
            #

            print "\nJournal:"

            if "journal" in doc and len(doc["journal"]) > 0:
                for entry in doc["journal"]:
                    print time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"])) + ":"
                    print re.sub("<br>", "\n", entry["entry"])
                    print "----------------------------------"

            else:
                print "No journal entries"
