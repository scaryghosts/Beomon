#!/bin/bash
# Description: Beomon init script for beomon_compute_node_agent.py
# Written by: Jeff White of the University of Pittsburgh (jaw171@pitt.edu)
# Version: 1
# Last change: Initial version

# License:
# This software is released under version three of the GNU General Public License (GPL) of the
# Free Software Foundation (FSF), the text of which is available at http://www.fsf.org/licensing/licenses/gpl-3.0.html.
# Use or modification of this software implies your acceptance of this license and its terms.
# This is a free software, you are free to change and redistribute it with the terms of the GNU GPL.
# There is NO WARRANTY, not even for FITNESS FOR A PARTICULAR USE to the extent permitted by law.



script="${0##*/}"
node_number=${NODE:=${1:?"No Node Specified"}}



bpsh -m $node_number /opt/sam/beomon/bin/beomon_compute_agent.py --daemonize

status=$?

if [ $status != 0 ];then
  echo "Beomon startup failed!"
fi