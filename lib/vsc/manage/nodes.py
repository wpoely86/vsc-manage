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
Created on Oct 17, 2011

@author: Jens Timmerman
'''
try:
    import json
except:
    import simplejson as json

import gzip
import libxml2
import os
import re
import threading
import traceback

from vsc.utils import fancylogger
from vsc.manage.config import get_config

from managecommands import BladeSoftPoweroffCommand, BladePoweronCommand, \
    BladePoweroffCommand, TestCommand, Command, FullStatusCommand, \
    FullBladeStatusCommand, SshCommand, BladeRebootCommand, PBSStateCommand, \
    MasterStatusCommand, SetOnlineMasterCommand, SetOfflineMasterCommand, \
    SoftPoweroffCommand, SoftRebootCommand, PbsmomCommand, PbsmomCleanupCommand, \
    DracPoweronCommand, DracPoweroffCommand, DracRebootCommand, \
    DracFullStatusCommand, IpmiFullStatusCommand, IpmiPoweronCommand, \
    IpmiPoweroffCommand, IpmiSoftPoweroffCommand, IpmiRebootCommand, \
    ImmSoftPoweroffCommand, ImmPoweronCommand, ImmPoweroffCommand, ImmRebootCommand, \
    FullImmStatusCommand, MoabPauseCommand, MoabResumeCommand, MoabRestartCommand, \
    ImmSoftRebootCommand, Worker, NotSupportedCommand, DMTFSMASHCLPLEDOnCommand, \
    DMTFSMASHCLPLEDOffCommand, FixDownOnErrorCommand


class Node(Worker):
    """
    This class represents a node

    Nodes can queue commands, and will perform then once doIt is called.
    To create new nodes, extend this one, and set the commands to the right classes
    you should set the command classes (classes that extend the command class) for
        self.statusCommand
        self.softpoweroffCommand
        self.poweronCommand
        self.poweroffCommand
        self.rebootCommand
        self.postpoweronCommand
        self.pbsmonstatusCommand
        self.customCommandClass #class, not actuall command instance
        self.pbsmomcleanupCommand
        self.pbsmomstopCommand
        self.pbsmomrestartCommand
    """
    # statusses as shown by pbsnodes
    DOWN = "down"  # powered of
    FREE = "free"  # accepting work
    BUSY = "job-exclusive"  # full with work
    OFFLINE = "offline"  # not accepting work

    # statusses with diagnostic tools
    POWEROFF = "Poweroff"  # doesn't respond to ping
    SSHDOWN = "Hanging"   # doesn't respond to ssh
    POWERON = "Poweron"  # responds to ping
    ALIVE = "Alive"  # Responds to ssh

    UNKNOWN = "Unknown"

    # statusses in scheduling
    SCHEDDOWN = "ScheduleDown"
    SCHEDIDLE = "Idle"

    # alternate way of asking statusses: moab: #via mdiag -n on master
    def __init__(self, nodeid, clustername, masternode, commands=None):
        """
        constructor
        all real nodes have an id
        """
        Worker.__init__(self, commands=commands)
        self.log = fancylogger.getLogger(self.__class__.__name__)
        self.log.debug("creating Node %s" % nodeid)
        self.nodeid = nodeid
        self.status = None
        self.clustername = clustername
        self.slot = None
        self.customcmd = None
        self.chassisname = None
        self.masternode = masternode

        #TODO: (medium) allow for initializing this with the commands thing above
        # so no overwriting is needed, these can be parsed from quattor
        # see ticket 469

        # defaults
        self.customCommandClass = SshCommand

        self.hostname = get_config('HOST_TPL') % {"nodeid": nodeid, "clustername": clustername}
        self.immname = get_config('IMM_TPL') % {"nodeid": nodeid, "clustername": clustername}
        self.immmonitoring = None
        self.softpoweroffCommand = SoftPoweroffCommand(self.hostname)
        self.softrebootCommand = SoftRebootCommand(self.hostname)

        # not implemented - use this command

        ## Overwrite in extensions
        #self.poweronCommand = None
        #self.poweroffCommand = None
        #self.ledoffcommand = NotSupportedCommand("ledoff")
        #self.ledoncommand = NotSupportedCommand("ledon")

        self.statusCommand = None

        self.rebootCommand = None

        # this is only for workernodes
        #self.pbsmomstatusCommand = NotSupportedCommand("pbsmomstatus")
        #self.pbsmomcleanupCommand = NotSupportedCommand("pbsmomcleanup")
        #self.pbsmomstopCommand = NotSupportedCommand("pbsmomstop")
        #self.pbsmomrestartCommand = NotSupportedCommand("pbsmomrestart")
        #self.fixdownonerrorCommand = NotSupportedCommand("fixdownonerror")

    def getStatus(self, forced=False):
        """
        get the status of this node
        this is cached, will be refreshed if forced=True
        """
        if not self.status or forced:
            self.log.debug("getting node %s status by running %s" % (self, self.statusCommand))
            out = self.statusCommand.run()
            self.log.info("status for %s: %s" % (self.nodeid, out))
            self.status = out

        return self.status

    def getPbsStatus(self):
        """
        get the status of this node
        as reported by pbsmon
        use the node.DOWN etc constants (DOWN,OFFLINE and IDLE are defined by default)
        """
        "this is implemented in the master node"
        self.log.debug("getPbsStatus called on %s" % self)
        self.log.debug("going to call pbsstatus on master %s" % self.getMaster())
        return self.getMaster().getPbsStatusForNode(self.nodeid)[0]

    def getid(self):
        """
        returns the id of this node
        """
        return self.nodeid

    def isdown(self):
        """
        returns True if this node is currently down
        """
        return Node.DOWN in self.getPbsStatus().split(",")

    def isoffline(self):
        """
        returns True if this node is currently offline in pbs mom
        """
        return Node.OFFLINE in self.getPbsStatus().split(",")

    def isidle(self):
        """
        returns True if this node is currently idle
        """
        return Node.FREE in self.getPbsStatus().split(",")

    def isBusy(self):
        """
        returns True if this node is currently Busy doing work (job-exclusive in pbsmon)
        """
        return Node.BUSY in self.getPbsStatus().split(",")

    def ledOn(self):
        """
        schedule to turn on the locator led on this node
        """
        self._adcommand(self.ledoncommand)

    def ledOff(self):
        """
        schedule to turn on the locator led on this node
        """
        self._adcommand(self.ledoffcommand)

    def powercut(self):
        """
        schedule to power on this node
        """
        self._adcommand(self.poweroffCommand)

    def softreboot(self):
        """
        schedule to issue a soft reboot this node
        """
        self._adcommand(self.softrebootCommand)

    def reboot(self):
        """
        schedule to reboot this node
        """
        self._adcommand(self.rebootCommand)

    def softpoweroff(self):
        """
        schedule to poweroff this node
        """
        self._adcommand(self.softpoweroffCommand)

    def poweron(self):
        """
        poweron this node
        """
        self._adcommand(self.poweronCommand)

    def pbsmomrestart(self):
        """
        Service pbs_mom restart on this node
        """
        self._adcommand(self.pbsmomrestartCommand)

    def pbsmomstatus(self):
        """
        Service pbs_mom status on this node
        """
        self._adcommand(self.pbsmomstatusCommand)

    def pbsmomstop(self):
        """
        Service pbs_mom stop on this node
        """
        self._adcommand(self.pbsmomstopCommand)

    def pbsmomcleanup(self):
        """
        Service pbs_mom cleanup on this node
        """
        self._adcommand(self.pbsmomcleanupCommand)

    def fixdownonerror(self):
        """
        Service to fix down on error for this node
        """
        self._adcommand(self.fixdownonerrorCommand)

    def run_component(self, components):
        """
        Service to run a list of quattor components
        """
        command = "ncm-ncd --co %s" % " ".join(components)
        self.runCustomCmd(command)

    def runCustomCmd(self, command=None):
        """
        Run an arbitraty command on this node
        """
        if not command:
            command = self.customcmd
        self._adcommand(command)

    #TODO: (medium)  implement shutdown:
    #try softpoweroff first
    # if this fails, then powercut
    #we need some state for this, like a daemon running on the master, or fork to background?

    def _createCustomCommand(self, command):
        """
        create a custom command before calling runCustomCmd
        this will not be started in a seperate thread,
        so output from the command can be logged
        """
        if not self.customCommandClass:
            self.log.raiseException("customCommandClass %s is not defined"
                                    "did you properly extend the Node class?" % self.customCommandClass,
                                    NodeException)
        if not issubclass(self.customCommandClass, Command):
            self.log.raiseException("customCommandClass %s is not a command class child"
                                    "did you properly extend the Node class?" % self.customCommandClass,
                                    NodeException)
        customcmd = self.customCommandClass(host=self.hostname, command=command)
        return customcmd

    def _getQuattorPath(self):
        """Gets and checks the quattor path of this node"""
        path = os.path.join(get_config('QUATTOR_PATH'), get_config('QUATTOR_FILES_TPL') %
                            {'nodeid': self.nodeid, 'clustername': self.clustername})

        if not os.path.exists(path):
            self.log.raiseException("No file found for node %s in %s" % (self, path), NodeException)
        return path

    def _getQuattorElementFromXML(self, xpath, path):
        """
        get quattor files and parse the xml, and return the content
        of a given xpath
        """
        #parse xml
        doc = libxml2.parseFile(path)
        ctxt = doc.xpathNewContext()
        res = ctxt.xpathEval(xpath)
        if len(res) > 0:
            content = res[0].getContent()
        else:
            content = ""
        self.log.debug("element %s: %s found for %s" % (xpath, content, self))
        doc.freeDoc()
        ctxt.xpathFreeContext()
        return content

    def _getQuattorElementFromJSON(self, jsonpath, path):
        """
        Get quattor files and parse the json and return the content
        of a given json path.
        """
        self.log.debug("jsonpath: %s" % str(jsonpath))
        if "gz" in path:
            path = gzip.open(path)
        out = json.load(path)
        for x in jsonpath.split(","):
            out = out[x.strip()]
        return out

    def _getLocation(self):
        """
        find location,chassis of this node using quattor
        """
        path = self._getQuattorPath()
        filename = path.split("/")[-1]
        if "xml" in filename:
            location = self._getQuattorElementFromXML(get_config("LOCATION_XPATH"), path)
        elif "json" in filename:
            location = self._getQuattorElementFromJSON(get_config("LOCATION_JSON"), path)

        self.log.debug("location: %s" % location)

        content1 = re.search(get_config("QUATTOR_LOCATION_STRING_REGEX"), location)

        if len(location) < 1 or not content1:
            self.log.debug("No chassis and slot location found for node %s in %s" % (self, get_config("QUATTOR_PATH")))
            return location, "None"

        #parse  content

        values1 = content1.groupdict()
        chassis = int(values1['chassis'])
        slot = int(values1['slot'])
        chassisname = get_config("CHASISNAME_TPL") % {'chassisname': chassis, 'clustername': self.clustername}

        return slot, chassisname

    def getSlot(self):
        """
        return the slot number of this node
        """
        self.log.debug("getslot called on %s" % self)
        if not self.slot and not self.chassisname:
            self.slot, self.chassisname = self._getLocation()
        elif not self.slot:
            self.slot, _ = self._getLocation()
        return self.slot

    def getChassis(self):
        """
        return the chassisname number of this node
        """
        self.log.debug("getchassis called on %s" % self)
        if not self.slot and not self.chassisname:
            self.slot, self.chassisname = self._getLocation()
        elif not self.chassisname:
            _, self.chassisname = self._getLocation()
        return self.chassisname

    def getMaster(self):
        """
        returns a master of this node
        """
        self.log.debug("getmaster called on %s" % self)
        return self.masternode

    def __repr__(self):
        return self.nodeid


class CompositeNode(Node):
    """
    implementation of Node
    a compositenode can contain multiple nodes and delegate calls to them
    """

    def __init__(self, clustername=None, masternode=None, nodeid=None):
        Node.__init__(self, nodeid, clustername, masternode)  # we're not a real node, so no id
        self.nodes = {}
        self.threads = None

    def __str__(self):
        """
        get a string representation of a composite node
        """
        if self.getNodes():
            return str([str(node) for node in self.getNodes()])
        else:
            return "Empty CompositeNode"

    def doIt(self, threaded=True, group_by_chassis=False):
        """
        do everything that has been queued now
        this will start a new thread for every node
        unless threaded = False is given
        or alternatively if group_by_chassis is True only one thread is started per chassis.
        """
        #threading here!
        out = []
        if threaded:
            if group_by_chassis:
                    for node in self._doThreading("doIt", args={'threaded': False}, group_by_chassis=group_by_chassis):
                        self.log.debug("adding output of doit for %s" % str(node[1]))
                        out.extend(node[1])
            else:
                out = self._doThreading("doIt", group_by_chassis=group_by_chassis)
        else:
            for node in self.getNodes():
                out.append([node, node.doIt()])

        return out

        #avg of 3 runs
        #threaded
        #[root@gastly manage]# time python manage.py -a --pbsmomstatus
        #real    0m12.032s
        #user    0m9.928s
        #sys    0m0.399s
        #non threaded
        #[root@gastly manage]# time python manage.py -a --pbsmomstatus --non_threaded
        #real    0m25.367s
        #user    0m9.551s
        #sys    0m0.160s

    def _getLocation(self):
        """
        no such thing for a compositenode
        """
        return None, None

    def showCommands(self):
        """
        shows a list of commands to be run when doIt is called
        """
        return ["""%s:%s""" % (node.getid(), node.showCommands()) for node in self.getNodes()]

    def add(self, node):
        """
        add a node to this composite node
        """
#        if node.__class__.__name__ == self.__class__.__name__:
#            raise TypeError("No CompositeNode expected, use union if you want to add two compositnodes toghether")
        self.nodes[node.getid()] = node

    def get(self, nodeid):
        """
        returns the node with given id
        """
        try:
            node = self.nodes[nodeid]
        except KeyError:
            raise NodeException("could not find node %s" % nodeid)
        return node

    def contains(self, nodeid):
        """
        returns true if this compositenode contains a given nodeid, false if it does not.
        """
        try:
            self.get(nodeid)
            return True
        except NodeException:
            return False

    def getNodes(self):
        """
        returns a set of nodes in this compositenode
        sorted by name
        """
        return self._sorted()

    def union(self, compositenode):
        """
        join 2 Compositenodes, making sure the resulting node doesn't contain duplicates
        """
        if not compositenode.__class__.__name__ == self.__class__.__name__:
            raise TypeError("CompositeNode expected")
        #add all nodes from the new compositenode to our nodes
        #don't do duplicates
        newnodes = compositenode.getNodes()

        for node in newnodes:
            if not node.getid() in self.nodes:
                self.add(node)

    def _sorted(self):
        """
        returns a sorted list of nodes
        """
        keys = self.nodes.keys()
        keys.sort()
        sortedl = map(self.nodes.get, keys)
        self.log.debug("sorted keys: %s" % sorted)
        return sortedl

    def getStatus(self, forced=False, threaded=True, group_by_chassis=False):
        """
        overwrites getstatus from nodes
        """
        self.log.debug("getting statuses from %s" % self)
        statusses = []
        if not self.status or forced:
            if threaded:
                if group_by_chassis:
                    for node in self._doThreading("getStatus", args={'threaded': False}, group_by_chassis=group_by_chassis):
                        self.log.debug("adding status for %s" % str(node[1]))
                        statusses.extend(node[1])
                else:
                    statusses = self._doThreading("getStatus", group_by_chassis=group_by_chassis)

            else:
                for node in self.getNodes():
                    statusses.append([node, node.getStatus()])
        self.status = statusses
        return self.status

    def _doThreading(self, method, args=None, group_by_chassis=False):
        """
        give this method a methodname and optional arguments
        it will perform it threaded on all
        nodes in this compositenode
        If group_by_chassis is given only one thread per chassis is started (default False)
        """
        if self.threads:
            self.log.raiseException("Trying to do 2 threaded operations at the same time,",
                                    " this is not allowed!")
        self.threads = []
        outputs = []
        #creating threads and getting results as discussed here: http://stackoverflow.com/questions/3239617/how-to-manage-python-threads-results
        if group_by_chassis:
            group = self.getNodesPerChassis()
        else:
            group = self
        for node in group.getNodes():
            #commands are ran in parrallel, but serial on each node
            #TODO (high): group by chassis to avoid overloading!
            out = []
            self.log.debug("running %s on %s with args: %s" % (method, node, args))
            t, out = _dothreading(node, method, args)
            #TODO: use a thread pool?
            self.threads.append([t, out])
            t.start()
        for t, out in self.threads:
            #TODO: (low) print progress? http://stackoverflow.com/questions/3160699/python-progress-bar
            t.join()
            # get result from each thread and append it to the result here
            self.log.debug("thread %s on node %s completed, result: %s" % (t, out[0], out[1]))
            if out[2]:
                self.log.warning("thread %s on node %s completed with an error: %s" %
                                 (t, out[0], out[2]))
            outputs.append(out)
        self.threads = None  # delete threads
        return outputs

    def ledOn(self):
        """
        schedule to turn on the location led on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.ledOn())
        self.log.debug("ledOn on compositenode returned %s" % statusses)
        return statusses

    def ledOff(self):
        """
        schedule to turn on the location led on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.ledOff())
        self.log.debug("ledOff on compositenode returned %s" % statusses)
        return statusses

    def poweroff(self):
        """
        schedule poweroff on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.softpoweroff())
        self.log.debug("softpoweroff on compositenode returned %s" % statusses)
        return statusses

    def powercut(self):
        """
        schedule powercut on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.powercut())
        self.log.debug("poweroff on compositenode returned %s" % statusses)
        return statusses

    def softreboot(self):
        """
        schedule a softreboot on all nodes in this compositenode
        a soft reboot will be a reset signal from the bmc to the motherboard
        or a reboot command executed in a shell for devices with limited bmc features.
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.softreboot())
        self.log.debug("softreboot on compositenode returned %s" % statusses)
        return statusses

    def reboot(self):
        """
        schedule reboot on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.reboot())
        self.log.debug("reboot on compositenode returned %s" % statusses)
        return statusses

    def poweron(self):
        """
        schedule reboot on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.poweron())
        self.log.debug("poweron on compositenode returned %s" % statusses)
        return statusses

    def setonline(self):
        """
        run setonline on all nodes in this compositenode
        """
        nodeonlinelist = []
        for node in self.getNodes():
            nodeonlinelist.append(get_config('NODENAME_TPL') % {'nodeid': node.nodeid, 'clustername': node.clustername})
        if len(nodeonlinelist) < 1:
            self.log.raiseException("No nodes selected to set online", NodeException)
        master = self.getMaster()
        statusses = []
        statusses.append(master.setonline(nodeonlinelist))
        self.log.debug("setonline on compositenode returned %s" % statusses)
        return statusses

    def setoffline(self):
        """
        run setoffline on all nodes in this compositenode
        """
        nodeofflinelist = []
        for node in self.getNodes():
            nodeofflinelist.append(get_config('NODENAME_TPL') % {'nodeid': node.nodeid, 'clustername': node.clustername})
        if len(nodeofflinelist) < 1:
            self.log.raiseException("No Nodes selected to set offline")
        master = self.getMaster()
        statusses = []
        statusses.append(master.setoffline(nodeofflinelist))
        self.log.debug("setoffline on compositenode returned %s" % statusses)
        return statusses

    def pbsmomstatus(self):
        """
        schedule pbsmomstatus on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.pbsmomstatus())
        self.log.debug("pbsmomstatus on compositenode returned %s" % statusses)
        return statusses

    def pbsmomrestart(self):
        """
        schedule pbsmomrestart on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.pbsmomrestart())
        self.log.debug("pbsmomrestart on compositenode returned %s" % statusses)
        return statusses

    def pbsmomstop(self):
        """
        schedule pbsmomstop on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.pbsmomstop())
        self.log.debug("pbsmomstop on compositenode returned %s" % statusses)
        return statusses

    def pbsmomcleanup(self):
        """
        schedule pbsmom cleanup on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            statusses.append(node.pbsmomcleanup())
        self.log.debug("pbsmomcleanup on compositenode returned %s" % statusses)
        return statusses

    def fixdownonerror(self):
        """
        run fixdownonerror on all nodes in this compositenode
         - remove all healtscripts on the nodes
         - clear the message on the nodes now
        """
        nodelist = []
        statusses = []
        for node in self.getNodes():
            nodelist.append(get_config('NODENAME_TPL') % {'nodeid': node.nodeid, 'clustername': node.clustername})
            statusses.append(node.fixdownonerror())
        if len(nodelist) < 1:
            self.log.raiseException("No nodes selected to set online", NodeException)
        self.log.debug("fixdownonerror on compositenode returned %s" % statusses)
        return statusses

    def runCustomCmd(self, command):
        """
        schedule a custom command to be run on all nodes in this compositenode
        """
        statusses = []
        for node in self.getNodes():
            tcommand = node._createCustomCommand(command)
            statusses.append(node.runCustomCmd(tcommand))
        self.log.debug("runCustomCmd on compositenode returned %s" % statusses)
        return statusses

    def _filterdict(dict, function):
        """
        filter like method for a dict
        this method is static
        and will return a new composite node
        with in it all the nodes in the given dict for which the given function returns true
        when called upon it
        """
        new = CompositeNode()
        for i in dict.values():
            if function(i):
                new.add(i)
        return new
    _filterdict = staticmethod(_filterdict)

    def getDownNodes(self):
        """
        returns a compositenode with all the nodes in this one
        that are down
        """
        return CompositeNode._filterdict(self.nodes, Node.isdown)

    def getOfflineNodes(self):
        """
        returns a compositenode with all offline nodes from this compositenode in it
        """
        return CompositeNode._filterdict(self.nodes, Node.isoffline)

    def getIdleNodes(self):
        """
        returns a compositenode with all idle nodes from this compositenode in it
        """
        return CompositeNode._filterdict(self.nodes, Node.isidle)

    def getNodesPerChassis(self):
        """
        returns  a compositenode with compositenodes containing nodes grouped per chassis
        """
        self.log.debug("getNodesPerChassis called on %s" % (self))
        groups = CompositeNode()
        for node in self.getNodes():
            self.log.debug("getNodesPerChassis: calling getchassis")
            chassis = node.getChassis()
            if not groups.contains(chassis):
                groups.add(CompositeNode(nodeid=chassis))
            groups.get(chassis).add(node)

        self.log.debug("getting nodes per chassis %s" % (groups))
        return groups

    def getNodesFromChassis(self, chassis):
        """
        returns a compositenode with all nodes from a certain chassis in it
        """
        self.log.debug("getNodesFromChassis called on %s" % (self))
        new = CompositeNode()
        for node in self.getNodes():
            self.log.debug("getNodesFromChassis: calling getchassis")
            if node.getChassis() == chassis:
                new.add(node)

        self.log.debug("getting nodes from chassis %s: %s" % (chassis, new))
        return new

    def getMaster(self):
        """
        returns a master of the first node in this compositenode
        """
        return self.getNodes()[0].getMaster()


## helper methods for multithreading
def _threadingHandler(node, result, method, args):
    """
    calls a method on all nodes, in a threaded way

    this will return an array of
     - node
     - output of the method on the node
     - possibly errors

    This is intended to be run in a new thread
    """
    # Modify existing object result
    status = None
    error = None
    try:
        nodemethod = getattr(node, method)  # get the method from the node
        if args:
            status = nodemethod(**args)  # call it
        else:
            status = nodemethod()

        fancylogger.getLogger("_threadingNodeHandler").debug("%s from %s: %s" %
                                                             (method, node, status))
    except Exception, e:
        error = e
    fancylogger.getLogger("_threadingNodeHandler").debug("%s from %s: %s" %
                                                         (method, node, status))
    result.append(node)
    result.append(status)
    result.append(error)
    return result


def _dothreading(node, method, args):
    """
    static function to be used for threading of nodestatusses
    give this method a node, a function and arguments,
     and it will run it as a new thread and return the results
    this will the output like in _threadingNodeHandler

    as explained here
    http://stackoverflow.com/questions/3239617/how-to-manage-python-threads-results
    """
    result = []
    thread = threading.Thread(target=_threadingHandler, args=(node, result, method, args))
    return thread, result


class WorkerNode(Node):
    """
    default implementation of a worker node
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        #this is a class, the others should be real commands
        self.statusCommand = FullStatusCommand(self.hostname, masternode=self.getMaster())

        self.pbsmomstatusCommand = PbsmomCommand(self.hostname, "status")
        self.pbsmomstopCommand = PbsmomCommand(self.hostname, "stop")
        self.pbsmomrestartCommand = PbsmomCommand(self.hostname, "restart")
        self.pbsmomcleanupCommand = PbsmomCleanupCommand(self.hostname, self.getMaster().nodeid)
        self.fixdownonerrorCommand = FixDownOnErrorCommand(self.hostname)


class SpecialNode(Node):
    _special_node = True  # allow checking for speciality
    """
    implementation of a special node
    these nodes print out extra warnings when created
    we don't want to do something on these by accident
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        self.log.debug("Creating a special node: %s.%s" % (nodeid, clustername))

### actual implementations

        #these first 2 not for defaultnodes
#        #self.customCommandClass =
#        #self.statusCommand =
#        self.poweronCommand =
#        self.poweroffCommand =
#        self.rebootCommand =
#        self.pbsmomstopCommand =
#        self.pbsmomrestartCommand =
#        self.pbsmomcleanupCommand =


class MasterNode(SpecialNode):
    """
    this class implements a masternode
    extended from node
    """
    def __init__(self, nodeid, clustername):
        """
        constructor
        """
        SpecialNode.__init__(self, nodeid, clustername, None)
        self.nodestates = None
        self.PBSStateCommand = PBSStateCommand(self.hostname)
        self.nodestates = None
        self.statusCommand = MasterStatusCommand(self.hostname)

        self.customCommandClass = SshCommand  # this is a class, the others should be real commands
        self.setOnlineCommand = SetOnlineMasterCommand(self.hostname)
        self.setOfflineCommand = SetOfflineMasterCommand(self.hostname)

        #no such commands
        self.pbsmomstatusCommand = TestCommand("No pbsmom on the masters!")
        self.pbsmomstopCommand = TestCommand("No pbsmom on the masters!")
        self.pbsmomrestartCommand = TestCommand("No pbsmom on the masters!")
        self.pbsmomcleanupCommand = TestCommand("No pbsmom on the masters!")
        self.fixdownonerrorCommand = TestCommand("fixdownonerror is not run on a master")
        #cheduling commands
        self.pauseSchedulerCommand = MoabPauseCommand(self.hostname)
        self.resumeSchedulerCommand = MoabResumeCommand(self.hostname)
        self.restartSchedulerCommand = MoabRestartCommand(self.hostname)

        #No set on or offline commands in masternodes
        #set this depending on what type of node this is

#        self.poweronCommand =
#        self.poweroffCommand =
#        self.rebootCommand =

    def setonline(self, nodelist):
        """
        Run setonline on the master
        """
        self.setOnlineCommand.setNodeList(nodelist)
        self._adcommand(self.setOnlineCommand)

    def setoffline(self, nodelist):
        """
        Run setoffline on the master
        """
        self.setOfflineCommand.setNodeList(nodelist)
        self._adcommand(self.setOfflineCommand)

    def getNodeStates(self):
        """
        returns the states of all nodes owned by this masternode
        """
        if not self.nodestates:
            self.nodestates, err = self.PBSStateCommand.run()
            self.log.debug("got pbsStatuses:%s" % self.nodestates)
        return self.nodestates

    def getPbsStatusForNode(self, nodeid):
        """
        get the status of this node
        as reported by pbsmon
        use the node.DOWN etc constants (DOWN,OFFLINE and IDLE are defined by default)
        """
        out = None
        err = None
        try:
            out = self.getNodeStates()[nodeid]
        except KeyError:  # node not found in pbsStats
            self.log.warning("unable to get PBSStatus for %s from %s" % (nodeid, self.nodeid))
            self.log.debug(traceback.format_exc())
            err = "PbsStatus for %s not found on %s" % (nodeid, self.nodeid)
        return out, err

    def getWorkerNodeIds(self):
        """
        return the workernode id's for this masternode
        """
        return self.getNodeStates().keys()

    def getMaster(self):
        """
        returns a master of this node
        """
        return self

    def pauseScheduler(self):
        """
        pauses the cheduler on a cluster
        """
        self.log.debug("scheduling the scheduler to pause")
        self._adcommand(self.pauseSchedulerCommand)

    def resumeScheduler(self):
        """
        resume the cheduler on a cluster
        """
        self.log.debug("scheduling the scheduler to resume")
        self._adcommand(self.resumeSchedulerCommand)

    def restartScheduler(self):
        """
        restarts the cheduler on a cluster
        """
        self.log.debug("scheduling the scheduler to restart")
        self._adcommand(self.restartSchedulerCommand)

    def __repr__(self):
        return """%s("%s","%s")""" % (self.__class__.__name__, self.nodeid,
                                      self.clustername)


class StorageNode(SpecialNode):
    """
    storage node implementation
    """
    #TODO (later) #466 implement
    def __init__(self, nodeid, clustername):
        SpecialNode.__init__(self, nodeid, clustername, None)


class BladeNode(Node):
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)

        self.log.debug("creating Bladenode")
        self.slot = self.getSlot()
        self.shassishost = get_config('CHASIS_HOST_TPL') % {'chasisname': self.getChassis(),
                                                            'clustername': self.clustername}
        self.immname = self.chassisname
        self.immmonitoring = get_config('ICINGA_BLADE_IMM_TPL') % {
            'chassisname': self.chassisname,
            'clustername': self.clustername,
        }

        self.softpoweroffCommand = BladeSoftPoweroffCommand(chassisname=self.shassishost,
                                                            slot=self.slot)
        self.poweroffCommand = BladePoweroffCommand(chassisname=self.shassishost, slot=self.slot)
        self.poweronCommand = BladePoweronCommand(chassisname=self.shassishost, slot=self.slot)
        self.rebootCommand = BladeRebootCommand(chassisname=self.shassishost, slot=self.slot)
        self.statusCommand = FullBladeStatusCommand(host=self.hostname,
                                                    masternode=self.getMaster(),
                                                    chassisname=self.shassishost,
                                                    slot=self.slot)
        self.ledoffcommand = NotSupportedCommand("ledoff")
        self.ledoncommand = NotSupportedCommand("ledon")


class BladeWorkerNode(BladeNode, WorkerNode):
    """
    extension of the Node class
    to do some Blade specific things
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        BladeNode.__init__(self, nodeid, clustername, masternode)


class BladeMasterNode(BladeNode, MasterNode):
    """
    extension of the Node class
    to do some Blade specific things
    """
    def __init__(self, nodeid, clustername):
        MasterNode.__init__(self, nodeid, clustername)
        BladeNode.__init__(self, nodeid, clustername, nodeid)


class ImmNode(Node):
    """
    extension of the Node class
    to do some Imm specific things
   """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        self.log.debug("creating ImmNode")
        host = self.hostname
        adminhost = self.immname
        self.immmonitoring = get_config('ICINGA_IDPX_IMM_TPL') % {
            'nodeid': self.nodeid,
            'clustername': self.clustername,
        }
        self.statusCommand = FullImmStatusCommand(host, adminhost, self.getMaster())
        self.softpoweroffCommand = ImmSoftPoweroffCommand(adminhost)
        self.poweronCommand = ImmPoweronCommand(adminhost)
        self.poweroffCommand = ImmPoweroffCommand(adminhost)
        self.rebootCommand = ImmRebootCommand(adminhost)
        self.softrebootCommand = ImmSoftRebootCommand(adminhost)
        self.ledoffcommand = NotSupportedCommand("ledoff")
        self.ledoncommand = NotSupportedCommand("ledon")


## Actual node implementations

class ImmWorkerNode(ImmNode, WorkerNode):
    """
    implements a ipdx worker node
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        ImmNode.__init__(self, nodeid, clustername, masternode)


class ImmStorageNode(ImmNode, StorageNode):
    """
    implements a ipdx storage node
    """
    def __init__(self, nodeid, clustername):
        StorageNode.__init__(self, nodeid, clustername)
        ImmNode.__init__(self, nodeid, clustername, None)


class ImmMasterNode(ImmNode, MasterNode):
    """
    implements a ipdx master node
    """
    def __init__(self, nodeid, clustername):
        MasterNode.__init__(self, nodeid, clustername)
        ImmNode.__init__(self, nodeid, clustername, nodeid)


class CuboneWorkerNode(BladeNode, WorkerNode):
    """
    this class implements a node for the cubone cluster
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        BladeNode.__init__(self, nodeid, clustername, masternode)
#        self.poweronCommand = TestCommand("poweron on %s.%s" % (nodeid, clustername))
#        self.poweroffCommand = TestCommand("poweroff on %s.%s" % (nodeid, clustername))
#        self.rebootCommand = TestCommand("reboot on %s.%s" % (nodeid, clustername))


class CuboneMasterNode(BladeNode, MasterNode):
    """
    implements a cubone master node
    """
    def __init__(self, nodeid, clustername):
        MasterNode.__init__(self, nodeid, clustername)
        BladeNode.__init__(self, nodeid, clustername, self)


class DracNode(Node):
    """
    implementation of a drac node
    - r610 of r710
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        host = self.hostname
        adminhost = self.immname
        self.statusCommand = DracFullStatusCommand(host, adminhost, self.getMaster())
        self.poweronCommand = DracPoweronCommand(adminhost)
        self.poweroffCommand = DracPoweroffCommand(adminhost)
        self.rebootCommand = DracRebootCommand(adminhost)
        #self.softrebootCommand = DracSoftRebootCommand(adminhost)
        self.ledoffcommand = NotSupportedCommand("ledoff")
        self.ledoncommand = NotSupportedCommand("ledon")


class DracWorkerNode(DracNode, WorkerNode):
    """
    implementation of a worker node
    - r610 of r710
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        DracNode.__init__(self, nodeid, clustername, masternode)


class DracMasterNode(DracNode, MasterNode):
    """
    implementation of a drac master node
    - r610
    """
    def __init__(self, nodeid, clustername):

        MasterNode.__init__(self, nodeid, clustername)
        DracNode.__init__(self, nodeid, clustername, self)


class IpmiNode(Node):
    """
    Implementation of a node using the ipmi commands
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        adminhost = self.immname
        hostname = self.hostname
        self.statusCommand = IpmiFullStatusCommand(hostname, adminhost, self.getMaster())
        self.poweronCommand = IpmiPoweronCommand(adminhost)
        self.poweroffCommand = IpmiPoweroffCommand(adminhost)
        self.softpoweroffCommand = IpmiSoftPoweroffCommand(adminhost)
        self.rebootCommand = IpmiRebootCommand(adminhost)
        self.ledoffcommand = NotSupportedCommand("ledoff")
        self.ledoncommand = NotSupportedCommand("ledon")


class IpmiMasterNode(IpmiNode, MasterNode):
    """
    Implementation of a node using the ipmi commands
    """
    def __init__(self, nodeid, clustername, masternode):
        MasterNode.__init__(self, nodeid, clustername)
        IpmiNode.__init__(self, nodeid, clustername, self)


class IpmiWorkerNode(IpmiNode, WorkerNode):
    """
    Implementation of a node using the ipmi commands
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        IpmiNode.__init__(self, nodeid, clustername, masternode)


class DMTFSMASHCLPNode(Node):
    """
    Implementation of a node using the DMTF SMASH CLP
    (Distributed Management Task Force,
    Systems Management Architecture for Server Hardware,
    Command Line Protocol)
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        self.ledoffcommand = DMTFSMASHCLPLEDOffCommand(self.immname)
        self.ledoncommand = DMTFSMASHCLPLEDOnCommand(self.immname)


class DMTFSMASHCLPIpmiNode(DMTFSMASHCLPNode, IpmiNode):
    """
    Implementation of a worker node supporting both ipmi and DMTFSMASHCLP
    """
    def __init__(self, nodeid, clustername, masternode):
        DMTFSMASHCLPNode.__init__(self, nodeid, clustername, masternode)
        IpmiNode.__init__(self, nodeid, clustername, masternode)


class DMTFSMASHCLPIpmiWorkerNode(DMTFSMASHCLPIpmiNode, WorkerNode):
    """
    Implementation of a workernode supporting both ipmi and DMTFSMASHCLP
    """
    def __init__(self, nodeid, clustername, masternode):
        WorkerNode.__init__(self, nodeid, clustername, masternode)
        DMTFSMASHCLPIpmiNode.__init__(self, nodeid, clustername, masternode)


class DMTFSMASHCLPIpmiMasterNode(DMTFSMASHCLPIpmiNode, MasterNode):
    """
    Implementation of a masternode supporting both ipmi and DMTFSMASHCLP
    """
    def __init__(self, nodeid, clustername):
        MasterNode.__init__(self, nodeid, clustername)
        DMTFSMASHCLPIpmiNode.__init__(self, nodeid, clustername, self)


class TestNode(Node):
    """
    implementation of node, used for testing
    """
    def __init__(self, nodeid, clustername, masternode):
        Node.__init__(self, nodeid, clustername, masternode)
        self.statusCommand = FullStatusCommand(host=self.hostname,
                                               masternode=self.getMaster())
        self.softpoweroffCommand = TestCommand("softpoweroff on %s.%s" % (nodeid, clustername))
        self.poweronCommand = TestCommand("poweron on %s.%s" % (nodeid, clustername))
        self.poweroffCommand = TestCommand("poweroff on %s.%s" % (nodeid, clustername))
        self.rebootCommand = TestCommand("reboot on %s.%s" % (nodeid, clustername))
        self.softrebootCommand = TestCommand("softreboot on %s.%s" % (nodeid, clustername))
        self.pbsmomstopCommand = TestCommand("pbsmomstop on %s.%s" % (nodeid, clustername))
        self.pbsmomrestartCommand = TestCommand("pbsmomrestart on %s.%s" % (nodeid, clustername))
        self.pbsmomcleanupCommand = TestCommand("pbsmomcleanup on %s.%s" % (nodeid, clustername))
        self.customCommandClass = TestCommand
        self.ledoffcommand = TestCommand("ledoff on %s.%s" % (nodeid, clustername))
        self.ledoncommand = TestCommand("ledon on %s.%s" % (nodeid, clustername))


### Exceptions

class NodeException(Exception):
    """
    Node Exception
    Thrown by a node
    """
    pass
