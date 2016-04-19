#
# Copyright 2011-2016 Ghent University
#
# This file is part of vsc-manage,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Flemish Research Foundation (FWO) (http://www.fwo.be/en)
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
Created on Oct 18, 2011

@author: Jens Timmerman
'''
import os
import sys
import traceback
from vsc.install.testing import TestCase

# use the default shipped configfile
from vsc.manage import config
config.DEFAULT_CONFIGFILE = os.path.join(os.path.dirname(sys.argv[0]),'config/manage_defaults.cfg')
# get_options will initialize
config.get_options()


from vsc.manage.config import Options, get_config
from vsc.manage.manage import Manager
from vsc.manage.clusters import Cluster, NoSuchClusterException
from vsc.manage.managecommands import Command
from vsc.manage.nodes import NodeException, TestNode, CompositeNode


TEST_CLUSTER = 'shuppet'
TEST_NODE = 'node2201'

QUATTOR_PATH = os.path.join(os.path.dirname(sys.argv[0]),'test/profiles')
if not os.path.isdir(QUATTOR_PATH):
    raise Exception('Cannot find QUATTOR_PATH in %s (set VSC_MANAGE_QUATTOR_PATH envvar)' % QUATTOR_PATH)
config.CONFIG['QUATTOR_PATH'] = QUATTOR_PATH
config.CONFIG['QUATTOR_PATH'.lower()] = QUATTOR_PATH


class ManageTest(TestCase):

    # TODO: add tests for  options.pause  options.resume and options.restart

    def testSchedulerOptions(self):
        """
        test the cheduler options
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.pause = True
        Manager(opts)
        opts.resume = True
        Manager(opts)
        opts.pause = False
        opts.resume = True
        Manager(opts)
        Manager(opts).doit()
        opts.restart = True
        try:
            if Manager(opts).doit():
                self.fail("Scheduler restart ran without the --force option")
        except Exception, ex:
            self.fail("Scheduler restart failed with ex %s" % ex)
            print traceback.format_exc()

    def test_ClustersInQuator(self):
        """
        test if all clusters with a class implementing them are in quator
        """
        for cls in Cluster.__subclasses__():
            self.clustertest(cls.__name__)

    def clustertest(self, name):
        try:
            cluster = Cluster.getCluster(name)
        except NoSuchClusterException:
            self.fail("value error in getcluster, cluster %s has no class extending Cluster for it" % name)
        cluster.getWorkerNodes()
        try:
            cluster.getWorkerNodes()
        except Exception, e:
            self.fail("getting quattor results failed for cluster %s with: %s" % (name, e))

    def testUnknownClusters(self):
        """
        test if getCluster actually fails with an unknown cluster name
        """
        self.assertRaises(NoSuchClusterException, Cluster.getCluster, ("THIS_is_NOT a cluster name%$3"))

    def testClusterNames(self):
        """
        test if all clusternames have a class implementing them
        """
        if not os.path.exists(QUATTOR_PATH):
            self.fail("Path not found, check quattor path:%s" % QUATTOR_PATH)
        # get names from the files in the quattor dir
        clusternames = set([s.split('.')[1] for s in os.listdir(QUATTOR_PATH) if len(s.split('.')) > 1])
        for name in clusternames:
            # TODO: add support for non clustered devices: https://github.com/hpcugent/vsc-manage/issues/1
            # ignore unsupported 'clusters'
            if name not in ('ugent', 'gligar', 'muk', 'altaria', 'zorua', 'gigalith', 'gengar', 'cubone', 'hpc'):
                self.clustertest(name)

    def testManagerCreatorNodesFromChassis(self):
        """
        test the manager constructor with the chassis option
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.chassis = "61"
        Manager(opts)

    def testGroupByChassis(self):
        """
        test the group by chassis feature
        """
        pass

    def testManagerCreatorNodesFromID(self):
        """
        test the manager constructor with a nodename option
        """
        opts = Options()
        opts.cluster = TEST_CLUSTER
        opts.node = 'nosuchnodeid3234#%'
        opts.setonline = True

        try:
            Manager(opts)
            self.fail("manager didn't fail with unknown node selected")
        except NodeException:
            pass
        else:
            self.fail("manager didn't fail with a NodeException when an unknown node was selected")
        opts.node = 'node2201,201,magikarp'
        Manager(opts)
        opts.node = 'node2201-node2205'
        Manager(opts)
        opts.node = 'node2208,node2203-node2205,magikarp'
        Manager(opts)

    def testManagerCreatorNodeOptions(self):
        """
        test the manager constructor
        """
#        debug = True cluster = None chassis = None down = False all = False
#        idle = False offline = False node = ""
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        Manager(opts)  # should create a manager

        opts.down = True
        Manager(opts)  # should create a manager

        opts.idle = True
        Manager(opts)  # should create a manager

        opts.offline = True
        Manager(opts)  # should create a manager

        opts.master = "master7"
        Manager(opts)  # should create a manager

    def testManagerhasSpecials(self):
        """
        test on inclusion of special nodes
        """
        opts = Options()
        opts.cluster = TEST_CLUSTER

        manager = Manager(opts)
        self.assertFalse(manager.hasSpecials())
        opts.worker = True
        manager = Manager(opts)
        self.assertFalse(manager.hasSpecials())
        opts.all_nodes = True
        manager = Manager(opts)
        self.assertTrue(manager.hasSpecials())  # should have special nodes with force (the master)

        opts = Options()
        opts.cluster = TEST_CLUSTER
        opts.master = "master1"
        self.assertTrue(Manager(opts).hasSpecials())  # should create a manager

    # TODO: test for storage

    def testManagerSetOnlineOption(self):
        """
        test the setonline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.worker = True
        opts.setonline = True
        Manager(opts)

    def testManagerSetOnline(self):
        """
        test the setonline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = TEST_NODE
        opts.setonline = True
        Manager(opts).doit()

    def testManagerLEDs(self):
        """
        test the Ledon, ledoff and ledstatus option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = TEST_NODE
        opts.ledon = True
        Manager(opts).doit()
        # TODO: get led status and test if it's on
        opts.ledon = False
        opts.ledoff = True
        Manager(opts).doit()
        # TODO: get led status and test if it's off

    def testManagerTestrun(self):
        """
        test the setonline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.worker = True
        opts.testrun = True
        Manager(opts).doit()

    def testManagerSetOfflineOption(self):
        """
        test the setoffline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.worker = True
        opts.setoffline = True
        Manager(opts)

    def testManagerSetOffline(self):
        """
        test the setoffline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = TEST_NODE
        opts.setoffline = True
        Manager(opts).doit()

    def testAck(self):
        """
        test the setoffline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = 'node2201-node2208'
        opts.setoffline = True
        opts.ack = True
        Manager(opts)

    def testDowntime(self):
        """
        test the setoffline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = 'node2201-node2208'
        opts.setoffline = True
        opts.downtime = "2 m"
        Manager(opts)  # should fail
        opts.downtime = "2h"
        Manager(opts)

    def testAckService(self):
        """
        test the setoffline option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.node = 'node2201-node2208'
        opts.ack_service = "Swapping"
        Manager(opts)

    def testManagerPowercutOptions(self):
        """
        test the powercut option parameter
        """
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.worker = True
        opts.powercut = True
        Manager(opts)

    def testManagerQuattorOption(self):
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.quattor_nodes = True
        opts.runcmd = "echo hello"

    def testNoDefaultRuncmdOption(self):
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.quattor_nodes = True
        manager = Manager(opts)
        self.assertFalse(bool(manager.nodes.showCommands()))

    def testdoitOutput(self):
        """Test the consistency of the output of manager.doit"""
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.quattor_nodes = True
        opts.ledon = True
        manager = Manager(opts)
        manager.nodes = CompositeNode(timeout=1)
        # create a fake node
        testnode = TestNode('node111', 'localhost', None)
        # overwrite it's testcommand to be sure it times out
        testnode.ledoncommand = Command('sleep 3', timeout=1)
        manager.nodes.add(testnode)

        # make sure this works for multiple nodes
        testnode2 = TestNode('node112', 'localhost', None)
        # overwrite it's testcommand to be sure it times out
        testnode2.ledoncommand = Command('sleep 3', timeout=1)
        manager.nodes.add(testnode2)
        # parse actions again so they get applied on the new node
        manager.parseActions()
        out = manager.doit()
        # make sure this output is of a format we can handle
        errors = []
        for i in out:
            if len(i) > 1 and len(i[1]) > 0:
                for j in i[1]:  # second element is an array of [outputs of commands,errors]
                    self.assertEquals(j[1][0], None)
                    if j[1][1]:
                        self.assertEquals(j[1][1], 'command timed out')
                        errors.append(i[0])

        # actuall node should be in output, not just the name, because this is also used for printstatussee
        self.assertTrue(testnode in errors)
        self.assertTrue(testnode2 in errors)

    def testManagerCreatorActionOptions(self):
        """
        test the manager constructor
        """
#        debug = True cluster = None chassis = None down = False all = False
#        idle = False offline = False node = ""
        opts = Options()  # default options object
        opts.cluster = TEST_CLUSTER
        opts.quattor = True
        opts.all = True
        opts.forced = True
        opts.state = True
        manager = Manager(opts)
        manager.doit()
        opts.non_threaded = True
        manager = Manager(opts)
        opts.non_threaded = False
        manager = Manager(opts)
        manager.doit()

        opts.non_threaded = False
        opts.poweron = True
        Manager(opts).doit()

        opts.postpoweron = True
        Manager(opts)  # should create a manager

        opts.postpoweron = False
        opts.hardreboot = True
        Manager(opts)

        opts.hardreboot = False
        opts.softreboot = True
        Manager(opts)

        opts.all = False
        opts.worker = True
        opts.forced = False

        opts.pbsmomstatus = True
        Manager(opts).doit()

        opts.pbsmomrestart = True
        Manager(opts)  # should create a manager

        opts.pbsmomstop = True
        Manager(opts)  # should create a manager

        opts.pbsmomcleanup = True
        Manager(opts)  # should create a manager

        opts.runcmd = "echo hello"
        Manager(opts).doit()  # should create a manager
