#!/usr/bin/env python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.2.2
# Last change: Added whitespace after the table so the pop up info box doesn't go below the page, 
# added a warning about using IE

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, re, MySQLdb, time
from optparse import OptionParser



nodes = ""



# How were we called?
parser = OptionParser("%prog [options]\n" + 
    "Beomon status viewer.  This CGI program will display the status of compute nodes."
)

(options, args) = parser.parse_args()



# Query MySQL for a given column of a given node
def do_sql_query(column, node):
    cursor.execute("SELECT " + column + " FROM beomon WHERE node_id=" + node)
        
    results = cursor.fetchone()
        
    return results[0]
            
            

# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")
dbpass = dbpasshandle.read().rstrip("\n")
dbpasshandle.close()

    
    
# Open a DB connection
try:
    db = MySQLdb.connect(
        host="clusman0-dev.francis.sam.pitt.edu", user="beomon",
        passwd=dbpass, db="beomon"
    )
                                             
    cursor = db.cursor()
    
except Exception as err:
    sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
    sys.exit(1)
    


# Header 
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

    <center>
        <h2>Beomon</h2>
        <p>Node state (up, down, boot ...) is checked every 5 minutes.</p>
    </center>
<table id="nodes" summary="Node status" class="tablesorter">
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
            <th scope="col">/lchong/home</th>
            <th scope="col">/lchong/archive</th>
            <th scope="col">/lchong/work</th>
            <th scope="col">/pan</th>
        </tr>
    </thead>
    <tbody>
""")



# Loop through each node in the DB
cursor.execute("SELECT node_id FROM beomon")

nodes = cursor.fetchall()

for node in nodes:
    node = str(node[0])
    
    
    sys.stdout.write("<tr>\n<td><span align='left' class='dropt'>" + node + "<span>\n")
    
    
    cpu_type = do_sql_query("cpu_type", node)
    if cpu_type: sys.stdout.write("CPU Type: " + cpu_type + "<br>")
    
    
    cpu_num = do_sql_query("cpu_num", node)
    if cpu_num: sys.stdout.write("Number of CPUs: " + str(cpu_num) + "<br>")
    
    
    ram = do_sql_query("ram", node)
    if ram: sys.stdout.write("RAM: " + str(ram) + " GB<br>")
    
    
    scratch_size = do_sql_query("scratch_size", node)
    if scratch_size: sys.stdout.write("Scratch Size: " + str(scratch_size) + " GB<br>")
    
    
    ib     = do_sql_query("infiniband", node)
    if ib == "n/a":
        sys.stdout.write("Infiniband?: No" + "<br>")
        
    elif ib:
        sys.stdout.write("Infiniband?: Yes" + "<br>")
    
    
    gpu = do_sql_query("gpu", node)
    #sys.stdout.write("GPU?: " + gpu + "<br>")
    if gpu == 0:
        sys.stdout.write("GPU?: No" + "<br>")
        
    elif gpu == 1:
        sys.stdout.write("GPU?: Yes" + "<br>")
    
    
    last_check = do_sql_query("last_check", node)
    if last_check: sys.stdout.write("Last Node Check-in: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check)) + "<br>")
    
    
    sys.stdout.write("</span></span></td>\n")
    
    
    
    # State
    state = do_sql_query("state", node)
    if state == None:
        sys.stdout.write("<td><span style='color:red'><span>unknown</span></span></td>\n")
        
        print "<td></td>" * 14
        
        continue
        
    elif state == "up":
        sys.stdout.write("<td>up\n")
        
    else:
        state_time = do_sql_query("state_time", node)
        
        sys.stdout.write("<td><span style='color:red' class='dropt'>" + state + "<span>Since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state_time)) + "</span></span></td>\n")
        
        print "<td></td>" * 14
        
        continue
        
        
        
    # PBS
    pbs_state = do_sql_query("pbs_state", node)
    if pbs_state == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif pbs_state == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + pbs_state + "</span></td>\n")
        
        
        
    # Moab
    moab = do_sql_query("moab", node)
    if moab == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif moab == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + moab + "</span></td>\n")
        
        
        
    # Infiniband
    infiniband = do_sql_query("infiniband", node)
    if infiniband == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif infiniband == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    elif infiniband == "n/a":
        sys.stdout.write("<td>n/a</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + infiniband + "</span></td>\n")



    ### Tempurature
    ##tempurature = do_sql_query("tempurature", node)
    ##if tempurature == None:
        ##sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    ##else:
        ##sys.stdout.write("<td>" + tempurature + "</td>\n")


        
    # /scratch
    scratch = do_sql_query("scratch", node)
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
        "/lchong/archive" : "lchong_archive",
        "/lchong/home" : "lchong_home",
        "/lchong/work" : "lchong_work",
        "/pan" : "panasas",
    }

    
    for mount_point in sorted(filesystems.iterkeys()):
        mount_status = do_sql_query(filesystems[mount_point], node)
        
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
<script src="beomon-stuff/jquery.stickytableheaders.js" type="text/javascript"></script> 

<script type="text/javascript">

                $(document).ready(function () {
                        $("table").stickyTableHeaders();
                });

</script>
</body>
</html>
""")
