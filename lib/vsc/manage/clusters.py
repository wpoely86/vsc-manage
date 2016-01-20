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
"""
Created on Oct 17, 2011

@author: jens

This module contains cluster classes

the Cluster class is the abstract class
To add real clusters extend this class in this file, and it will be automatically detected (based on the class name)

"""
import platform
import os
import re
from vsc.manage.nodes import CompositeNode, MasterNode, StorageNode, DracMasterNode, \
    CuboneWorkerNode, BladeWorkerNode, ImmMasterNode, ImmWorkerNode, \
    IpmiWorkerNode, DMTFSMASHCLPIpmiWorkerNode, DMTFSMASHCLPIpmiMasterNode, BladeMasterNode
from vsc.manage.managecommands import PBSStateCommand
from vsc.manage.config import get_config
from vsc.utils import fancylogger


class Cluster(object):
    """
    This class represents a cluster
    A cluster has a list of nodes in it
    A real cluster should extend this class and at least set the self.masterNodeClass and workerNodeClass
    this class should be an extensions of the Node class
    """
    def __init__(self):
        """
        constructor
        takes the name of the cluster to create
        """
        self.log = fancylogger.getLogger(self.__class__.__name__)
        self.workerNodeClass = None
        self.masterNodeClass = MasterNode
        self.storageNodeClass = None
        self.workernodes = None  # cache workernodes here
        self.masters = None
        self.storagenodes = None
        self.name = self.__class__.__name__
        self.master = None

    def __str__(self):
        return str(self.__class__.__name__)

    def getWorkerNodes(self, quattor=False):
        """
        returns all workernodes in this cluster
        if quattor is specified, the quattor dir will be used to look up nodes
        instead of running pbsmon on the master.
        """
        # get my nodes
        # TODO: get these from vsc.quattor
        if not self.workernodes:
            workernodes = CompositeNode()
            workerids = self._getWorkerNodeIds(quattor=quattor)  # get ids
            master = self.getMaster()
            for nodeid in workerids:
                node = self.workerNodeClass(nodeid, self.name, master)
                workernodes.add(node)
            self.workernodes = workernodes
        return self.workernodes

    def getStorageNodes(self):
        """
        returns all storage nodes in this cluster
        """
        # TODO: get these from vsc.quattor
        if not self.storagenodes:
            storagenodes = CompositeNode()
            storageids = self._getStorageNodeIds()
            for nodeid in storageids:
                node = self.storageNodeClass(nodeid, self.name)
                storagenodes.add(node)
            self.storagenodes = storagenodes
        return self.storagenodes

    def _getMasters(self):
        """
        returns the master(s) from this cluster as a list
        """
        # TODO: get these from vsc.quattor
        if not self.masters:
            masterids = self._getMasterNodeIds()
            masternodes = CompositeNode()
            for masterid in masterids:
                masternodes.add(self.masterNodeClass(masterid, self.name))
            self.masters = masternodes
        return self.masters

    def _getNodeIds(self, regex):
        """
        returns a list of id's. based on a regex
        this regex should have a named group id
        and represents a file in the quattor dir
        """
        if not os.path.exists(get_config("QUATTOR_PATH")):
            self.log.raiseException("Path %s not found, is this not a quattor server?" % get_config("QUATTOR_PATH"),
                                    QuattorException)
        filelistAll = os.listdir(get_config("QUATTOR_PATH"))
        self.log.debug("matching files for regex %s" % regex.pattern)
        nodenames = []
        for filename in filelistAll:
            # The compiled versions of the most recent patterns passed to re.match(), re.search() or re.compile() are
            # cached so programs that use only a few regular expressions at a time needn't worry about compiling regular
            # expressions.
            m = regex.match(filename)
            if m:
                nodenames.append(m.group('id'))
                self.log.debug("matched filename: %s" % filename)
        # we might have doubles
        nodenames = sorted(set(nodenames))
        return nodenames

    def _getWorkerNodeIdsFromQuattor(self):
        """
        get a set of all node id's in this cluster, using the quattor dir naming
        """
        # create regex from template
        template = get_config("QUATTOR_FILES_TPL") % {"clustername": self.name,
                                                      "nodeid": get_config("QUATTOR_NODEID_REGEX")}
        regex = re.compile(template)

        return self._getNodeIds(regex)

    def _getWorkerNodeIds(self, quattor=False):
        """
        returns a set of all node id's in this cluster,
        obtained by pbsnodes on one of the masters,
        or via quattor if this fails (TODO)
        or if quattor is True
        """
        if quattor:
            nodenames = self._getWorkerNodeIdsFromQuattor()
        else:
            master = self.getMaster()
            nodenames = master.getWorkerNodeIds()  # Try using -q instead of -a if you see this line.
            self.log.debug("worker node id's for %s: %s" % (self.name, str(nodenames)))
            if not nodenames:
                self.log.warning("No nodes found on %s, you might want to try '-q'" % (master))
        return nodenames

    def _getStorageNodeIds(self):
        """
        return a set of all storage node id's in this cluster
        """
        regex = re.compile(get_config("QUATTOR_FILES_TPL") % {'nodeid': get_config("QUATTOR_STORAGEID_REGEX"),
                                                              'clustername': self.name})
        nodenames = self._getNodeIds(regex)
        self.log.debug("storage id's for %s: %s" % (self.name, str(nodenames)))
        return nodenames

    def _getMasterNodeIds(self):
        """
        get a set of all master node ids in this cluster using the quattor dir
        """
        regex = re.compile(get_config("QUATTOR_FILES_TPL") % {'nodeid': get_config("QUATTOR_MASTERID_REGEX"),
                                                              'clustername': self.name})
        nodenames = self._getNodeIds(regex)
        self.log.debug("master id's for %s: %s" % (self.name, str(nodenames)))
        return nodenames

    def getNodesFromChassis(self, chassis, quattor=False):
        """
        returns all the workernodes from a certain chassis
        """
        # TODO: get these from vsc.quattor
        self.log.debug("selecting worker nodes from chassis: %s" % chassis)
        nodes = self.getAllNodes(quattor=quattor)
        return nodes.getNodesFromChassis(chassis)

    def getAllNodes(self, quattor=False):
        """
        returns all the nodes in this cluster
        (workernodes and masters)
        does not return storage!
        """
        self.log.debug("selecting all nodes (minus storage)")
        nodes = CompositeNode()
        nodes.union(self.getWorkerNodes(quattor=quattor))
        nodes.union(self._getMasters())
        self.log.debug("selected worker and master nodes: %s" % nodes)
        return nodes

    def getNode(self, nodeid):
        """
        returns the workernode in this cluster with the given id
        this bypasses pbsserver on master
        """
        return self.workerNodeClass(nodeid, self.__class__.__name__, self.getMaster())

    def getDownNodes(self):
        """
        return a compositenode with all down worker nodes in it
        """
        return self.getWorkerNodes().getDownNodes()

    def getOfflineNodes(self):
        """
        returns the offline worker nodes
        """
        return self.getWorkerNodes().getOfflineNodes()

    def getIdleNodes(self):
        """
        returns the idle worker nodes
        """
        return self.getWorkerNodes().getIdleNodes()

    def getMaster(self):
        """
        returns a master of this cluster
        This will first make sure the master is having a working pbs installation,
        and try the next one if this fails
        """
        # cache this function
        if self.master:
            return self.master

        masters = self._getMasters()
        if not masters:
            raise ClusterException("Could not get masterNode for %s, check your quattor configuration" % self.name)

        masters = masters.getNodes()
        if not masters:
            raise ClusterException("Could not get masterNode for %s, check your quattor configuration" % self.name)

        for master in masters:
            # check if this master gives us a valid pbsnodes response
            out, err = PBSStateCommand(master.hostname, get_config("COMMAND_FAST_TIMEOUT")).run()
            if not err:
                self.master = master
                return master
        self.log.warning("Cound not get a working master for %s, make sure pbs is working on it, will conitinue without"
                         "working master" % self.name)
        self.master = masters[0]
        return masters[0]

    # # factory methods for cluster
    # to add a new cluster just create a new class that extends the cluster class
    # see http://stackoverflow.com/questions/456672/class-factory-in-python
    # classmethod
    def _is_cluster_for(cls, name):
        """
        see if this class is the cluster with this name
        this is a classmethod
        """
        return cls.__name__ == name
    _is_cluster_for = classmethod(_is_cluster_for)

    # static method
    def getCluster(name):
        """
        static factory method, should be in Cluster class
        returns a cluster object of the given name
        """
        for cls in Cluster.__subclasses__():
            if cls._is_cluster_for(name):
                return cls()
        fancylogger.getLogger("clusters.getCluster").raiseException("No such cluster %s" % name, NoSuchClusterException)
    getCluster = staticmethod(getCluster)

    # static method
    def getDefaultCluster():
        """
        static method
        returns the default cluster, which is the cluster you are currently on.
        """
        # where are we?
        logger = fancylogger.getLogger("clusters.getDefaultCluster")
        hostname = platform.uname()[1].split(".")
        logger.debug("hostname: %s" % hostname)
        if len(hostname) < 2:
            logger.raiseException("Hostname is not a fqdn, could not guess clustername, set it on the command line with"
                                  " --cluster <clustername>", ClusterException)
        clustername = hostname[1]
        logger.debug("Detected cluster %s as default cluster" % clustername)
        return Cluster.getCluster(clustername)
    getDefaultCluster = staticmethod(getDefaultCluster)


# ## extensions of cluster
# add new cluster here
# TODO: get cluster configuration from config file, not here

# TODO: (medium) #469 allow for getting nodes and their commands from quattor
# create the cluster commands from quattor xml files
# instead of giving them here (or in the nodes file)
#
class shuppet(Cluster):
    """
    this class represents the shuppet cluster
    """
    group_by_chassis = False

    def __init__(self):
        """
        constructor
        sets the nodeclass
        """
        Cluster.__init__(self)
        self.workerNodeClass = ImmWorkerNode
        self.masterNodeClass = BladeMasterNode
        self.storageNodeClass = StorageNode

class raichu(Cluster):
    """
    this class represents the raichu cluster
    """
    def __init__(self):
        """
        constructor
        sets the nodeclass
        """
        Cluster.__init__(self)
        self.workerNodeClass = DMTFSMASHCLPIpmiWorkerNode  # hp gen8
        self.masterNodeClass = DMTFSMASHCLPIpmiMasterNode


class phanpy(Cluster):
    """
    this class represents the phanpy cluster (hp gen9)
    """
    def __init__(self):
        """
        constructor
        sets the nodeclass
        """
        Cluster.__init__(self)
        self.workerNodeClass = DMTFSMASHCLPIpmiWorkerNode  # hp gen9
        self.masterNodeClass = DMTFSMASHCLPIpmiMasterNode


class golett(phanpy, Cluster):
    """This class represents the golett cluster, it's equal to phanpy"""
    pass


class swalot(phanpy, Cluster):
    """This class represents the swalot cluster, it's equal to phanpy"""
    pass


class delcatty(Cluster):
    """
    this class represents the delcatty cluster
    """
    def __init__(self):
        """
        constructor
        sets the nodeclass
        """
        Cluster.__init__(self)
        self.workerNodeClass = IpmiWorkerNode  # c8220
        self.masterNodeClass = DracMasterNode


# ## exceptions
class QuattorException(Exception):
    """
    custom exception, thrown when the quattor dir could not be found
    """

    def __init__(self, message=None):
        """
        constructor, overwrites empty exception message with the quattor path
        """
        if not message:
            message = "Could not find quattor dir %s" % get_config("QUATTOR_PATH")
        Exception.__init__(self, message)


class ClusterException(Exception):
    """
    Cluster exception
    """
    pass


class NoSuchClusterException(Exception):
    """
    Cluster exception
    thrown when a non existing cluster is requested
    """
    pass
