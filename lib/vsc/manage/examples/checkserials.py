##
# Copyright 2011-2013 Ghent University
#
# This file is part of vsc-manage,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/vsc-manage
#
# vsc-manage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# vsc-manage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vsc-manage.  If not, see <http://www.gnu.org/licenses/>.
#
##
'''
Created on Mar 6, 2012

This module contains some example scripts that use manage to make some tasks easier.

@author: Jens Timmerman
'''

import sys
sys.path.append("../.")
from manage import options, Manager
from nodes import Node

#usage: give a list of clusternames you want to check the serials from
#also set the ENV in config to TESTING or SERVER

CLUSTERS = sys.argv[1:]
SERIAL_XPATH = "/*/nlist[@name='hardware']/string[@name='serialnumber']"

def checkSerials():
    """
    check all serials in all nodes on all clusters,
    compare the serials in quattor with the real serials reported by the machines
    """
    #set options
    opts = options() #default options object
    opts.all_nodes = True
    opts.verbose= 0
    opts.forced = True
    opts.runcmd = "dmidecode -s system-serial-number"

    for cluster in CLUSTERS:
        opts.cluster = cluster

        #create manager
        manager = Manager(opts)

        #get serials from quattor
        serials = {}
        for  node in manager.nodes.getNodes():
            serials[node.nodeid] = node._getQuattorElement(SERIAL_XPATH)
        print serials

        #get serials from nodes
        out = manager.doit()

        #parse output and compare
        for nodeout in out:
            if not isinstance(nodeout[0],Node):
                continue #skip monitoring etc...

            node = nodeout[0].nodeid
            if nodeout[1] and len(nodeout[1]) > 0 and len(nodeout[1][0]) > 1:
                serial = nodeout[1][0][1][0]
                if nodeout[1][0][1][1]:
                    print "error checking %s: %s"%(node,nodeout[1][0][1][1])
            else:
                serial = None

            try:
                if serials[node] != serial:
                    print "serial for %s is incorrect in quattor:%s, reported by machine: %s"%(node,serials[node],serial)
                #print node,serial,serials[node]
            except (KeyError,AttributeError):
                pass #master or icinga gets added my manager, ignore this.


checkSerials()
