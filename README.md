Beomon
======

Beomon is an application used to monitor the status of the University of Pittsburgh's HPC 
cluster "[Frank](http://core.sam.pitt.edu/frank)".  This software adds two node states not available in 
the standard Scyld/Beowulf install: orphaned and partnered.

"Orphaned" means that the compute node is still alive and checking into
the back-end database (or at least has in the past 10 minutes).  This is
needed to support Scyld's "run to completion" feature.  When a compute 
node is first seen in the state "orphan" Beomon's master agent will
prevent new jobs from being scheduled on the node.  Similarly when
the node is first seen in the state "up" jobs scheduling will be
enabled for the compute node.

"Partnered" means that the compute node is under the control of another
master node.  This is needed to support Scyld's active-active master
configuration.  For example with master nodes head0a and head0b both configured
to be a possible master of node 10, one master will consider the node 
"partnered" while the other in control of the compute node considers
it up, boot or error.  Otherwise both masters consider it down
or orphaned when no master is in control.

![Beomon Display](http://www.pitt.edu/~jaw171/beomon/main.jpg)
![Beomon Display Nodes](http://www.pitt.edu/~jaw171/beomon/nodes.jpg)

License
-------

Except where otherwise noted, this software is released under version three of the GNU General Public License (GPL) of the
Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
Use or modification of this software implies your acceptance of this license and its terms.
This is free software, you are free to change and redistribute it with the terms of the GNU GPL.
There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.

Installation
------------

Beomon utilizes a MongoDB database.  These instructions are for
RHEL6/CentOS6 and assumes /opt/sam is available to all nodes.  Any Web server
capable of running a Python script should work but here I use Apache httpd.

### Install MongoDB
* Add the [10gen repository](http://docs.mongodb.org/manual/tutorial/install-mongodb-on-red-hat-centos-or-fedora-linux/)
* Install MongoDB: `yum install mongo-10gen mongo-10gen-server`
* Enable authentication: Edit /etc/mongod.conf and set 'auth = true'
* Optionally, disable the Web interface and preallocation: 'nohttpinterface = true' and 'noprealloc = true'
* Start mongod: `service mongod start`


### Prepare the database
* Enter the mongo shell: `mongo`
* Switch to the admin database: `> use admin`
* Create an admin user: `> db.addUser("admin", "somepass")`
* Authenticate as the admin user: `>db.auth("admin", "somepass")`
* Switch to the beomon database: `> use beomon`
* Create the beomon user: `> db.addUser("beomon", "somepass")`


### Prepare clients
* `yum install python-devel gcc`
* Install PyMongo: `mkdir pymongo; cd pymongo; wget https://github.com/mongodb/mongo-python-driver/archive/v2.5.zip`
* `unzip v2.5`
* `/opt/sam/python/2.7.5/gcc447/bin/python setup.py build`
* `/opt/sam/python/2.7.5/gcc447/bin/python setup.py install --prefix=/opt/sam/python/2.7.5/gcc447/`
* Repeat for paramiko
* Create the password file: `echo 'somepass' > /opt/sam/beomon/beomonpass.txt`
* Secure the password file: `chmod 600 /opt/sam/beomon/beomonpass.txt`


### Configure Apache httpd

* `yum install httpd mod_wsgi`
* Add the Beomon configuration file to /etc/httpd/conf.d
* Copy style.css, [jquery.stickytableheaders.js](https://github.com/jmosbech/StickyTableHeaders/tree/master/js) and [jquery.min.js](http://code.jquery.com/jquery-1.8.3.min.js) to /opt/sam/beomon/html/static/
* Ensure the user httpd runs as can execute the program and access the files.
* Go to http://your.web.server/beomon



The programs
------------

**beomon_master_agent.py** is ran on the master/head nodes of the cluster.  This 
program checks the status (up, down, boot, error, orphan) of compute nodes and 
updates the database.  To use it pass a string of which nodes to check.

Example: `beomon_master_agent.py 0-5,7-9`


**beomon_compute_node_agent.py** is ran on each compute node and checks the status
of Infiniband, mount points, etc as well as gathering system information such as RAM size, 
CPU count, etc.  It can be ran via the master/head node with:

`beorun --all-nodes --nolocal beomon_compute_node_agent.py`

However, it is designed to be started in daemon mode on each compute node as they boot
with `99zzzbeomon`.  Note that in daemon mode health is only checked once (except for Infiniband) then 
every 5 minutes it will only update the DB saying it checked in (and check Infiniband again).


**99zzzbeomon.sh** is a Beowulf init script.  Place it in /etc/beowulf/init.d and make it executable.
Compute nodes should run it when they boot or you can run it by hand with an argument of which
node you want to start the compute agent on.


**beomon_outage.py** will show when compute nodes went down, when they came back up and how long they were down.


**beomon_display.py** is a WSGI program to be ran by a Web server.  This will display a table of the
current status of each compute node.  Click the node number to see the node's details (CPU type, RAM 
amount, etc.).  It also displays a summary/status of head nodes and storage.  This does not support Internet Explorer.

It uses style.css and [jquery.stickytableheaders.js](https://github.com/jmosbech/StickyTableHeaders).
The style.css file is derived from unlicensed work by Adam Cerini of the University of Pittsburgh.  
The file jquery.stickytableheaders.js is from [Jonas Mosbech](https://github.com/jmosbech).  


**beomon_zombie_catcher.py** will attempt to find processes on compute nodes which are not from a running 
job (zombies).  Note 'zombie' in this sense is not a Unix-style zombie process but
a running process left over from a previous job.
