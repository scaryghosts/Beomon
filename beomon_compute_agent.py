#!/opt/sam/python/2.7.5/gcc447/bin/python
# Description: Beomon compute node agent
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 2
# Last change: Switched from MySQL to MongoDB, added IPs and rack ID, added GPU info

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys, os, re, pymongo, subprocess, time, syslog, signal
from optparse import OptionParser
from multiprocessing import cpu_count
from string import ascii_lowercase



mongo_host = "clusman.frank.sam.pitt.edu"
ibv_devinfo = "/usr/bin/ibv_devinfo"
ipmitool = "/usr/bin/ipmitool"
lsmod = "/sbin/lsmod"
dmidecode = "/usr/sbin/dmidecode"
deviceQuery = "/opt/sam/cuda/4.0/cuda/bin/deviceQuery"
new_compute_data = {}
red = "\033[31m"
endcolor = '\033[0m'



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



# Connect to the DB
def connect_mongo():
    # Returns the db object
    
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
                                                
        return db
        
    except Exception as err:
        sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
        sys.exit(1)
        
        
        
# Update the compute collection
def update_compute_collection(my_compute_data):
    db.compute.update(
        {
            "_id" : node
        },
        {
            "$set" : my_compute_data
        },
        upsert = True,
    )
    

        
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

node = int(node)
        


        
    
#    
# Health checks    
#
        
# Moab
def check_moab(db):
    signal.alarm(30)
    
    try:
        with open(os.devnull, "w") as devnull:
            subprocess.check_call(["/bin/true"], stdin=None, stdout=devnull, stderr=devnull, shell=False)
            
        signal.alarm(0)
            
        sys.stdout.write("Moab: ok\n")
        
        new_compute_data["moab"] = True
        
    except Alarm:
        sys.stdout.write("Moab: Timeout\n")
        
        new_compute_data["moab"] = False
        
    except subprocess.CalledProcessError:
        sys.stdout.write(red + "Moab: down\n" + endcolor)
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Moab in state 'down'")
        
        new_compute_data["moab"] = False
            
    except Exception as err:
        sys.stderr.write(red + "Moab: sysfail (" + str(err) + ")\n" + endcolor)
        
        syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Moab in state 'sysfail'")
        
        new_compute_data["moab"] = False
        
        

        
        
# Infiniband
def infiniband_check(db):
    # Which nodes to skip
    ib_skip_ranges = [(4,11), (40,52), (59,66), (242,242), (283,284)]
    
    if any(lower <= int(node) <= upper for (lower, upper) in ib_skip_ranges):
        sys.stdout.write("Infiniband: n/a\n")
        
        new_compute_data["infiniband"] = True
        
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
                    
                    new_compute_data["infiniband"] = True
                    
                else:
                    sys.stdout.write(red + "Infiniband: down\n" + endcolor)
                    
                    syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Infiniband in state down")
            
                    new_compute_data["infiniband"] = False
            
        except Alarm:
            sys.stdout.write(red + "Infiniband: Timeout\n" + endcolor)
            
            new_compute_data["infiniband"] = "timeout"
            
        except Exception as err:
            sys.stderr.write(red + "Infiniband: sysfail (" + str(err) + ")" + endcolor)
            
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has Infiniband in state sysfail")
            
            new_compute_data["infiniband"] = False
            
            


            
# Tempurature
def check_tempurature(db):
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
            
            new_compute_data["tempurature"] = True

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
                    
                    new_compute_data["tempurature"] = temp + "C (" + sensor_name + ")"
                    
                    break
                
                else:
                    continue
                
            # If we couldn't find a temp...
            if not temp:
                sys.stdout.write("Tempurature: unknown\n")
                
                new_compute_data["tempurature"] = "unknown"
                
    except Alarm:
        sys.stdout.write("Tempurature: Timeout")
        
        new_compute_data["tempurature"] = "timeout"
        
    except Exception as err:
        sys.stderr.write("Tempurature: sysfail (" + str(err) + ")")
        
        new_compute_data["tempurature"] = False
        


        
        
# Filesystems check
def check_filesystems(db):
    filesystems = {
        "/data/pkg" : "datapkg",
        "/data/sam" : "datasam",
        "/gscratch1" : "gscratch1",
        "/home" : "home0",
        "/home1" : "home1",
        "/home2" : "home2",
        "/pan" : "panasas",
        "/scratch" : "scratch",
    }
    
    sys.stdout.write("Filesystems:\n")

    
    for mount_point in sorted(filesystems.iterkeys()):
        if os.path.ismount(mount_point) is True:
            sys.stdout.write("     " + mount_point + ": ok\n")
            
            new_compute_data["filesystems." + filesystems[mount_point]] = True
            
        else:
            sys.stdout.write(red + "     " + mount_point + ": failed\n" + endcolor)
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has " + mount_point + " in state failed")
            
            new_compute_data["filesystems." + filesystems[mount_point]] = False
            
        
        
        
        
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
            sys.stdout.write("Hyperthreading: ok (disabled)\n")
            
        else:
            sys.stdout.write(red + "Hyperthreading: Error (enabled)\n" + endcolor)
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has hyperthreading enabled")
        
        
        
        
        
#    
# General node info
#    
        
# CPU info
def get_cpu_info(db):
    # Number of cores
    num_cpu_cores = cpu_count()
    
    new_compute_data["cpu.cpu_num"] = num_cpu_cores
    
    # CPU type
    proc_info_file = open("/proc/cpuinfo", "r")

    for line in proc_info_file:
        line = line.rstrip()
        
        model_match = re.match("^model name\s+:\s+(.*)$", line)
        
        if model_match:
            cpu_type = re.sub("\s+", " ", model_match.group(1))
            
            new_compute_data["cpu.cpu_type"] = cpu_type
            
            break

    proc_info_file.close()
    
    # Hyperthreading info
    # Skip Interlagos nodes
    if any(lower <= int(node) <= upper for (lower, upper) in [(325,378)]):
        sys.stdout.write("Hyperthreading: n/a\n")
        
        new_compute_data["cpu.hyperthreading"] = False
        
    else:
        proc_info_file = open("/proc/cpuinfo", "r")

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
            new_compute_data["cpu.hyperthreading"] = False
            
        else:
            syslog.syslog(syslog.LOG_ERR, "NOC-NETCOOL-TICKET: Node " + str(node) + " has hyperthreading enabled")
            
            new_compute_data["cpu.hyperthreading"] = True
    
    
    
    sys.stdout.write("CPU:\n")
    sys.stdout.write("     CPU Type: " + cpu_type + "\n")
    sys.stdout.write("     CPU Cores: " + str(num_cpu_cores) + "\n")
    if new_compute_data["cpu.hyperthreading"] is False:
        sys.stdout.write("     Hyperthreading: ok (disabled)\n")
        
    else:
        sys.stdout.write(red + "     Hyperthreading: Error (enabled)\n" + endcolor)



        
        
# RAM amount
def get_ram_amount(db):
    ram_amount = int()

    signal.alarm(30)
    
    try:
        with open(os.devnull, "w") as devnull:
            info = subprocess.Popen([dmidecode, "--type", "memory"], stdin=None, stdout=subprocess.PIPE, stderr=devnull, shell=False)
            out = info.communicate()[0]
            
            signal.alarm(0)
            
            out = out.rstrip()
            
            for dimm in re.findall("Size:\s+(\d+)", out):
                ram_amount = ram_amount + int(dimm)
                
    except Alarm:
        sys.stdout.write("Failed to get RAM amount, process timed out.\n")
        
    except Exception as err:
        sys.stderr.write("Failed to get RAM amount, process failed: " + str(err))
        
        
    if ram_amount != 0:
        sys.stdout.write("RAM: " + str(ram_amount / 1024) + " GB\n")
        
        new_compute_data["ram"] = ram_amount / 1024
        
        
        
        
        
# /scratch size
def scratch_size(db):
    scratch_size = int()
    
    for drive_letter in ascii_lowercase:
        # Stop if we have no more drives to look at
        if not os.path.isfile("/sys/block/sd" + drive_letter + "/size"):
            break
            
        with open("/sys/block/sd" + drive_letter + "/size", "r") as drive_size_file_handle:
            drive_size = drive_size_file_handle.read()
            
            drive_size = (int(drive_size) * 512) / 1000 / 1000 / 1000
            
            scratch_size = scratch_size + drive_size
            
            
    sys.stdout.write("/scratch Size: " + str(scratch_size) + " GB\n")
    
    new_compute_data["scratch_size"] = scratch_size
    
    
    
        
        
# GPU
def get_gpu_info(db):
    signal.alarm(30)

    try:
        with open(os.devnull, "w") as devnull:
            # Add a library path deviceQuery needs
            try:
                os.environ['LD_LIBRARY_PATH'] += ":/opt/sam/cuda/4.0/cuda/lib64"
                
            except KeyError:
                os.environ['LD_LIBRARY_PATH'] = ":/opt/sam/cuda/4.0/cuda/lib64"
                
            info = subprocess.Popen([deviceQuery], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=devnull, shell=True)
            out = info.communicate("\n")[0]
            
            signal.alarm(0)
            
            gpu_info = {}
            
            for line in out.split(os.linesep):
                line = line.rstrip()
                
                # If we don't have a GPU, say so and stop looking
                if re.search("^cudaGetDeviceCount FAILED", line) is not None:
                    sys.stdout.write("GPU:\n")
                    sys.stdout.write("     Cards: 0\n")
                    
                    gpu_info["num_cards"] = 0
                    
                    new_compute_data["gpu"] = False
                    
                    break
                    
                # How many cards do we have?
                if re.search("There are (\d+) devices supporting CUDA", line) is not None:
                    gpu_info["num_cards"] = int(line.split()[2])
                    
                    continue
                    
                # How much memory do we have?
                if re.search("^\s+Total amount of global memory:\s+(\d+) bytes", line) is not None:
                    gpu_info["ram_size"] = int(round((float(line.split()[5]) / 1024.0 / 1024.0 / 1024.0) * gpu_info["num_cards"], 0))
                    
                    continue
                
                # How many GPU core do we have?
                if re.search("^\s+Number of cores:\s+(\d+)", line) is not None:
                    gpu_info["num_cores"] = int(line.split()[3]) * gpu_info["num_cards"]
                    
                    break
                
                
            # Done, print and note our GPU info if we have any
            if gpu_info["num_cards"] != 0:
                sys.stdout.write("GPU:\n")
                sys.stdout.write("     Cards: " + str(gpu_info["num_cards"]) + "\n")
                sys.stdout.write("     Total RAM Size: " + str(gpu_info["ram_size"]) + " GB\n")
                sys.stdout.write("     Total GPU Cores: " + str(gpu_info["num_cores"]) + "\n")
            
            new_compute_data["gpu"] = gpu_info
                    
    except Alarm:
        sys.stdout.write(red + "Failed to check for GPU, process timed out.\n" + endcolor)
        
    except Exception as err:
        sys.stderr.write(red + "Failed to check for GPU, process failed: " + str(err) + endcolor)
            
        

        
        
# Serial number
def get_seral_number(db):
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
            
            new_compute_data["serial"] = serial
            
    except Alarm:
        sys.stdout.write(red + "Failed to get serial number, process timed out.\n" + endcolor)
        
    except Exception as err:
        sys.stderr.write(red + "Failed to get serial number, process failed: " + str(err) + endcolor)
        
        
        
        
        
# IP addresses
def get_ip_addresses(db):
    sys.stdout.write("IPs:\n")
    
    if node < 256:
        sys.stdout.write("     GigE: 10.201.1." + str(node) + "\n")
        sys.stdout.write("     BMC: 10.202.1." + str(node) + "\n")
        sys.stdout.write("     IB: 10.203.1." + str(node) + "\n")
        
        new_compute_data["ip.gige"] = "10.201.1." + str(node)
        new_compute_data["ip.bmc"] = "10.202.1." + str(node)
        new_compute_data["ip.ib"] = "10.203.1." + str(node)
        
    elif node > 255:
        sys.stdout.write("     GigE: 10.201.2." + str(node - 256) + "\n")
        sys.stdout.write("     BMC: 10.202.2." + str(node - 256) + "\n")
        sys.stdout.write("     IB: 10.203.2." + str(node - 256) + "\n")
        
        new_compute_data["ip.gige"] = "10.201.2." + str(node - 256)
        new_compute_data["ip.bmc"] = "10.202.2." + str(node - 256)
        new_compute_data["ip.ib"] = "10.203.2." + str(node - 256)
        

        
        
        
# Rack ID
def note_rack_id(db):
    if node in range(0, 4):
        sys.stdout.write("Rack: C-0-2\n")
        
        new_compute_data["rack"] = "C-0-2"
        
        
    if node in range(4, 14):
        sys.stdout.write("Rack: C-0-4\n")
        
        new_compute_data["rack"] = "C-0-4"
        
        
    if node in range(14, 53):
        sys.stdout.write("Rack: C-0-3\n")
        
        new_compute_data["rack"] = "C-0-3"
        
        
    if node in range(53, 59):
        sys.stdout.write("Rack: C-0-4\n")
        
        new_compute_data["rack"] = "C-0-4"
        
        
    if node in range(59, 113):
        sys.stdout.write("Rack: C-0-20\n")
        
        new_compute_data["rack"] = "C-0-20"
        
        
    if node in range(113, 173):
        sys.stdout.write("Rack: C-0-19\n")
        
        new_compute_data["rack"] = "C-0-19"
        
        
    if node in range(173, 177):
        sys.stdout.write("Rack: C-0-20\n")
        
        new_compute_data["rack"] = "C-0-20"
        
        
    if node in range(177, 211):
        sys.stdout.write("Rack: C-0-18\n")
        
        new_compute_data["rack"] = "C-0-18"
        
        
    if node in range(211, 242):
        sys.stdout.write("Rack: C-0-17\n")
        
        new_compute_data["rack"] = "C-0-17"

    if node == 242:
        sys.stdout.write("Rack: C-0-2\n")
        
        new_compute_data["rack"] = "C-0-2"
        
        
    if node in range(243, 284):
        sys.stdout.write("Rack: C-0-21\n")
        
        new_compute_data["rack"] = "C-0-21"
        
        
    if node in range(284, 325):
        sys.stdout.write("Rack: C-0-22\n")
        
        new_compute_data["rack"] = "C-0-22"
        
        
    if node in range(325, 351):
        sys.stdout.write("Rack: C-0-23\n")
        
        new_compute_data["rack"] = "C-0-23"
        
        
    if node in range(351, 379):
        sys.stdout.write("Rack: C-0-24\n")
        
        new_compute_data["rack"] = "C-0-24"

        
        

        
##    
## Daemonizer
##



if options.daemonize == False:
    db = connect_mongo()
    
    check_moab(db)
    infiniband_check(db)
    #check_tempurature(db)
    check_filesystems(db)
    get_cpu_info(db)
    get_gpu_info(db)
    get_ip_addresses(db)
    get_ram_amount(db)
    scratch_size(db)
    note_rack_id(db)
    get_seral_number(db)
    
    
    # Report that we've now checked ourself
    new_compute_data["last_check"] = int(time.time())
    
    # Update the compute collection
    update_compute_collection(new_compute_data)
    
    # Close syslog, we're done
    syslog.closelog()
    
else:
    # Check if our PID or lock files already exist
    if os.path.exists("/var/lock/subsys/beomon_compute_agent") and not os.path.exists("/var/run/beomon_compute_agent.pid"):
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
    log_file = open("/opt/sam/beomon/log/" + str(node) + ".log", "a")
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
    db = connect_mongo()

    check_moab(db)
    #check_tempurature(db)
    check_filesystems(db)
    get_cpu_info(db)
    get_gpu_info(db)
    get_ip_addresses(db)
    get_ram_amount(db)
    scratch_size(db)
    note_rack_id(db)
    get_seral_number(db)

    # Give IB time to come up
    time.sleep(30)
    
    # Keep checking in and make sure IB is up
    while True:
        infiniband_check(db)
        
        # Report that we've now checked ourself
        new_compute_data["last_check"] = int(time.time())
        
        # Update the compute collection
        update_compute_collection(new_compute_data)
        
        # Sleep for 5 minutes
        time.sleep(60 * 5)
    