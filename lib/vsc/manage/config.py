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
This module provides the option and config parsing for manage
"""
import os
from ConfigParser import NoSectionError
from vsc.utils.generaloption import GeneralOption


# Configfiles
# this one is shipped with the rpm
DEFAULT_CONFIGFILE = '/etc/manage_defaults.cfg'
# this one is if you want to overwrite some fo the the defaults with your own, without having to edit the original
CONFIGFILES = ["/etc/manage.cfg", os.path.expanduser("~/.local/manage.cfg")]

global CONFIG
CONFIG = {}
OPTIONS = None
LOGGER = None


def parseoptions():
    """
    Parses the options
    """
    # be as restrictive as possible
    # TODO: add softreboot, watch out, dracsoftreboot is actually stil pretty hard!
    # so implement properly
    # {longopt:(help_description,type,action,default_value,shortopt),}
    parser = ManageOptionParser(go_configfiles=[DEFAULT_CONFIGFILE] + CONFIGFILES,
                                go_mainbeforedefault=True,
                                go_prefixloggername=True)
    options = parser.options
    global LOGGER
    LOGGER = parser.log

    if options.poweroff and (options.poweron or options.hardreboot) or (options.poweron and options.hardreboot):
        parser.log.error("--hardreboot, --poweron and --poweroff are mutually exclusive")
    if options.restart and not options.forced:
        parser.log.error("You trying to restart the scheduler"
                         "without the --forced option, do you know what you are doing?")

    # TODO: (low) more options checking? - running without option doesn't show a usage flag?

    # args should be empty, since everything is optional
    if len(parser.args) > 1:
        parser.log.error("Invalid arguments")

    global CONFIG
    # parse constants
    try:
        for opt, val in parser.configfile_parser.items('raw_configs', raw=True):
            parser.log.debug("adding %s to config (from configfile) ", opt)
            CONFIG[opt.lower()] = val
    except NoSectionError:
        parser.log.error("Could not find the [raw_configs] section in the configfile, make sure at least %s is present",
                         DEFAULT_CONFIGFILE)

    global OPTIONS
    OPTIONS = parser.options


def get_config(name=None):
    """Returns the global config dict"""
    if OPTIONS is None:
        # the options needs to be parsed at least once
        # before get_config can be successfully ran
        parseoptions()

    global CONFIG
    if name is not None:
        try:
            config = CONFIG[name.lower()]
        except KeyError:
            try:
                config = CONFIG[name.upper()]
            except KeyError:
                LOGGER.raiseException("Error: Could not find configuration for '%s' or '%s', make sure it is in %s or"
                                      " is properly added in %s, or alternatively change the location of these config"
                                      " files in %s" % (name.lower(), name.upper(), DEFAULT_CONFIGFILE, CONFIGFILES,
                                                        __file__))

        # allow ~ or ~user to be used in paths
        if name.lower().endswith('_path'):
            config = os.path.expanduser(config)

        return config

    return CONFIG


def get_options():
    """Return the global options object"""
    if OPTIONS is None:
        # the options needs to be parsed at least once
        parseoptions()

    return OPTIONS


class Options(object):
    """
    dummy class
    you can set attributes here
    so you can create objects like the options object returned by optparse
    """
    def __init__(self):
        """
        provide some defaults
        """
        self.verbose = 2
        self.non_threaded = False
        self.test_run = False
        self.forced = False
        self.ack = None
        self.ack_service = None
        self.downtime = None
        self.comment = None
        # actions
        self.state = False
        self.poweron = False
        self.setonline = False
        self.setoffline = False
        self.hardreboot = False
        self.reboot = False
        self.pbsmomstatus = False
        self.pbsmomrestart = False
        self.pbsmomstop = False
        self.pbsmomcleanup = False
        self.fix_downonerror = False
        self.runcmd = None
        self.poweroff = False
        self.powercut = False
        self.ledon = False
        self.ledoff = False
        self.co = None
        # node selection
        self.storage = False
        self.cluster = None
        self.master = None
        self.chassis = None
        self.down = False
        self.worker = False
        self.quattor = True
        self.all_nodes = False
        self.imms = False
        self.idle = False
        self.offline = False
        self.node = ""
        # cluster actions
        self.pause = False
        self.resume = False
        self.restart = False


class ManageOptionParser(GeneralOption):
    """
    Optionparser for manage
    """

    def general_options(self):
        """Set the general options"""
        # general options
        general_optiongroup = {
            "verbose": ("Enable extra output, use -vv for even more output", None, "count", 0, 'v'),
            "forced": ("Included as a dummy protection. If a special node is selected, --forced is required as well",
                       None, "store_true", False, "f"),
            "test-run": ("Print what would be done, without actually doing anything", None, 'store_true', False, 't'),
            "non-threaded": ("Disable threading, do commands one by one", None, "store_true", False),
            "cluster": ("Specify the cluster to run on, When not specified, the script will attempt to detect the"
                        "current cluster. All operations can only affect one cluster at a time",
                        None, "store", None, "C")
        }
        self.add_group_parser(general_optiongroup, ("General Options", "General options for Manage"))

    def node_options(self):
        """Set the node selection options"""
        # node selection
        descr = ("Node selection", "Use these to select a node "
                 "or a group of nodes. All selections will be added up. "
                 "F.ex. -od will select all nodes that are either down or offline")

        nodesel_group = {
            "idle": ("Select all free/idle nodes", None, "store_true", False, 'i'),
            "worker": ("Select all worker nodes", None, "store_true", False, 'a'),
            "down": ("Select all down nodes", None, "store_true", False),
            "offline": ("Select all offline nodes", None, "store_true", False, 'o'),
            "node": ("Select a specific node. Multiple worker nodes can be given separated by ',', no spaces."
                     "This will bypass pbs server. You can also specify a range of nodes, when separated by '-'. e.g."
                     "'node601,605-608,203-208", "string", "store", None, 'n'),
            "master": ("Select a master node WARNING: this will bypass the PBS server."
                       "Multiple nodes can be given separated by ',', no spaces.", "string", "store", None),
            "storage": ("Select this master", "string", "store", None),
            "chassis": ("Select all nodes in a chassis, as it is listed in quattor, e.g. mmodule01.gengar.gent/vsc"
                        "WARNING: this might also include masters", "string", "store", None),
            "quattor": ("Use quattor to select nodes instead of pbsnodes on the master."
                        " this might be faster, and also works if the master is offline."
                        " This option will be ignored when using the idle, down or offline node selection.",
                        None, "store_true", False, 'q'),
            "all-nodes": ("Select all servers, WARNING: THIS WILL INCLUDE MASTERS", None, "store_true", False),
        }
        self.add_group_parser(nodesel_group, descr)

    def action_options(self):
        """"Set the action options"""

        # action selection
        # TODO (high) don't reboot anything where the sheduling is on
        descr = ("Node actions", "Use these to select the sepecific action you want to do on the selected node(s)."
                 "You can select multiple actions. They will be run in the order as shown here.")

        actiongroup = {
            "state": ("State information (tcp, ssh, nodestate, power)."
                      "This will run instantly (on the master), no test-run here", None, "store_true", False, 's'),
            "setoffline": ("Set the selected nodes offline", None, "store_true", False),
            "setonline": ("Set the selected nodes online", None, "store_true", False),
            "pbsmomcleanup": ("Run pbs cleanupscripts", None, "store_true", False),
            "pbsmomstop": ("Stop pbs_mom on selected nodes", None, "store_true", False),
            "runcmd": ("Run a (bash) command on the selected nodes", "string", "store", None),
            "pbsmomstatus": ("gives the status of pbsmom on the selected nodes", None, "store_true", False),
            "poweroff": ("Power off the selected nodes in a clean way", None, "store_true", False),
            "powercut": ("Power off the selected nodes as soon as possible", None, "store_true", False),
            "poweron": ("Power on the selected nodes", None, "store_true", False),
            "reboot": ("Reboot the selected nodes in a clean way", None, "store_true", False),
            "hardreboot": ("Power cycle the selected nodes", None, "store_true", False),
            "pbsmomrestart": ("Restart pbs_mom on the selected nodes", None, "store_true", False),
            "ledon": ("Turn on the locator led of the selected nodes", None, "store_true", False),
            "ledoff": ("Turn off the locator led of the selected nodes", None, "store_true", False),
            "fix-downonerror": ("Fix the down on error status (for selected workernodes)", None, "store_true", False),
            "co": ("Run a quattor component on the selected nodes, e.g. spma,cron", "string", "store", None),
        }
        self.add_group_parser(actiongroup, descr)

    def clusteraction_options(self):
        """Set the clusteaction options"""

        # actions on a cluster
        descr = ("Cluster actions", "Use these to select the specific action you want to run on the selected cluster."
                 "These are run in the order as listed here")
        clusteractiongroup = {
            "pause": ("Pause the scheduler", None, "store_true", False, 'p'),
            "resume": ("Resume the scheduler", None, "store_true", False, 'r'),
            "restart": ("Restart the scheduler, Warning: will pass all jobs through GOLD before 1st rescheduling,"
                        "--force needed", None, "store_true", False),
        }
        self.add_group_parser(clusteractiongroup, descr)

    def monitoring_options(self):
        """Set the monitoring options"""
        # actions involving monitoring
        descr = ("Monitoring options", "Use these to enable notification of the monitoring service")
        monitoringgroup = {
            "ack": ("Acknowledge a problem with all selected nodes.", None, "store_true", False),
            "ack-service": ("Acknowledge a problem with a service on all selected nodes", "string", "store", None),
            "downtime": ("Schedule all selected nodes and it's services for a downtime (in hours)", "string", "store",
                         None),
            "comment": ("Set the comment for the acknowledgement or scheduled downtime", "string", "store", None),
            "imms": ("also select the imms of the selected nodes, only applies to acknowleding problems to monitoring",
                     None, "store_true", False),
        }
        self.add_group_parser(monitoringgroup, descr)
