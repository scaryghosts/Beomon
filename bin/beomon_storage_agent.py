#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon storage agent
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
import signal
import ConfigParser
import traceback
import datetime
from optparse import OptionParser



red = "\033[31m"
endcolor = '\033[0m' # end color



# How were we called?
parser = OptionParser("%prog [options] [nodes ...]\n" +
    "Beomon storage agent.  This program will check the status of \n" +
    "the local storage server and update the Beomon database.\n"
)

(options, args) = parser.parse_args()





# Print a stack trace, exception, and an error string to STDERR
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
storage_config = dict(config.items(hostname.split(".")[0]))



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
# Check our health and performance
#

old_storage_data = db.storage.find_one(
    {
        "_id" : hostname.split(".")[0]
    }
)

if old_storage_data is None:
    old_storage_data = {}

new_storage_data = {}



#
# Note our basic information
#

new_storage_data["active_node"] = config.getboolean(hostname.split(".")[0], "active_node")
new_storage_data["data_device"] = storage_config["data_device"]
new_storage_data["data_mount"] = storage_config["data_mount"]
new_storage_data["client_mount"] = storage_config["client_mount"]
new_storage_data["description"] = storage_config["description"].strip('"')





#
# Is our device mounted?
#

if os.path.ismount(storage_config["data_mount"]):
    new_storage_data["data_device_mounted"] = True

else:
    new_storage_data["data_device_mounted"] = False

    # Update the storage collection
    db.storage.update(
        {
            "_id" : hostname.split(".")[0]
        },
        {
            "$set" : new_storage_data
        },
        upsert = True,
    )

    fatal_error("Data device " + storage_config["data_device"] + " is not mounted at " + storage_config["data_mount"])





#
# Get the current load average
#

load_avg_data = open("/proc/loadavg", "r").read()
new_storage_data["loadavg"] = {}
new_storage_data["loadavg"]["1"] = load_avg_data.split()[0]
new_storage_data["loadavg"]["5"] = load_avg_data.split()[1]
new_storage_data["loadavg"]["15"] = load_avg_data.split()[2]

print "Load average:"
print "    1 minute: " + new_storage_data["loadavg"]["1"]
print "    5 minutes: " + new_storage_data["loadavg"]["5"]
print "    15 minutes: " + new_storage_data["loadavg"]["15"]





##
## Get the NFS statistics
##

#print "NFS IOP statistics:"
#new_storage_data["nfs_stats"] = {}

## If we don't have previous statistics to compare to in the DB, just get the total statistics
#if "nfs_stats" in old_storage_data:
    ## Make a file of the previous NFS stats
    #prev_nfs_stats_file = "/tmp/beomon_storage_agent-previous_nfs_data." + str(os.getpid())
    #prev_nfs_stats_handle = open(prev_nfs_stats_file, "w")

    #for stat, value in old_storage_data["nfs_stats"].iteritems():
        #prev_nfs_stats_handle.write("nfs v3 server    " + stat + ":    " + value + "\n")

    #prev_nfs_stats_handle.close()

    #signal.alarm(30)

    #try:
        #with open(os.devnull, "w") as devnull:
            #info = subprocess.Popen(["/usr/sbin/nfsstat", "--server", "-3", "--list", "--since", prev_nfs_stats_file], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
            #out = info.communicate()[0]

            #signal.alarm(0)

            #for line in out.split(os.linesep):
                #line = line.rstrip("\n")

                #if line == "------------- ------------- --------" or line == "":
                    #continue

                #split_line = line.split()

                #value = split_line.pop()

                #stat = split_line.pop().rstrip(":")

                #new_storage_data["nfs_stats"][stat] = value

                #print "    " + stat + ": " + value

    #except Alarm:
        #sys.stderr.write("Failed to get NFS IOP statistics, process timed out.\n")

    #except:
        #fatal_error("Failed to get NFS IOP statistics", None)

    ##finally:
        ##os.remove(prev_nfs_stats_file)


#else:
    #signal.alarm(30)

    #try:
        #with open(os.devnull, "w") as devnull:
            #info = subprocess.Popen(["/usr/sbin/nfsstat", "--server", "-3", "--list"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
            #out = info.communicate()[0]

            #signal.alarm(0)

            #for line in out.split(os.linesep):
                #line = line.rstrip("\n")

                #if line == "------------- ------------- --------" or line == "":
                    #continue

                #split_line = line.split()

                #value = split_line.pop()

                #stat = split_line.pop().rstrip(":")

                #new_storage_data["nfs_stats"][stat] = value

                #print "    " + stat + ": " + value

    #except Alarm:
        #sys.stderr.write("Failed to get NFS IOP statistics, process timed out.\n")

    #except:
        #fatal_error("Failed to get NFS IOP statistics", None)





#
# Disk transfers per second
#

signal.alarm(30)

try:
    with open(os.devnull, "w") as devnull:
        info = subprocess.Popen(["/usr/bin/sar", "-d", "-p"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
        out = info.communicate()[0]

        signal.alarm(0)

        blocks_read_per_second = 0
        blocks_written_per_second = 0

        for line in out.split(os.linesep):
            line = line.rstrip("\n")

            # When we reach the "average" lines, stop
            if re.search("^Average", line) is not None:
                break

            line_split = line.split()

            # If the line has less than two elements, it's not what were looking for so we don't care about it
            if len(line_split) >= 2:
                try:
                    blocks_written_per_second = float(line_split[6])
                    blocks_read_per_second = float(line_split[5])
                    transactions_per_second = float(line_split[5])

                except ValueError, IndexError: # If it can't be converted to a float, we don't care about it anyway
                    pass


        # Convert blocks per second to KB per second
        bytes_read_per_second = blocks_read_per_second * 512
        kilobytes_read_per_second = round(bytes_read_per_second / float(1024), 2)

        bytes_written_per_second = blocks_written_per_second * 512
        kilobytes_written_per_second = round(bytes_written_per_second / float(1024), 2)


        print "KB/s read (last 10 minutes): " + str(kilobytes_read_per_second)
        print "KB/s written (last 10 minutes): " + str(kilobytes_written_per_second)
        print "Transactions/s (last 10 minutes): " + str(transactions_per_second)

        new_storage_data["kilobytes_read_per_second"] = kilobytes_read_per_second
        new_storage_data["kilobytes_written_per_second"] = kilobytes_written_per_second
        new_storage_data["transactions_per_second"] = transactions_per_second

except Alarm:
    sys.stderr.write("Failed to get disk IOP statistics, process timed out.\n")

except:
    fatal_error("Failed to get disk IOP statistics", None)





#
# Verify the filesystem is still writable
#

sys.stdout.write("Filesystem write test: ")
sys.stdout.flush()

# Spawn a watchdog process that will time out and throw an alert if we hang too long/forever
watchdog_pid = os.fork()

if watchdog_pid == 0: # Child
    os.setsid()

    # Set an alarm for 5 minutes
    signal.alarm(60 * 5)

    slept_for = 0

    while True:
        try:
            time.sleep(1)

            slept_for += 1

            if slept_for % 5 == 0:
                log_self("Filesystem-write-test watchdog agent has waited " + str(slept_for) + " seconds so far")

        except Alarm:
            if config.getboolean(hostname.split(".")[0], "active_node") is True:
                syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: Beomon storage agent watchdog process detected hang during filesystem write test of PRIMARY/ACTIVE node.  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") unwritable?  Do manual write test, see KB.")

                fatal_error("Beomon storage agent watchdog process detected a hang during filesystem write test of PRIMARY/ACTIVE node.  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") unwritable?  Do manual filesystem write test, see KB.", None)

            else:
                syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Beomon storage agent watchdog process detected hang during filesystem write test of SECONDARY/INACTIVE node.  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") unwritable?  Do manual write test, see KB.")

                fatal_error("Beomon storage agent watchdog process detected a hang during filesystem write test of SECONDARY/INACTIVE node.  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") unwritable?  Do manual filesystem write test, see KB.", None)

            new_storage_data["write_test"] = False

            # Update the storage collection
            db.storage.update(
                {
                    "_id" : hostname.split(".")[0]
                },
                {
                    "$set" : new_storage_data
                },
                upsert = True,
            )

            sys.exit(0)


else: # Parent
    write_test_file = storage_config["data_mount"] + "/beomon_storage_agent-write_test_file." + str(os.getpid())

    try:
        # Open the test file and write a byte to it then close it
        write_test_handle = open(write_test_file, "w")
        write_test_handle.write("1")
        write_test_handle.close()

        # Re-open the test file and ensure our last write worked
        write_test_handle = open(write_test_file, "r")
        write_test_data = write_test_handle.read()
        write_test_handle.close()

        os.remove(write_test_file)

        # Does the read data match what we wrote?
        if write_test_data == "1":
            log_self("Filesystem write test: success")
            print "ok"

            new_storage_data["write_test"] = True

        else:
            if config.getboolean(hostname.split(".")[0], "active_node") is True:
                syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: Beomon storage agent write test failed of PRIMARY/ACTIVE node (read data does not match written data).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.")

                fatal_error("Beomon storage agent write test failed of PRIMARY/ACTIVE node (read data does not match written data).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.", None)

            else:
                syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Beomon storage agent write test failed of PRIMARY/ACTIVE node (read data does not match written data).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.")

                fatal_error("Beomon storage agent write test failed of PRIMARY/ACTIVE node (read data does not match written data).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.", None)

            new_storage_data["write_test"] = False

    except IOError:
        if config.getboolean(hostname.split(".")[0], "active_node") is True:
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-ALERT: Beomon storage agent write test failed of PRIMARY/ACTIVE node (IOError exception thrown).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.")

            fatal_error("Beomon storage agent write test failed of PRIMARY/ACTIVE node (IOError exception thrown).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.", None)

        else:
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Beomon storage agent write test failed of PRIMARY/ACTIVE node (IOError exception thrown).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.")

            fatal_error("Beomon storage agent write test failed of PRIMARY/ACTIVE node (IOError exception thrown).  Filesystem " + storage_config["data_mount"] + " (client mount: " + storage_config["client_mount"] + ") corrupted?  Do manual write test, see KB.", None)

        new_storage_data["write_test"] = False

    finally:
        # Get rid of our watchdog process
        os.kill(watchdog_pid, 15) # SIGTERM





# Report that we've now checked ourself
new_storage_data["last_check"] = int(time.time())



# Update the storage collection
db.storage.update(
    {
        "_id" : hostname.split(".")[0]
    },
    {
        "$set" : new_storage_data
    },
    upsert = True,
)



log_self("- - - Run completed - - -")



# Close the DB and logs, we're done with them
syslog.closelog()
log_file_handle.close()
mongo_client.close()
