#!/usr/bin/env python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1.1.1
# Last change: Added additional mount points to check

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
<link href="http://clusman0-dev.francis.sam.pitt.edu/nodes-css/style.css" rel="stylesheet" type="text/css">
</head>
<body>
    <center>
        <h2>Beomon</h2>
        <p>Node state (up, down, boot ...) is checked every 5 minutes.
    </center>
<table id="nodes" summary="Node status" class="fancy">
    <thead>
        <tr>
            <th scope="col">Node</th>
            <th scope="col">State</th>
            <th scope="col">PBS</th>
            <th scope="col">Moab</th>
            <th scope="col">Infiniband</th>
            <th scope="col">/scratch</th>
            <th scope="col">/pan</th>
            <th scope="col">/home</th>
            <th scope="col">/home1</th>
            <th scope="col">/home2</th>
            <th scope="col">/gscratch0</th>
            <th scope="col">/gscratch1</th>
            <th scope="col">/data/sam</th>
            <th scope="col">/data/pkg</th>
            <th scope="col">/lchong/home</th>
            <th scope="col">/lchong/archive</th>
            <th scope="col">/lchong/work</th>
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
        
        print "<td></td>" * 15
        
        continue
        
    elif state == "up":
        sys.stdout.write("<td>up\n")
        
    else:
        state_time = do_sql_query("state_time", node)
        
        sys.stdout.write("<td><span style='color:red' class='dropt'>" + state + "<span>Since " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state_time)) + "</span></span></td>\n")
        
        print "<td></td>" * 15
        
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

        
        
    # /pan
    panasas = do_sql_query("panasas", node)
    if panasas == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif panasas == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + panasas + "</span></td>\n")
        
        
        
    # /home
    home = do_sql_query("home", node)
    if home == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif home == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + home + "</span></td>\n")
        
        
        
    # /home1
    home1 = do_sql_query("home1", node)
    if home1 == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif home1 == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + home1 + "</span></td>\n")
        
        

    # /home2
    home2 = do_sql_query("home2", node)
    if home2 == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif home2 == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + home2 + "</span></td>\n")
        
        
        
    # /gscratch0
    gscratch0 = do_sql_query("gscratch0", node)
    if gscratch0 == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif gscratch0 == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + gscratch0 + "</span></td>\n")
        
        
 
    # /gscratch1
    gscratch1 = do_sql_query("gscratch1", node)
    if gscratch1 == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif gscratch1 == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + gscratch1 + "</span></td>\n")
        
        
        
    # /data/sam
    datasam = do_sql_query("datasam", node)
    if datasam == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif datasam == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + datasam + "</span></td>\n")
        
        
        
    # /data/pkg
    datapkg = do_sql_query("datapkg", node)
    if datapkg == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif datapkg == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + datapkg + "</span></td>\n")
        
        
        
    # /lchong/home
    lchong_home = do_sql_query("lchong_home", node)
    if lchong_home == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif lchong_home == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + lchong_home + "</span></td>\n")
        
        
        
    # /lchong/archive
    lchong_archive = do_sql_query("lchong_archive", node)
    if lchong_archive == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif lchong_archive == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + lchong_archive + "</span></td>\n")
        
        
        
    # /lchong/work
    lchong_work = do_sql_query("lchong_work", node)
    if lchong_work == None:
        sys.stdout.write("<td><span style='color:red'>unknown</span></td>\n")
        
    elif lchong_work == "ok":
        sys.stdout.write("<td>ok</td>\n")
        
    else:
        sys.stdout.write("<td><span style='color:red'>" + lchong_work + "</span></td>\n")
        
        
        
    sys.stdout.write("</tr>\n")



# Close the DB, we're done with it
db.close()



# Footer
sys.stdout.write("""    </tbody>
</table>
</body>
</html>
""")