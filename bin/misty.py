#!/usr/bin/env python
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
""""
The main misty/manage executable
Misty is a command line interface to the manage libraries to manage the HPC clusters present in the Ghent University.
It ties in with quattor to detect the clusters and it's masters and nodes.
Manage also allows you to start and stop the pbs scheduler, put nodes online/offline,
reboot them (using ssh, impi, dmtf smash,...),
acknowledge services/hots in icinga/nagios...
Misty will parse the output manage output and show it in a somehow readable form to the user on the command line.
"""
# import fancylogger and config first, this way loging options should be in effect before external tools start logging
from vsc.utils import fancylogger
from vsc.manage.config import get_options
from vsc.manage.manage import Manager
# after importing config


def main():
    """
    main method
    parses arguments and constructs Manager object and performs actions
    """
    logger = fancylogger.getLogger()
    options = get_options()
    logger.debug("arguments parsed, starting manager")
    manager = Manager(options)

    #print status
    if manager.status:
        print "Status:\n %s" % manager.status

    #actually do requested commands
    out = manager.doit()
    #parse and display the output
    errors = []
    if out:
        for i in out:  # this is an array of nodes and their  output,err
            if len(i[1]) > 0:  # only print if something to show
                print "%s:" % i[0]  # first element is the node
                for j in i[1]:  # second element is an array of [outputs of commands,errors]
                    print "    output: %s" % str(j[1][0])
                    if j[1][1]:
                        print "    error:  %s" % str(j[1][1])
                        errors.append(i[0])

    # print all nodes with errors out on the end
    if len(errors) > 0:
        print "ERRORS occured in: \n ", ",".join([str(x) for x in errors])

    #TODO: actuallym use a smart diff algorithm to only show relevant output
    #(which nodes differ, and those with errors)
    #done


main()
