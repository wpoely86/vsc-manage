#
# Copyright 2011-2016 Ghent University
#
# This file is part of vsc-manage,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/hpcugent/vsc-manage
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
'''
This is the main Manager object, you will mostly interact in python using this object.
If you want an exacutable script to run on the cli, use misty.

You can create a Manager object, with given options (there is a default Options object in vsc.manage.config)
This will parse the options and set everything up to run the selected actions on the selected nodes.

Created on Oct 13, 2011

@author: Jens Timmerman
'''

import re

from clusters import Cluster
from config import get_config
from monitoring import Icinga
from nodes import CompositeNode, NodeException
from vsc.utils import fancylogger


# TODO: (low) add espeon (add --server option?)
class Manager(object):
    '''
    This class is used to manage the UGent HPC clusters

    adding a new cluster involves creating a new extension of the Cluster class
    here, set the NodeClass
    you'll probably have to create a new extension of node to implement what you want to do here
    '''

    def __init__(self, options):
        '''
        Constructor,
        requires a options object (as created by OptionParser)
        f.ex:
        {'debug':False, 'node': None, 'forced': False, 'hardreboot': False, 'allForced': False, 'chassis': None, 'state': True,
        'down': False, 'all': False, 'ack': None, 'idle': False, 'runcmd': None,
        'cluster': None, 'poweroff': False, 'pbsmomcleanup': False, 'pbsmomstop': False,
        'pbsmomstatus': False, 'debug': False, 'postpoweron': False, 'offline': False,
        'poweron': False, 'test_run': False, 'pbsmomrestart': False, 'Master':None,}
        '''
        self.log = fancylogger.getLogger(self.__class__.__name__)
        self.log.debug("manager created")
        self.status = None
        self.comment = None
        self.log.debug("options: %s" % options.__dict__)
        self.options = options

        # get cluster
        if not options.cluster:
            self.cluster = Cluster.getDefaultCluster()
            self.log.warning("Selected cluster %s as default cluster" % self.cluster)
        else:
            self.cluster = Cluster.getCluster(options.cluster)

        self.log.debug("creating cluster: %s" % self.cluster)

        # group by chassis
        self.group_by_chassis = (hasattr(self.cluster, "group_by_chassis") and self.cluster.group_by_chassis)

        # get nodes from cluster
        self.nodes = self.getNodes()
        self.log.info("selected nodes on cluster %s: %s" % (self.cluster, self.nodes))

        # monitoring service
        self.monitoring = Icinga(self.nodes.getNodes(), options.imms)

        # parse action(s)
        self.parseActions()

    def doit(self):
        """
        do the actual actions
        This will run al commands scheduled on the selected nodes
        AND this clusters master node.
        (only the things you scheduled on the master node)
        output is an array of arrays of nodes and an array of their commands and an array of out,err

        f.ex
        [
        [node001,
            [[command1,[out,err]],
             [command2,[out,err]]]
        ],
        [node002,[[command1,[out,err]]]]
        ]
        """
        # check for special nodes
        if self.hasSpecials():
            self.log.info("Selected nodes include special nodes (storage, masters,...)")
            if not self.options.forced:
                msg = "You are selecting special nodes (storage, masters,...) "\
                      "without the --forced option\nAborting"
                self.log.warning(msg)
                return False

        # TODO: check for special actions, just checking one right now
        # we might want to check for not doing anything special on a node
        # where the scheduler is running on.
        if self.options.restart and not self.options.forced:
                msg = "You trying to restart the scheduler"\
                      "without the --forced option, do you know what you are doing?\nAborting"
                self.log.warning(msg)
                return False

        # add the master if it was not selected. this is ok, nothing special should have
        # been queued on it.
        if not self.nodes.contains(self.cluster.getMaster().nodeid):
            self.log.info("Master not in selected nodes, adding it")
            # this is ok, since only options regarding the master will be queued on it.
            self.nodes.add(self.cluster.getMaster())

        commands = self.nodes.showCommands()
        commands.append(self.monitoring.showCommands())
        if self.options.test_run:
            msg = "was going to run %s\n" % commands
            self.log.info(msg)
            print msg
            return False
        else:
            self.log.info("Going to run: %s" % commands)

        monout = self.monitoring.doIt()
        self.log.debug("monitoring output: %s " % (monout))

        out = self.nodes.doIt(not self.options.non_threaded, group_by_chassis=self.group_by_chassis)
        out.append(monout)
        self.log.info("Done it")
        return out

    def getNodes(self):
        """
        gets the nodes defined by this manager object
        """
        options = self.options
        cluster = self.cluster
        nodes = CompositeNode()
        if options.chassis:
            self.log.debug("option chassis: %s" % options.chassis)
            nodes.union(cluster.getNodesFromChassis(options.chassis, options.quattor))
        if options.down:
            self.log.debug("option down")
            nodes.union(cluster.getDownNodes())
        if options.all_nodes:
            self.log.debug("option all")
            tnodes = cluster.getAllNodes(quattor=bool(options.quattor))
            self.log.debug("Selecting all nodes: %s" % tnodes)
            nodes.union(tnodes)

        if options.worker:
            self.log.debug("option worker nodes")
            nodes.union(cluster.getWorkerNodes(quattor=bool(options.quattor)))

        if options.idle:
            self.log.debug("option idle")
            nodes.union(cluster.getIdleNodes())
        if options.offline:
            self.log.debug("option offline")
            nodes.union(cluster.getOfflineNodes())

        if options.storage:
            self.log.debug("found --storage option: %s" % options.master)
            self.log.warning("--storage not implemented yet")

        if options.master:
            # find master
            self.log.debug("found --master option: %s" % options.master)
            tnodes = re.findall("master\d*", options.master)
            if tnodes:
                self.log.debug("found master specifier %s" % tnodes)
                for nodeid in tnodes:
                    try:
                        masters = cluster._getMasters()
                        self.log.debug('got masters %s' % masters)

                        self.log.debug('getting masters %s' % nodeid)
                        node = masters.get(nodeid)
                        self.log.debug("adding master %s" % node)
                        nodes.add(node)
                    except NodeException, ex:
                        self.log.warning("could not add master node %s : %s" % (nodeid, ex))
        if options.node:
            self.log.debug("found --node option: %s" % options.node)
            for nodeid in self._parseNodes(options.node):
                try:
                    nodes.add(self._getNode(nodeid))
                    self.log.debug("added node %s" % nodeid)
                except NodeException, e:
                    self.log.warning("Could not find %s: %s" % (nodeid, e))
        return nodes

    def _parseNodes(self, nodestring):
        """
        given a string parses the nodes selected in it
        you can give up different nodes or ranges separated by a ','
        a range is formated like: 'startid-stopid'
        """
        ids = []
        self.log.debug("parsing nodes from %s" % nodestring)
        # we can specify different nodes or ranges with the ',' delimiter.
        # so recursively parse what's in between ,'s
        if len(re.split(",", nodestring)) > 1:
            tnodes = re.split(",", nodestring)
            self.log.debug("found node specifiers %s" % tnodes)
            for nodeid in tnodes:
                ids.extend(self._parseNodes(nodeid))
            return ids

        # ranges can't be nested
        if len(re.split("-", nodestring)) == 2:
            self.log.info("found range specifier: %s" % nodestring)
            ranged = re.split("-", nodestring)
            start = self._getIdFromString(ranged[0])
            stop = self._getIdFromString(ranged[1])
            self.log.debug("start %s - stop %s" % (start, stop))
            for x in xrange(int(start), int(stop) + 1):
                snodeid = "node%03d" % x
                try:
                    ids.append(snodeid)
                except NodeException, ex:
                    self.log.raiseException("could not add node %s : %s" % (id, ex))
            self.log.debug("id range parsed: %s" % ids)
            return ids
        else:
            return [nodestring]

    def _getNode(self, nodeid):
        """
        internal method
        returns a node with the given nodeid (as string)
        """
        # TODO use templates for regexes here.
        # see question http://stackoverflow.com/questions/2654856/python-convert-format-string-to-regular-expression
        nid = self._getIdFromString(nodeid)
        snodeid = "node%03d" % int(nid)  # at least 3
        self.log.debug("parsing %s to %s" % (nid, snodeid))
        try:
            return self.cluster.getNode(snodeid)
        except NodeException, ex:
            self.log.raiseException("could not add node %s : %s" % (nid, ex), NodeException)

    def _getIdFromString(self, string):
        nodeidt = []
        nodeidtt = re.findall("^(\d{3,4})$", string)
        if nodeidtt:
            nodeidt.append(nodeidtt[0])
        nodeidtt = re.findall("^node(\d{3,4})$", string)
        if nodeidtt:
            nodeidt.append(nodeidtt[0])
        if not nodeidt:
            self.log.raiseException("could not parse ids from %s" % (string), NodeException)

        return nodeidt[0]

    def hasSpecials(self):
        """
        checks if any of the nodes are special nodes
        """
        for node in self.nodes.getNodes():
            if hasattr(node, "_special_node") and node._special_node:
                return True
        return False

    def printstatusses(self):
        """
        print the statusses of the selected nodes
        """
        txt = "\nNodes - Chassis interface - Location        "\
              " tcpping - alivessh - pbs state - hwstate \n"
        txt += '-' * len(txt) + "\n"
        statusses = self.nodes.getStatus(forced=False, threaded=(not self.options.non_threaded), group_by_chassis=self.group_by_chassis)
        # parse results
        errors = {}
        for status in statusses:
            node = status[0]
            result = None
            try:
                result = [x[0] for x in status[1]]
            except (IndexError, TypeError):
                self.log.info("failed to parse status of %s: %s" % (node, status))

            # keep track of errors
            try:
                errors[node] = [x[1] for x in status[1] if x[1]]
            except (IndexError, TypeError):
                # no errors is a normal case
                pass

            # get nodename
            txt += "%-7s %-19s %-16s %s\n" % (node.nodeid, node.getChassis(), node.getSlot(), result)

        # print errors
        if errors:
            txt += "Errors occured:\n    "
            txt += "\n    ".join(["%s: %s" % (x, errors[x]) for x in sorted(errors.keys()) if errors[x]])
            txt += "\n"
        self.log.info("getStatus in master: %s" % txt)
        print txt

    def parseActions(self):
        """
        parse the actions in the self.options and queue them on self.nodes
        """
        options = self.options
        if options.state:
            self.printstatusses()

        # node actions
        if options.ledon:
            self.nodes.ledOn()
        if options.ledoff:
            self.nodes.ledOff()
        if options.pbsmomcleanup:
            self.nodes.pbsmomcleanup()
        if options.fix_downonerror:
            self.nodes.fixdownonerror()
        if options.co:
            self.nodes.run_component(options.co.split(","))
        if options.setoffline:
            self.nodes.setoffline()
        if options.pbsmomstop:
            self.nodes.pbsmomstop()
        if options.runcmd:
            self.nodes.runCustomCmd(options.runcmd)
        if options.pbsmomstatus:
            self.nodes.pbsmomstatus()
        if options.poweroff:
            self.nodes.poweroff()
        if options.powercut:
            self.nodes.powercut()
        if options.poweron:
            self.nodes.poweron()
        if options.reboot:
            self.nodes.softreboot()
        if options.hardreboot:
            self.nodes.reboot()
        if options.setonline:
            self.nodes.setonline()
        if options.pbsmomrestart:
            self.nodes.pbsmomrestart()
        if options.poweroff or options.hardreboot or options.powercut or options.reboot:
            if not options.downtime:
                downtime = get_config('DOWN_TIME')
                self.log.warning("No downtime scheduled, Scheduling %s by default", downtime)
                options.downtime = float(downtime)

        # cluster actions
        if options.pause:
            self.cluster.getMaster().pauseScheduler()
        if options.resume:
            self.cluster.getMaster().resumeScheduler()
        if options.restart:
            self.cluster.getMaster().restartScheduler()

        # icinga actions, do this before something else
        if options.ack:
            self.monitoring.acknowledgeHost(options.comment)

        if options.ack_service:
            self.monitoring.acknowledgeService(options.ack_service, comment=options.comment)

        if options.downtime:
            hours = float(get_config('DOWN_TIME'))
            try:
                hours = float(options.downtime.split("h")[0])
            except:
                self.log.warning("No valid downtime supplied: %s, using %s by default", options.ack, hours)
            self.monitoring.scheduleDowntime(hours, comment=options.comment)
