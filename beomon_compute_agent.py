#!/opt/sam/python/2.6/gcc45/bin/python
# Description: Beomon compute node agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.0.1
# Last change: Added additional mount points to check

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, MySQLdb, subprocess, time, syslog
from optparse import OptionParser



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
        db = MySQLdb.connect(
            host="clusman0-dev.francis.sam.pitt.edu", user="beomon",
            passwd=dbpass, db="beomon"
        )
                                                
        return db
        
    except MySQLError as err:
        sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
        sys.exit(1)
        

        
# Query MySQL for a given column of a given node
def do_sql_query(cursor, column, node):
    cursor.execute("SELECT " + column + " FROM beomon WHERE node_id=" + node)
    
    results = cursor.fetchone()
    
    return results[0]
            

            
# Prepare syslog
syslog.openlog(os.path.basename(sys.argv[0]), syslog.LOG_NOWAIT, syslog.LOG_DAEMON)



# Are we on a compute node?
hostname = os.uname()[1]

match = re.match("n\d+", hostname)

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
    if cursor.execute("SELECT node_id FROM beomon WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO beomon (node_id) VALUES (" + node + ")")
    
        
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
                 
                        
        cursor.execute("UPDATE beomon SET last_check=" + str(int(time.time())) + " WHERE node_id=" + node)
        
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
            
def check_health(db):
    cursor = db.cursor()
    
    # Add a row for the node if one does not exist.
    if cursor.execute("SELECT node_id FROM beomon WHERE node_id=" + node) == 0:
        cursor.execute("INSERT INTO beomon (node_id) VALUES (" + node + ")")
            
    # Moab
    try: 
        with open(os.devnull, "w") as devnull:
            subprocess.check_call(["/bin/true"], stdin=None, stdout=devnull, stderr=devnull, shell=False)
            
        sys.stdout.write("Moab: ok\n")
        
        cursor.execute("UPDATE beomon SET moab='ok' WHERE node_id=" + node)
        
    except subprocess.CalledProcessError:
        sys.stdout.write("Moab: down\n")
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has Moab in state 'down'")
        
        cursor.execute("UPDATE beomon SET moab='down' WHERE node_id=" + node)
            
    except OSError:
        sys.stdout.write("Moab: sysfail\n")
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has Moab in state 'sysfail'")
        
        cursor.execute("UPDATE beomon SET moab='sysfail' WHERE node_id=" + node)

        
        
    # Infiniband
    # Which nodes to skip
    ib_skip_ranges = [(4,11), (40,52), (59,66), (242,242), (283,284)]

    if any(lower <= int(node) <= upper for (lower, upper) in ib_skip_ranges):
        sys.stdout.write("Infiniband: n/a\n") 
        
        cursor.execute("UPDATE beomon SET infiniband='n/a' WHERE node_id=" + node)
        
    else:
        try: 
            with open(os.devnull, "w") as devnull:
                ib_info = subprocess.Popen(["/usr/bin/ibv_devinfo"], stdin=None, stdout=subprocess.PIPE, stderr=devnull)
                out = ib_info.communicate()[0]
                
                # Get the last state
                last_state = do_sql_query(cursor, "infiniband", node)
                
                match = re.match("state:\s+PORT_ACTIVE", out)

                if match is None:
                    sys.stdout.write("Infiniband: down\n")
                    
                    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has Infiniband in state down")
            
                    cursor.execute("UPDATE beomon SET infiniband='down' WHERE node_id=" + node)
            
                else:
                    sys.stdout.write("Infiniband: ok\n")
            
                    cursor.execute("UPDATE beomon SET infiniband='ok' WHERE node_id=" + node)
            
        except subprocess.CalledProcessError and OSError:
            sys.stdout.write("Infiniband: sysfail\n")
            
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has Infiniband in state sysfail")
            
            # Get the last state
            last_state = do_sql_query(cursor, "infiniband", node)
            
            cursor.execute("UPDATE beomon SET infiniband='sysfail' WHERE node_id=" + node)
            

        
    ## Tempurature
    #try:
        #sensor_name = ""
        #temp = False
        
        ## Figure out which sensor name to use
        #if any(lower <= int(node) <= upper for (lower, upper) in [(0,16), (170,176)]):
            #sensor_name = "System Temp"
        
        #elif any(lower <= int(node) <= upper for (lower, upper) in [(177,241)]):
            #sensor_name = "Ambient Temp"
            
        #elif any(lower <= int(node) <= upper for (lower, upper) in [(242,242), (283,284)]):
            #sensor_name = "CPU0 Temp"
            
        #elif any(lower <= int(node) <= upper for (lower, upper) in [(243,324)]):
            #sensor_name = "CPU0_Temp"
            
        #else:
            #sys.stdout.write("Tempurature: n/a\n")
            
            #cursor.execute("UPDATE beomon SET tempurature='n/a' WHERE node_id=" + node)
        ##sensor_name = "CPU 1 Temp"

        #with open(os.devnull, "w") as devnull:
            #info = subprocess.Popen(["/usr/bin/ipmitool sensor get '" + sensor_name + "'"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=True)
            #out = info.communicate()[0]
            
            #for line in out.split(os.linesep):
                #line = line.rstrip()
                
                #sensor_match = re.match("^\s+Sensor Reading\s+:\s+(\d+)", line)
                
                #if sensor_match:
                    #temp = sensor_match.group(1)
                    
                    #sys.stdout.write("Tempurature: " + temp + "C (" + sensor_name + ")\n")
                    
                    #cursor.execute("UPDATE beomon SET tempurature='" + temp + "C (" + sensor_name + ")' WHERE node_id=" + node)
                    
                    #break
                
                #else:
                    #continue
                
            ## If we couldn't find a temp...
            #if not temp:
                #sys.stdout.write("Tempurature: unknown\n")
        
                #cursor.execute("UPDATE beomon SET tempurature='unknown' WHERE node_id=" + node)

        
    #except subprocess.CalledProcessError and OSError:
        #sys.stdout.write("Tempurature: sysfail\n")
        
        #cursor.execute("UPDATE beomon SET tempurature='sysfail' WHERE node_id=" + node)
        

        
    # /scratch
    scratch_size = int()
    last_state = do_sql_query(cursor, "scratch", node)

    if os.path.ismount("/scratch") is True:
        sys.stdout.write("/scratch: ok\n")
        
        cursor.execute("UPDATE beomon SET scratch='ok' WHERE node_id=" + node)
            
        st = os.stat("/scratch")
        
        scratch_size = round(float(os.statvfs("/scratch")[2] * st.st_blksize) / 1024 / 1024 / 1024, 2)
        
        cursor.execute("UPDATE beomon SET scratch_size=" + str(scratch_size) + " WHERE node_id=" + node)
        
    else:
        sys.stdout.write("/scratch: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /scratch in state failed")
        
        cursor.execute("UPDATE beomon SET scratch='failed' WHERE node_id=" + node)    



    # /pan
    if os.path.ismount("/pan") is True:
        sys.stdout.write("/pan: ok\n")
        
        cursor.execute("UPDATE beomon SET panasas='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/pan: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /pan in state failed")
        
        cursor.execute("UPDATE beomon SET panasas='failed' WHERE node_id=" + node)    
        
        
        
    # /home
    if os.path.ismount("/home") is True:
        sys.stdout.write("/home: ok\n")
        
        cursor.execute("UPDATE beomon SET home='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/home: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /home in state failed")
        
        cursor.execute("UPDATE beomon SET home='failed' WHERE node_id=" + node)



    # /home1
    if os.path.ismount("/home1") is True:
        sys.stdout.write("/home1: ok\n")
        
        cursor.execute("UPDATE beomon SET home1='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/home1: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /home1 in state failed")
     
        cursor.execute("UPDATE beomon SET home1='failed' WHERE node_id=" + node)



    # /home2
    if os.path.ismount("/home2") is True:
        sys.stdout.write("/home2: ok\n")
        
        cursor.execute("UPDATE beomon SET home2='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/home2: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /home2 in state failed")
        
        cursor.execute("UPDATE beomon SET home2='failed' WHERE node_id=" + node)


        
    # /gscratch0
    if os.path.ismount("/gscratch0") is True:
        sys.stdout.write("/gscratch0: ok\n")
        
        cursor.execute("UPDATE beomon SET gscratch0='ok' WHERE node_id=" + node)
    else:
        sys.stdout.write("/gscratch0: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /gscratch0 in state failed")
        
        cursor.execute("UPDATE beomon SET gscratch0='failed' WHERE node_id=" + node)
            
            
            
    # /gscratch1
    if os.path.ismount("/gscratch1") == True:
        sys.stdout.write("/gscratch1: ok\n")
        
        cursor.execute("UPDATE beomon SET gscratch1='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/gscratch1: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /gscratch1 in state failed")
        
        cursor.execute("UPDATE beomon SET gscratch1='failed' WHERE node_id=" + node)



    # /data/sam
    if os.path.ismount("/data/sam") == True:
        sys.stdout.write("/data/sam: ok\n")
        
        cursor.execute("UPDATE beomon SET datasam='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/data/sam: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /data/sam in state failed")
        
        cursor.execute("UPDATE beomon SET datasam='failed' WHERE node_id=" + node)



    # /data/pkg
    if os.path.ismount("/data/pkg") == True:
        sys.stdout.write("/data/pkg: ok\n")
        
        cursor.execute("UPDATE beomon SET datapkg='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/data/pkg: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /data/pkg in state failed")
        
        cursor.execute("UPDATE beomon SET datapkg='failed' WHERE node_id=" + node)

        
        
        # /lchong/home
    if os.path.ismount("/lchong/home") is True:
        sys.stdout.write("/lchong/home: ok\n")
        
        cursor.execute("UPDATE beomon SET lchong_home='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/lchong/home: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /lchong/home in state failed")
        
        cursor.execute("UPDATE beomon SET lchong_home='failed' WHERE node_id=" + node)
        
        
      
    # /lchong/archive
    if os.path.ismount("/lchong/archive") is True:
        sys.stdout.write("/lchong/archive: ok\n")
        
        cursor.execute("UPDATE beomon SET lchong_archive='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/lchong/archive: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /lchong/archive in state failed")
        
        cursor.execute("UPDATE beomon SET lchong_archive='failed' WHERE node_id=" + node)
        
        
        
    # /lchong/work
    if os.path.ismount("/lchong/work") is True:
        sys.stdout.write("/lchong/work: ok\n")
        
        cursor.execute("UPDATE beomon SET lchong_work='ok' WHERE node_id=" + node)

    else:
        sys.stdout.write("/lchong/work: failed\n")
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + node + " has /lchong/work in state failed")
        
        cursor.execute("UPDATE beomon SET lchong_work='failed' WHERE node_id=" + node)
        
        
        
    #    
    # General node info
    #    
        
    # CPU model
    proc_info_file = open("/proc/cpuinfo", "r")

    for line in proc_info_file:
        line = line.rstrip()
        
        model_match = re.match("^model name\s+:\s+(.*)$", line)
        
        if model_match:
            cpu_type = model_match.group(1)
            
            sys.stdout.write("CPU Type: " + cpu_type + "\n")
            
            cursor.execute("UPDATE beomon SET cpu_type='" + cpu_type + "' WHERE node_id=" + node)
            
            break

    proc_info_file.close()



    # Number of CPU cores
    num_physical_cpus = int()
    cpu_cores = int()

    proc_info_file = open("/proc/cpuinfo", "r")

    for line in proc_info_file:
        line = line.rstrip()
        
        phys_match = re.match("^physical id\s+:\s+(\d+)$", line)
        
        if phys_match:
            phys_id = phys_match.group(1)
            
            if int(phys_id) > num_physical_cpus:
                num_physical_cpus = int(phys_id)
                
        core_match = re.match("^cpu cores\s+:\s+(\d+)$", line)
        
        if core_match:
            cpu_cores = int(core_match.group(1))

    num_physical_cpus += 1

    cpu_cores = cpu_cores * num_physical_cpus

    sys.stdout.write("CPU Cores: " + str(cpu_cores) + "\n")

    cursor.execute("UPDATE beomon SET cpu_num=" + str(cpu_cores) + " WHERE node_id=" + node)

    proc_info_file.close()
        
        
        
    # RAM amount
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

    cursor.execute("UPDATE beomon SET ram=" + str(ram_amount) + " WHERE node_id=" + node)

        
        
    # /scratch size we found earlier
    sys.stdout.write("/scratch Size: " + str(scratch_size) + " GB\n")
        
        
        
    # GPU
    gpu = False
    with open(os.devnull, "w") as devnull:
        info = subprocess.Popen(["/sbin/lsmod"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
        out = info.communicate()[0]
        
        for line in out.split(os.linesep):
            line = line.rstrip()
            
            match = re.match("^nvidia", line)
            
            if match:
                gpu = True
                
                sys.stdout.write("GPU?: 1\n")
                cursor.execute("UPDATE beomon SET gpu=1 WHERE node_id=" + node)
                
                break
            
            else:
                continue
            
        if not gpu == True:
            sys.stdout.write("GPU?: 0\n")
            
            cursor.execute("UPDATE beomon SET gpu=0 WHERE node_id=" + node)
            
        
            
    # IB?
    if do_sql_query(cursor, "infiniband", node) == "n/a":
        sys.stdout.write("IB?: 0\n")
        
    else:
        sys.stdout.write("IB?: 1\n")

            

    # Serial number
    with open(os.devnull, "w") as devnull:
        info = subprocess.Popen(["/usr/sbin/dmidecode", "-s", "system-serial-number"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
        out = info.communicate()[0]
        
        out = out.rstrip()
        
        if out:
            serial = out
            
        else:
            serial = "unknown"
            
        sys.stdout.write("Serial: " + serial + "\n")
        
        cursor.execute("UPDATE beomon SET serial='" + serial + "' WHERE node_id=" + node)

        
        
##    
## Daemonizer
##



if options.daemonize == False:
    db = connect_mysql()
    
    # Call check_health(db) to do the real work
    check_health(db)
    
else:
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
    
    db = connect_mysql()

    # Only run check_health() once then next time just report that we're still alive
    check_health(db)
    
    while True:
        # Report that we've now checked ourself
        cursor = db.cursor()
        cursor.execute("UPDATE beomon SET last_check=" + str(int(time.time())) + " WHERE node_id=" + node)
        
        # Sleep for 5 minutes, if we wake with time left go back to sleep.
        wake_time = int(time.time()) + 300

        while int(time.time()) < wake_time:
            time.sleep(30)
    
    
    
# Close the DB, we're done
syslog.closelog()
db.close()