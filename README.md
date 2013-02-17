Beomon
======

Beomon is an application used to monitor the status of compute nodes in a
Beowulf-style cluster and create a Web interface to view the status of the
nodes.  Specifically this supports the University of Pittsburgh's HPC 
cluster "Frank".

License
-------

This software is released under version three of the GNU General Public License (GPL) of the
Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
Use or modification of this software implies your acceptance of this license and its terms.
This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.

Installation
------------

Beomon utilizes a MySQL (or compatible) database.  These instructions are for
RHLE6/CentOS6 and assumes /opt/sam is available to all nodes.  Any Web server
capable of running a python script should work.

### Prepare the database
* `yum install mysql-server mysql MySQL-python`
* `rsync -Pah /usr/lib64/python2.6/site-packages/MySQLdb /opt/sam/beomon/modules/`
* `rsync -Pah /usr/lib64/python2.6/site-packages/_mysql* /opt/sam/beomon/modules/`
* `echo 'somepass' > /opt/sam/beomon/beomonpass.txt`
* `chmod 600 /opt/sam/beomon/beomonpass.txt`
* `service mysqld start`
* `/usr/bin/mysql_secure_installation`
* `mysql> CREATE DATABASE beomon;`
* `mysql> GRANT ALL PRIVILEGES ON beomon.* TO 'beomon'@'10.54.50.%' IDENTIFIED BY 'somepass';`
* `mysql> GRANT ALL PRIVILEGES ON beomon.* TO 'beomon'@'%.francis.sam.pitt.edu' IDENTIFIED BY 'somepass';`
* `mysql> FLUSH PRIVILEGES;`
* `mysql> USE beomon;`
* `mysql> CREATE TABLE beomon (node_id INT NOT NULL UNIQUE KEY PRIMARY KEY, state VARCHAR(50), state_count INT, \`
`moab VARCHAR(50), moab_count INT, infiniband VARCHAR(50), infiniband_count INT, tempurature VARCHAR(50), \`
`tempurature_count INT, scratch VARCHAR(50), scratch_count INT, panasas VARCHAR(50), panasas_count INT, \`
`home VARCHAR(50), home_count INT, home1 VARCHAR(50), home1_count INT, home2 VARCHAR(50), home2_count INT, \`
`home3 VARCHAR(50), home3_count INT, gscratch0 VARCHAR(50), gscratch0_count INT, gscratch1 VARCHAR(50), \`
`gscratch1_count INT, datasam VARCHAR(50), datasam_count INT, datapkg VARCHAR(50), datapkg_count INT, \`
`cpu_type VARCHAR(50), cpu_num INT, gpu BOOL, ib BOOL, scratch_size INT, ram INT, serial VARCHAR(50), \`
`last_check BIGINT);`


### Configure Apache httpd

* `yum install httpd`
* `...`

### Running the programs

beomon_master_agent.py is ran on the master/head node of the cluster.  This 
program checks the status (up, down, boot, error) of compute nodes and 
updates the database.  Pass a string to the -n flag of which nodes to check.

Example: `beomon_master_agent.py 0-5,7-9`

beomon_compute_node_agent.py is ran on each compute node and check the status
of Infiniband, mount points, CPU/system temperature, etc.  It can be ran via
the master/head node.

Example: `beorun --all-nodes --nolocal beomon_compute_node_agent.py`
