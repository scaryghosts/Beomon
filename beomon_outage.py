#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Show when compute nodes were down
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1
# Last change: Initial version

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys, os, pymongo, time
from optparse import OptionParser



mongo_host = "clusman.frank.sam.pitt.edu"
red = "\033[31m"
endcolor = '\033[0m' # end color



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Show when compute nodes were down.\n" + 
    "If no node is specified, all nodes will be displayed"
)


parser.add_option(
    "-d", "--daily",
    action="store_true", dest="daily", default=False,
    help="Show outages only from the past 24 hours"
)


parser.add_option(
    "-w", "--weekly",
    action="store_true", dest="weekly", default=False,
    help="Show outages only from the past 7 days"
)


parser.add_option(
    "-n", "--node", dest="specific_node",
    help="Only show outages of NODE", metavar="NODE"
)


(options, args) = parser.parse_args()


if options.specific_node is not None:
    try:
        options.specific_node = int(options.specific_node)
        
    except ValueError:
        sys.stderr.write(red + "Invalid node specified: " + specific_node + "\n" + endcolor)
        sys.exit(1)

    


    
# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip()
dbpasshandle.close()

    
    
# Open a DB connection
try:
    mongo_client = pymongo.MongoClient(mongo_host)

    db = mongo_client.beomon
    
    db.authenticate("beomon", dbpass)
    
    del(dbpass)
    
except Exception as err:
    sys.stderr.write(red + "Failed to connect to the Beomon database: " + str(err) + "\n" + endcolor)
    sys.exit(1)
    
    
    
    
    
# Should we get details on just one node or all of them?
if options.specific_node is None:
    range_low = 0
    range_high = 379
    
else:
    range_low = options.specific_node
    range_high = options.specific_node + 1    
    
    
    
for node in xrange(range_low, range_high):
    node = int(node)
    
    
    # Skip dead nodes
    if node in [191, 199, 203, 226, 229, 241, 241]:
        continue
    

    # Get the down and up times
    node_db_info = db.compute.find_one(
        {
            "_id" : node
        },
        {
            "down_times" : 1,
            "up_times" : 1,
            "_id" : 0,
        }
    )


    # Catch things that didn't exist in the document
    if node_db_info is None:
        sys.stderr.write("    " + red + "No such node found: " + str(node) + endcolor + "\n")
        
        continue
        

    down_times = node_db_info.get("down_times")
    up_times = node_db_info.get("up_times")
            

    if down_times is None and up_times is None:
        continue
    
    
    sys.stdout.write("\nOutage details for node " + str(node) + ":\n")


    while True:
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
            
            
            
        # Handle the daily and weekly options
        if options.daily is True:
            if min_down is not None and time.time() - min_down > (60 * 60 * 24):
                down_times.remove(min_down)
                min_down = None
                
            if min_up is not None and time.time() - min_up > (60 * 60 * 24):
                up_times.remove(min_up)
                min_up = None
                
        elif options.weekly is True:
            if min_down is not None and time.time() - min_down > (60 * 60 * 24 * 7):
                down_times.remove(min_down)
                min_down = None
                
            if min_up is not None and time.time() - min_up > (60 * 60 * 24 * 7):
                up_times.remove(min_up)
                min_up = None
            
            
            
        # Do we have anything to look at this iteration?
        if min_down is None and min_up is None:
            continue
        
        
        
        # Print the down time
        if min_down is None:
            sys.stdout.write("\n    " + "Down: Unknown\n")
        
        elif min_up is None:
            sys.stdout.write("\n    " + "Down: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_down)) + "\n")
            down_times.remove(min_down)
        
        elif min_down < min_up:
            sys.stdout.write("\n    " + "Down: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_down)) + "\n")
            down_times.remove(min_down)
            
        else:
            sys.stdout.write("\n    " + "Down: Unknown\n")
            
            
            
        # Print the up time
        if min_up is None:
            sys.stdout.write("    " + "Up: Unknown\n")
        
        elif min_down is None:
            sys.stdout.write("    " + "Up: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_up)) + "\n")
            up_times.remove(min_up)
        
        elif min_down < min_up:
            sys.stdout.write("    " + "Up: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min_up)) + "\n")
            up_times.remove(min_up)
            
        else:
            sys.stdout.write("    " + "Up: Unknown\n")
            
            
            
        # Print the outage duration
        if min_down is not None and min_up is not None and min_down < min_up:
            diff = min_up - min_down
            
            days = diff / (60 * 60 * 24)
            
            remaining_seconds = diff - days
            
            sys.stdout.write("    Outage: " + str(days) + ":" + time.strftime('%H:%M:%S', time.gmtime(remaining_seconds)) + "\n")
            
            
