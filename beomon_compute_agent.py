#!/opt/sam/python/2.6/gcc45/bin/python
# Description: Beomon compute node agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.4.3
# Last change: Switched compute node SQL table name to 'compute'

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



mysql_host = "clusman.frank.sam.pitt.edu"
ibv_devinfo = "/usr/bin/ibv_devinfo"
ipmitool = "/usr/bin/ipmitool"
lsmod = "/sbin/lsmod"
dmidecode = "/usr/sbin/dmidecode"



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, subprocess, time, syslog, signal
from MySQLdb import connect
from optparse import OptionParser
from multiprocessing import cpu_count



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon compute node agent.  This program will check the health of \n" + 
    "the node it is running on and update the Beomon database."
)

parser.add_option(
    "-d", "--daemonize",
    action="store_true", dest="daemonize", default=False,
    help="Become a background daemon"
)

(options, args) = parser.parse_args()



# Connect to the MySQL DB
def connect_mysql():
    # Returns a the db object
    
    # Get the DB password
    dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
    dbpass = dbpasshandle.read().rstrip()
    dbpasshandle.close()

        
        
    # Open a DB connection
    try:
        db = connect(
            host=mysql_host, user="beomon",
            passwd=dbpass, db="beomon"
        )
                                                
        return db
        
    except Exception as err:
        sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
        sys.exit(1)
        

        
# Query MySQL for a given column of a given node
def compute_query(cursor, column, node):
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



# Are we on a compute node?
hostname = os.uname()[1]

match = re.match("^n\d+", hostname)

if match is None:
    sys.stderr.write("Not a compute node, exiting.\n")
    sys.exit(1)

node = re.sub("^n", "", hostname)
        
        
        
##
## Run to completion
## 
        
def run_to_completion(db):
    cursor = db.cursor()
    
    # Add a row for the node if one does not exist.
    if cursor.execute("SELECT node_id FROM compute WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO compute (node_id) VALUES (" + node + ")")
    
        
    # Determine if we are an orphan
    if True:
        print "I have a master"
    
    else:
        sys.stderr.write("OH NO, I'M AN ORPHAN!\n")
        
        syslog.syslog(syslog.LOG_WARNING, "OH NO, I'M AN ORPHAN!")
        
        num_user_processes = 0
        
        # Check if we have any non-root and non-nscd processes
        for pid in os.listdir("/proc"):
            if not pid.isdigit(): continue
            
            try:
                with open("/proc/" + pid + "/status", "r") as proc_status_file:
                    for line in proc_status_file:
                        line = line.rstrip()

                        match = re.match("^Uid:\s+(\d+)", line)
            
                        if match:
                            uid = int(match.group(1))
                            
                            if (uid != 0 and uid != 28):
                                num_user_processes += 1
            except IOError:
                sys.stdout.write("Skipping PID " + str(pid) + "\n")
                 
                        
        cursor.execute("UPDATE compute SET last_check=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        if num_user_processes > 0:
            sys.stdout.write("It looks like I have a job running (" + str(num_user_processes) + " processes) ... Not rebooting myself\n")
            
        else:
            sys.stdout.write("No jobs appear to be running ... Rebooting myself NOW\n")
            
            syslog.syslog(syslog.LOG_WARNING, "No jobs appear to be running ... Rebooting myself NOW\n")
            
            sysrq_handle = open("/proc/sys/kernel/sysrq", "w")
            sysrq_handle.write("1")
            
            #sysrq_trigger = open("/proc/sysrq-trigger", "w")
            #sysrq_trigger.write("b")
        
        sys.exit(0)

        
    
#    
# Health checks    
#

# Add a row for the node if one does not exist.
def add_row(db):
    cursor = db.cursor()
    
    if cursor.execute("SELECT node_id FROM compute WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO compute (node_id) VALUES (" + node + ")")
            
        
        
# Moab
def check_moab(db):
    cursor = db.cursor()
    
    signal.alarm(30)
    
    try:
        with open(os.devnull, "w") as devnull:
            subprocess.check_call(["/bin/true"], stdin=None, stdout=devnull, stderr=devnull, shell=False)
            
        signal.alarm(0)
            
        sys.stdout.write("Moab: ok\n")
        
        cursor.execute("UPDATE compute SET moab='ok' WHERE node_id=" + node)
    
    except Alarm:
        sys.stdout.write("Moab: Timeout\n")
        
        cursor.execute("UPDATE compute SET moab=NULL WHERE node_id=" + node)
    
    except subprocess.CalledProcessError:
        sys.stdout.write("Moab: down\n")
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Moab in state 'down'")
        
        cursor.execute("UPDATE compute SET moab='down' WHERE node_id=" + node)
            
    except Exception as err:
        sys.stderr.write("Moab: sysfail (" + str(err) + ")\n")
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Moab in state 'sysfail'")
        
        cursor.execute("UPDATE compute SET moab='sysfail' WHERE node_id=" + node)

        
        
# Infiniband
def infiniband_check(db):
    cursor = db.cursor()
    
    # Which nodes to skip
    ib_skip_ranges = [(4,11), (40,52), (59,66), (242,242), (283,284)]
    
    if any(lower <= int(node) <= upper for (lower, upper) in ib_skip_ranges):
        sys.stdout.write("Infiniband: n/a\n") 
        
        cursor.execute("UPDATE compute SET infiniband='n/a' WHERE node_id=" + node)
        
    else:
        signal.alarm(30)
        
        try:
            with open(os.devnull, "w") as devnull:
                ib_info = subprocess.Popen([ibv_devinfo], stdin=None, stdout=subprocess.PIPE, stderr=devnull)
                out = ib_info.communicate()[0]
                
                signal.alarm(0)
                
                match = re.search("state:\s+PORT_ACTIVE", out)

                if match:
                    sys.stdout.write("Infiniband: ok\n")
            
                    cursor.execute("UPDATE compute SET infiniband='ok' WHERE node_id=" + node)
            
                else:
                    sys.stdout.write("Infiniband: down\n")
                    
                    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Infiniband in state down")
            
                    cursor.execute("UPDATE compute SET infiniband='down' WHERE node_id=" + node)
        
        except Alarm:
            sys.stdout.write("Infiniband: Timeout\n")
            
            cursor.execute("UPDATE compute SET infiniband=NULL WHERE node_id=" + node)
            
        except Exception as err:
            sys.stderr.write("Infiniband: sysfail (" + str(err) + ")")
            
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Infiniband in state sysfail")
            
            cursor.execute("UPDATE compute SET infiniband='sysfail' WHERE node_id=" + node)
            

        
# Tempurature
def check_tempurature(db):
    cursor = db.cursor()

    try:
        sensor_name = ""
        temp = False
        
        # Figure out which sensor name to use
        if any(lower <= int(node) <= upper for (lower, upper) in [(0,16), (170,176)]):
            sensor_name = "System Temp"
        
        elif any(lower <= int(node) <= upper for (lower, upper) in [(177,241)]):
            sensor_name = "Ambient Temp"
            
        elif any(lower <= int(node) <= upper for (lower, upper) in [(242,242), (283,284)]):
            sensor_name = "CPU0 Temp"
            
        elif any(lower <= int(node) <= upper for (lower, upper) in [(243,324)]):
            sensor_name = "CPU0_Temp"
            
        else:
            sys.stdout.write("Tempurature: n/a\n")
            
            cursor.execute("UPDATE compute SET tempurature='n/a' WHERE node_id=" + node)
        #sensor_name = "CPU 1 Temp"

        signal.alarm(30)
        
        with open(os.devnull, "w") as devnull:
            info = subprocess.Popen([ipmitool + " sensor get '" + sensor_name + "'"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=True)
            out = info.communicate()[0]
            
            signal.alarm(0)
            
            for line in out.split(os.linesep):
                line = line.rstrip()
                
                sensor_match = re.match("^\s+Sensor Reading\s+:\s+(\d+)", line)
                
                if sensor_match:
                    temp = sensor_match.group(1)
                    
                    sys.stdout.write("Tempurature: " + temp + "C (" + sensor_name + ")\n")
                    
                    cursor.execute("UPDATE compute SET tempurature='" + temp + "C (" + sensor_name + ")' WHERE node_id=" + node)
                    
                    break
                
                else:
                    continue
                
            # If we couldn't find a temp...
            if not temp:
                sys.stdout.write("Tempurature: unknown\n")
        
                cursor.execute("UPDATE compute SET tempurature='unknown' WHERE node_id=" + node)

    except Alarm:
        sys.stdout.write("Tempurature: Timeout")
        
        cursor.execute("UPDATE compute SET tempurature=NULL WHERE node_id=" + node)
        
    except Exception as err:
        sys.stderr.write("Tempurature: sysfail (" + str(err) + ")")
        
        cursor.execute("UPDATE compute SET tempurature='sysfail' WHERE node_id=" + node)
        

        
# /scratch
def check_scratch(db):
    cursor = db.cursor()

    scratch_size = int()

    if os.path.ismount("/scratch") is True:
        sys.stdout.write("/scratch: ok\n")
        
        cursor.execute("UPDATE compute SET scratch='ok' WHERE node_id=" + node)
            
        st = os.stat("/scratch")
        
        scratch_size = round(float(os.statvfs("/scratch")[2] * st.st_blksize) / 1024 / 1024 / 1024, 2)
        
        cursor.execute("UPDATE compute SET scratch_size=" + str(scratch_size) + " WHERE node_id=" + node)
        
    else:
        sys.stdout.write("/scratch: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has /scratch in state failed")
        
        cursor.execute("UPDATE compute SET scratch='failed' WHERE node_id=" + node)    



# Filesystems check
def check_filesystems(db):
    cursor = db.cursor()
    
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
        if os.path.ismount(mount_point) is True:
            sys.stdout.write(mount_point + ": ok\n")
            
            cursor.execute("UPDATE compute SET " + filesystems[mount_point] + "='ok' WHERE node_id=" + node)

        else:
            sys.stdout.write(mount_point + ": failed\n")
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has " + mount_point + " in state failed")
            
            cursor.execute("UPDATE compute SET " + filesystems[mount_point] + "='failed' WHERE node_id=" + node)
        
        
        
# Hyperthreading check
def check_hyperthreading():
    # Skip Interlagos nodes
    if any(lower <= int(node) <= upper for (lower, upper) in [(325,378)]):
        sys.stdout.write("Hyperthreading: n/a\n")
        
    else:
        proc_info_file = open("/proc/cpuinfo", "r")

        num_cpu_cores = cpu_count()

        for line in proc_info_file:
            line = line.rstrip()
            
            if re.search("^siblings", line) is not None:
                num_siblings = line.split()[2]
                
            elif re.search("^cpu cores", line) is not None:
                num_cores = line.split()[3]
                
                break
                
        proc_info_file.close()
                
                
        num_siblings = int(num_siblings)
        num_cores = int(num_cores)


        if num_cores == num_siblings:
            sys.stdout.write("Hyperthreading: OK (disabled)\n")
            
        else:
            sys.stdout.write("Hyperthreading: Error (enabled)\n")
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has hyperthreading enabled")
        
        
        
#    
# General node info
#    
        
# CPU model
def get_cpu_model(db):
    cursor = db.cursor()
    
    proc_info_file = open("/proc/cpuinfo", "r")

    for line in proc_info_file:
        line = line.rstrip()
        
        model_match = re.match("^model name\s+:\s+(.*)$", line)
        
        if model_match:
            cpu_type = re.sub("\s+", " ", model_match.group(1))
            
            sys.stdout.write("CPU Type: " + cpu_type + "\n")
            
            cursor.execute("UPDATE compute SET cpu_type='" + cpu_type + "' WHERE node_id=" + node)
            
            break

    proc_info_file.close()



# Number of CPU cores
def get_cpu_count(db):
    cursor = db.cursor()    
    
    num_cpu_cores = cpu_count()
    
    sys.stdout.write("CPU Cores: " + str(num_cpu_cores) + "\n")

    cursor.execute("UPDATE compute SET cpu_num=" + str(num_cpu_cores) + " WHERE node_id=" + node)
        
        
        
# RAM amount
def get_ram_amount(db):
    cursor = db.cursor()
    
    ram_amount = int()

    mem_info_file = open("/proc/meminfo", "r")

    for line in mem_info_file:
        line = line.rstrip()

        mem_match = re.match("^MemTotal:\s+(\d+)", line)
        
        if mem_match:
            ram_amount = int(mem_match.group(1))
            
            break

    ram_amount = round(float(ram_amount) / 1024 / 1024, 2)
            
    sys.stdout.write("RAM: " + str(ram_amount) + " GB\n")

    cursor.execute("UPDATE compute SET ram=" + str(ram_amount) + " WHERE node_id=" + node)

        
        
# /scratch size we found earlier
def show_scratch_size(db):
    cursor = db.cursor()
    
    scratch_size = compute_query(cursor, "scratch_size", node)
    
    sys.stdout.write("/scratch Size: " + str(scratch_size) + " GB\n")
        
        
        
# GPU
def get_gpu_info(db):
    cursor = db.cursor()
    
    signal.alarm(30)
    
    gpu = False
    try:
        with open(os.devnull, "w") as devnull:
            info = subprocess.Popen([lsmod], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
            out = info.communicate()[0]
            
            signal.alarm(0)
            
            for line in out.split(os.linesep):
                line = line.rstrip()
                
                match = re.search("^nvidia", line)
                
                if match:
                    gpu = True
                    
                    sys.stdout.write("GPU?: 1\n")
                    cursor.execute("UPDATE compute SET gpu=1 WHERE node_id=" + node)
                    
                    break
                
                else:
                    continue
                
            if not gpu == True:
                sys.stdout.write("GPU?: 0\n")
                
                cursor.execute("UPDATE compute SET gpu=0 WHERE node_id=" + node)
    
    except Alarm:
        sys.stdout.write("Failed to check for GPU, process timed out.\n")
        
    except Exception as err:
        sys.stderr.write("Failed to check for GPU, process failed: " + str(err))
            
        

# Serial number
def get_seral_number(db):
    cursor = db.cursor()
    
    signal.alarm(30)
    
    try:
        with open(os.devnull, "w") as devnull:
            info = subprocess.Popen([dmidecode, "-s", "system-serial-number"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
            out = info.communicate()[0]
            
            signal.alarm(0)
            
            out = out.rstrip()
            
            if out:
                serial = out
                
            else:
                serial = "unknown"
                
            sys.stdout.write("Serial: " + serial + "\n")
            
            cursor.execute("UPDATE compute SET serial='" + serial + "' WHERE node_id=" + node)

    except Alarm:
        sys.stdout.write("Failed to get serial number, process timed out.\n")
        
    except Exception as err:
        sys.stderr.write("Failed to get serial number, process failed: " + str(err))
        
        
        
##    
## Daemonizer
##



if options.daemonize == False:
    db = connect_mysql()
    
    add_row(db)
    check_moab(db)
    infiniband_check(db)
    #check_tempurature(db)
    check_scratch(db)
    check_filesystems(db)
    check_hyperthreading()
    get_cpu_model(db)
    get_cpu_count(db)
    get_ram_amount(db)
    show_scratch_size(db)
    get_gpu_info(db)
    get_seral_number(db)
    
    
    # Report that we've now checked ourself
    cursor = db.cursor()
    cursor.execute("UPDATE compute SET last_check=" + str(int(time.time())) + " WHERE node_id=" + node)
    
    
    # Close the DB, we're done
    syslog.closelog()
    db.close()
    
else:
    # Check if our PID or lock files already exist
    if os.path.exists("/var/lock/subsys/beomon_compute_agent") and not os.path.exists("/var/run/bemon_compute_agent.pid"):
        sys.stderr.write("PID file not found but subsys locked\n")
        sys.exit(1)
        
    elif os.path.exists("/var/lock/subsys/beomon_compute_agent") or os.path.exists("/var/run/beomon_compute_agent.pid"):
        sys.stderr.write("Existing PID or lock file found (/var/lock/subsys/beomon_compute_agent or " + 
        "/var/run/beomon_compute_agent.pid), already running?  Exiting.\n")
        sys.exit(1)
        
    
    # Set STDOUT and STDIN to /dev/null
    dev_null = open(os.devnull, "w")
    
    os.dup2(dev_null.fileno(), 0) # STDIN
    os.dup2(dev_null.fileno(), 1) # STDOUT

    # Set STDERR to a log file
    log_file = open("/opt/sam/beomon/log/" + node + ".log", "a")
    os.dup2(log_file.fileno(), 2) # STDERR
    
    
    # Fork time!
    os.chdir("/")
    
    pid = os.fork()
    
    if not pid == 0:
        sys.exit(0)
    
    os.setsid()
    
    
    # Create our lock and PID files
    lockfile_handle = open("/var/lock/subsys/beomon_compute_agent", "w")
    lockfile_handle.close()
    
    pidfile_handle = open("/var/run/beomon_compute_agent.pid", "w")
    pidfile_handle.write(str(os.getpid()) + "\n")
    pidfile_handle.close()
    
    
    # If we get a SIGINT or SIGTERM, clean up after ourselves and exit
    def signal_handler(signal, frame):
        sys.stderr.write("Caught signal, exiting.\n")
        
        try:
            os.remove("/var/run/beomon_compute_agent.pid")
        except:
            pass
        
        try:
            os.remove("/var/lock/subsys/beomon_compute_agent")
        except:
            pass
        
        try:
            syslog.closelog()
        except:
            pass
        
        try:
            log_file.close()
        except:
            pass
        
        try:
            db.close()
        except:
            pass
        
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    
    # Connect to the DB and get the initial info
    db = connect_mysql()

    add_row(db)
    check_moab(db)
    #check_tempurature(db)
    check_scratch(db)
    check_filesystems(db)
    check_hyperthreading()
    get_cpu_model(db)
    get_cpu_count(db)
    get_ram_amount(db)
    show_scratch_size(db)
    get_gpu_info(db)
    get_seral_number(db)

    # Give IB time to come up
    time.sleep(30)
    
    # Keep checking in and make sure IB is up
    while True:
        cursor = db.cursor()
        
        infiniband_check(db)
        
        # Report that we've now checked ourself
        cursor.execute("UPDATE compute SET last_check=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        # Sleep for 5 minutes, if we wake with time left go back to sleep.
        wake_time = int(time.time()) + 300

        while int(time.time()) < wake_time:
            time.sleep(30)
    