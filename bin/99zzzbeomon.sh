#!/bin/bash
# Description: Beomon init script for beomon_compute_node_agent.py



script="${0##*/}"
node_number=${NODE:=${1:?"No Node Specified"}}



bpsh -m $node_number /opt/sam/beomon/bin/beomon_compute_agent.py --daemonize

status=$?

if [ $status != 0 ];then
  echo "Beomon startup failed!"
fi