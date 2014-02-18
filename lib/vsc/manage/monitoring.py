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
Created on Feb 22, 2012

@author: Jens Timmerman
'''
from config import get_config
from managecommands import SshCommand, Worker
from vsc import fancylogger


class Monitoring(Worker):
    '''
    This class (interface) represents a monitoring service
    '''

    def __init__(self, nodelist, imms=False):
        '''
        Constructor
        nodelist is a list of hostnames for nodes to perform actions on
        if imms=True it will also do the same action on the imm nodes of the given nodelist nodes
        '''
        Worker.__init__(self)
        self.nodelist = nodelist
        self.log = fancylogger.getLogger(self.__class__.__name__)
        self.imms = imms

    def scheduleDowntime(self, hours):
        """
        schedule a downtime for the nodes
        """
        pass

    def __repr__(self):
        return self.__class__.__name__

    def doIt(self):
        """
        compatibility with the compositenode output
        """
        out = Worker.doIt(self)
        return [self, out]


class MonitoringException(Exception):
    """
    Raised when something goes wrong with monitoring
    """
    pass


class Icinga(Monitoring):
    """
    Implementation of monitoring, interfacing with icinga.
    """

    def scheduleDowntime(self, hours, comment=None):
        """
        schedule a downtime for the nodes

        This schedules a downtime for the host, and all it's services
        """
        commands = []
        import time

        #comment could still be None or false
        if not comment:
            comment = get_config("ICINGA_DEFAULT_COMMENT")

        starttime = int(time.time())
        duration = 3600 * float(hours)
        endtime = starttime + duration
        for node in self.nodelist:
            commands.append('echo "%s" > %s' %
                            (get_config("ICINGA_SCHEDULE_SERVICE_DOWNTIME") % {'host_name': node.hostname,
                            'start_time': starttime, 'timestamp': starttime - 1, 'comment': comment, 'end_time': endtime,
                            'duration': duration, 'clustername': node.clustername}, get_config("ICINGA_SOCKET"))
                            )
            if self.imms and node.immmonitoring:
                commands.append('echo "%s" > %s' %
                                (get_config("ICINGA_SCHEDULE_SERVICE_DOWNTIME") % {'host_name': node.immmonitoring,
                                'start_time': starttime, 'timestamp': starttime - 1, 'comment': comment,
                                'end_time': endtime, 'duration': duration, 'clustername': node.clustername},
                                get_config("ICINGA_SOCKET"))
                                )
        command = ";".join(commands)

        self.log.debug("creating command %s" % command)
        command = SshCommand(command=command, host=get_config("ICINGA_HOST"), user="root", port=22, timeout=60)
        self._adcommand(command)

        return True

    def acknowledgeHost(self, comment=None):
        """
        Acknowledges a problem on the current nodes

        This acknowledges the current problem on the host, but not it's services
        """
        commands = []
        import time
        starttime = int(time.time())

        #comment could still be None
        if not comment:
            comment = get_config("ICINGA_DEFAULT_COMMENT")

        for node in self.nodelist:
            tpldict = {
                'host_name': node.hostname,
                'timestamp': starttime - 1,
                'comment': comment,
                'clustername': node.clustername
            }
            tpldict['host_name'] = get_config('ICINGA_HOSTNAME') % tpldict
            ack_command = 'echo "%s" > %s' % (get_config("ICINGA_ACKNOWLEDGE_HOST_PROBLEM") % tpldict, get_config("ICINGA_SOCKET"))
            commands.append(ack_command)
            if self.imms and node.immmonitoring:
                commands.append('echo "%s" > %s' % (get_config("ICINGA_ACKNOWLEDGE_HOST_PROBLEM") % {
                    'host_name': node.immmonitoring,
                    'timestamp': starttime - 1,
                    'comment': comment,
                    'clustername': node.clustername,
                }, get_config("ICINGA_SOCKET")))

        command = ";".join(commands)
        self.log.debug("creating command %s" % command)
        command = SshCommand(command=command, host=get_config("ICINGA_HOST"), user="root", port=22, timeout=60,)
        self._adcommand(command)

    def acknowledgeService(self, servicename, comment=None):
        """
        Acknowledges a given service on all nodes
        """
        commands = []
        import time
        starttime = int(time.time())

        #comment could still be None
        if not comment:
            comment = get_config("ICINGA_DEFAULT_COMMENT")

        for node in self.nodelist:
            tpldict = {
                'host_name': node.hostname,
                'timestamp': starttime - 1,
                'comment': comment,
                'clustername': node.clustername,
                'service': servicename
            }
            # apply icinga templating to hostname
            tpldict['host_name'] = get_config('ICINGA_HOSTNAME') % tpldict
            ack_command = get_config("ICINGA_ACKNOWLEDGE_SERVICE_PROBLEM") % tpldict
            commands.append('echo "%s" > %s' % (ack_command, get_config("ICINGA_SOCKET")))
            if self.imms and node.immmonitoring:
                ack_command = get_config("ICINGA_ACKNOWLEDGE_SERVICE_PROBLEM") % {
                    'host_name': node.immmonitoring,
                    'timestamp': starttime - 1,
                    'comment': comment,
                    'clustername': node.clustername,
                    'service': servicename
                }
                commands.append('echo "%s" > %s' % (ack_command, get_config("ICINGA_SOCKET")))
        command = ";".join(commands)
        self.log.debug("creating command %s" % command)
        command = SshCommand(command=command, host=get_config("ICINGA_HOST"), user="root", port=22, timeout=60,)
        self._adcommand(command)
