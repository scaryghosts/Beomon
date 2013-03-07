#!/usr/bin/env python
# Description: Beomon status viewer
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1
# Last change: Initial version

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



import sys
sys.path.append("/opt/sam/beomon/modules/")
import os, MySQLdb
from optparse import OptionParser



# How were we called?
parser = OptionParser("%prog [options]\n" + 
  "Beomon node statistics generator.\n" +
  "This program will create a nodes.csv file containing information (CPU type, RAM \n" + 
  "amount, etc.) for each node and print a summary of all nodes."
)

(options, args) = parser.parse_args()



# Query MySQL for a given column of a given node
def do_sql_query(column, node):
    cursor.execute("SELECT " + column + " FROM beomon WHERE node_id=" + node)
    
    results = cursor.fetchone()
    
    return results[0]
      
      
      
# Open the nodes.csv file
if os.path.exists("nodes.csv"):
  sys.stderr.write("nodes.csv file exists, not clobbering.\n")
  sys.exit(1)
  
csv_handle = open("nodes.csv", "w")

csv_handle.write("Node, CPU Type, CPU Core Count, GPU?, Infiniband?, Scratch Amount (GB), RAM Amount (GB), Serial\n")




# Get the DB password
dbpasshandle = open("/opt/sam/beomon/beomonpass.txt", "r")

dbpass = dbpasshandle.read().rstrip("\n")

dbpasshandle.close()

  
  
# Open a DB connection
try:
  db = MySQLdb.connect(host="clusman0-dev.francis.sam.pitt.edu", user="beomon",
                       passwd=dbpass, db="beomon")
                       
  cursor = db.cursor()
  
except Exception as err:
  sys.stderr.write("Failed to connect to the Beomon database: " + str(err) + "\n")
  sys.exit(1)
  
  

summary_stats = {
  "nodes" : 0,
  "cpu_num" : 0,
  "scratch_size" : 0,
  "ram" : 0
}
  
  
  
# Loop through each node in the DB
cursor.execute("SELECT node_id, cpu_type, cpu_num, gpu, infiniband, scratch_size, ram, serial FROM beomon")

for row in sorted(cursor.fetchall()):
  [node, cpu_type, cpu_num, gpu, infiniband, scratch_size, ram, serial] = row


  # Skip the node if we are missing something
  skip = False
  for i in row:
    if i == None:
      sys.stderr.write("Details missing for node " + str(node) + ", skipping.\n")
      skip = True      
      break
      
  if skip == True: continue

  
  if gpu == 0:
    gpu = "No"
    
  elif gpu == 1:
    gpu = "Yes"
    
  
  if infiniband == "n/a":
    infiniband = "No"
    
  else:
    infiniband = "Yes"
  
  
  csv_handle.write(str(node) + "," + cpu_type + "," + str(cpu_num) + "," + gpu + "," + infiniband + "," + scratch_size + "," + ram + "," + serial + "\n")
  
  
  summary_stats["nodes"] += 1
  summary_stats["cpu_num"] += cpu_num
  summary_stats["scratch_size"] += float(scratch_size)
  summary_stats["ram"] += float(ram)
  
  

# Print the final stats
sys.stdout.write("Nodes: " + str(summary_stats["nodes"]) + "\n")
sys.stdout.write("CPUs: " + str(summary_stats["cpu_num"]) + "\n")
sys.stdout.write("Scratch: " + str(summary_stats["scratch_size"]) + " GB\n")
sys.stdout.write("RAM: " + str(summary_stats["ram"]) + " GB\n")  