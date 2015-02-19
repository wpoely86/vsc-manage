##
# Copyright 2011-2015 Ghent University
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
Created on Oct 21, 2011

@author: Jens Timmerman
'''
from config import get_config
from subprocess import Popen, PIPE
from vsc import fancylogger
import datetime
import os
import re
import signal
import socket
import struct
import telnetlib
import time
import traceback
import warnings

# ignore warnings when importing paramiko and it's dependencies
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import paramiko


class Worker(object):
    """
    This abstract class is able to receive commands,
    schedule them for a run, and actually run them.
    """
    def __init__(self, commands=None):
        """
        constructor
        """
        self.log = fancylogger.getLogger(self.__class__.__name__)
        if commands:
            self.commands = commands  # queue commands here, these will be run when doIt is called
        else:
            self.commands = []

    def _adcommand(self, command):
        """
        add a command to the internal 'queue'
        """
        if not isinstance(command, Command):
            raise CommandException("Command %s is not a valid command," % command,
                                   "did you properly extend the Node class?")
        self.commands.append(command)

    def doIt(self):
        """
        run all queued commands
        this is not threaded, so all commands will be ran one by one
        """
        outputs = []
        for command in self.commands:
            outputs.append([command, command.run()])
        return outputs

    def showCommands(self):
        """
        shows a list of commands to be run when doIt is called
        """
        self.log.debug("showcommands: %s" % self.commands)
        return [command.getCommand() for command in self.commands]


class Command(object):
    '''
    This class represents a command
    this will have to be extended
    '''

    def __init__(self, command=None, timeout=get_config("COMMAND_TIMEOUT"), host='localhost'):
        '''
        Constructor
        command is a string representing the command to be run
        '''
        self.log = fancylogger.getLogger(self.__class__.__name__)
        self.command = command
        self.host = host
        self.timeout = float(timeout)

    def __str__(self):
        return "going to run on %s: %s" % (self.host, str(self.getCommand()))

    def __repr__(self):
        return "going to run on %s: %s" % (self.host, str(self.getCommand()))

    def getCommand(self):
        """
        shows what commands would be run
        """
        return self.command

    def run(self):
        """
        Run commands
        """
        self.log.debug("Run going to run %s" % self.command)
        start = datetime.datetime.now()
        # TODO: (high) buffer overflow here sometimes, check what happens and fix
        # see easybuild/buildsoft/async
        p = Popen(self.command, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
        timedout = False
        while p.poll() is None:
            time.sleep(1)
            if os.path.exists("/proc/%s" % (p.pid)):
                now = datetime.datetime.now()
                if (now - start).seconds > self.timeout:
                    if timedout is False:
                        os.kill(p.pid, signal.SIGTERM)
                        self.log.debug("Timeout occured with cmd %s. took more than %i secs to complete." %
                                       (self.command, self.timeout))
                        timedout = True
                    else:
                        os.kill(p.pid, signal.SIGKILL)
        out = p.stdout.read().strip()
        err = p.stderr.read().strip()

        ec = p.returncode
        if ec:
            err += " exitcode: %d" % ec
            self.log.info("Problem occured with cmd %s: out %s, err %s" % (self.command, out, err))
        else:
            self.log.debug("cmd %s on %s: %s" % (self.command, self.host, out))
        return out, err


# composite command
class CompositeCommand(Command):
    """
    a command that can hold several commands and forwards run and getcommand to all of these
    """
    def __init__(self):
        Command.__init__(self)
        self.commands = []

    def run(self):
        """
        calls run for each command added to this composite command
        and
        """
        out = []
        for command in self.commands:
            out.append(command.run())
        return out

    def getCommand(self):
        """
        returns  a list of commands in this command
        """
        return self.commands

    def addCommand(self, command):
        """
        add a command to this composite command
        """
        self.commands.append(command)


class NetWorkCommand(Command):
    """
    class extending a command
    this represents a command to be run over the network
    so they need a host, user, pw, port and timeout
    """
    def __init__(self, command=None, host=None, user=None, passwd=None, port=None,
                 timeout=get_config("COMMAND_TIMEOUT")):
        """
        constructor
        """
        Command.__init__(self, command, timeout)
        self.port = port
        self.host = host
        self.user = user
        self.passwd = passwd
        self.timeout = float(timeout)

    def getCommand(self):
        """
        shows what commands would be run
        """
        return "%s: %s@%s:%s command: %s" % (self.__class__.__name__, self.user, self.host, str(self.port),
                                             self.command)

    def __str__(self):
        return self.getCommand()


class SshCommand(NetWorkCommand):
    """
    extension of the command class
    this class runs commands trought ssh
    """

    class TimeoutSSHClient(paramiko.SSHClient):
        """
        helper class for ssh connections,
        overwriting the default paramiki exec_command, since this does not allow
        for timeouts
        from http://mohangk.org/blog/2011/07/paramiko-sshclient-exec_command-timeout-workaround/
        """
        def exec_command(self, command, bufsize=-1, timeout=get_config("COMMAND_TIMEOUT")):
            """
            Overwritten from SSHClient
            @param command: the command to execute
            @param bufsize: the buffersize
            @param timeout: the amount of seconds to wait before considering this command timed out
            """
            chan = self._transport.open_session()
            chan.settimeout(float(timeout))
            chan.exec_command(command)
            stdin = chan.makefile('wb', bufsize)
            stdout = chan.makefile('rb', bufsize)
            stderr = chan.makefile_stderr('rb', bufsize)
            exitcode = chan.recv_exit_status()
            return stdin, stdout, stderr, exitcode

    def __init__(self, command=None, host=None, user="root", port=22, timeout=get_config("COMMAND_TIMEOUT"),
                 passwd=None):
        """
        constructor
        """
        # self.command = 'ssh -p %s -l %s %s "%s"' % (self.port, self.user, self.host, command)
        NetWorkCommand.__init__(self, command, host, user, passwd, port, timeout)

    def run(self):
        """
        run the command
        This creates a ssh client, runs the command and parses the output
        It returns output,errors
        """
        out = None
        err = None
        # use our inner class
        ssh = SshCommand.TimeoutSSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.passwd:
                # no need to use the agent or keys, we have the password
                ssh.connect(self.host, username=self.user, password=self.passwd, allow_agent=False, look_for_keys=False)
            else:
                ssh.connect(self.host, username=self.user)
        except Exception, ex:
            self.log.info("Problem occured trying to connect to %s error(%s): %s" % (self.host, ex.__class__, ex))
            self.log.debug(traceback.format_exc())
            ssh.close()
            return "", "Could not connect to %s" % self.host
        self.log.debug("going to run '%s' on '%s' as '%s' (using password: %s, timeout: %s)" %
                       (self.command, self.host, self.user, bool(self.passwd), self.timeout))
        # run the command (with a timeout)
        try:
            stdin, stdout, stderr, exitcode = ssh.exec_command(self.command, timeout=self.timeout)
        except Exception, ex:
            # catch the stacktrace
            self.log.info("Problem occured trying to run %s on %s: err (%s): %s" %
                          (self.command, self.host, ex.__class__.__name__, ex))
            self.log.debug(traceback.format_exc())
        # catch the output
        try:
            out = stdout.read().strip()
        except:
            pass
        try:
            err = stderr.read().strip()
        except Exception, ex:
            # really try to print something if an exception occurred
            if not err:
                err = "%s %s " % (ex.__class__.__name__, str(ex))
            self.log.info("Problem occurred trying to get output from %s: out: %s err: %s" % (self.host, out, ex))
            self.log.debug(traceback.format_exc())

        if not err and exitcode:
            # no error, but something went wrong
            err = "exitcode: %d" % exitcode

        try:
            # close our files
            stdin.close()
            stdout.close()
            stderr.close()
        except:
            pass
        self.log.debug("%s on %s returned out: %s, err: %s" % (self.command, self.host, out, err))
        ssh.close()
        return out, err


class TelnetCommand(NetWorkCommand):
    """
    extension of the command class
    this class runs commands over telnet
    """
    def __init__(self, command, host, user=None, passwd=None, port=23, timeout=get_config("COMMAND_FAST_TIMEOUT"),
                 logofftxt='>'):
        """
        constructor
        """
        NetWorkCommand.__init__(self, command, host, user, passwd, port, timeout)
        self.logintxt = "login :"
        self.passwdtxt = "Password:"
        self.logofftxt = logofftxt
        self.logoff = 'exit'

    def run(self):
        """
        Execute telnet commands
        - login
        - execute commnads
        - logout
        """
        err = None
        out = None
        if not self.host:
            self.log.raiseException("No host set when trying to run %s" % self.command, NetworkCommandException)

        try:
            tn = telnetlib.Telnet(self.host)

            self.log.debug("waiting for %s" % self.logintxt)
            tn.read_until(self.logintxt)
            tn.write(self.user + "\n")
            if self.passwd:
                self.log.debug("waiting for %s" % self.passwdtxt)
                tn.read_until(self.passwdtxt)
                tn.write(self.passwd + "\n")
            tn.read_until(self.logofftxt)
            self.log.debug("Run going to run %s" % self.command)
            tn.write(self.command + "\n")

            out = tn.read_until(self.logofftxt)
            tn.write(self.logoff + "\n")
        except Exception, ex:
            err = ex
            self.log.warning("Failed running %s on %s:%s" % (self.command, self.host, ex))
            self.log.debug(traceback.format_exc())
        self.log.debug("cmds %s on host %s ran with output: %s" % (self.command, self.host, out))

        return out, err


""" non abstract commands """


# state commands check if servers are alive (responding to ping) and responding (accepting ssh connections)
class ServerRespondingCommand(SshCommand):
    """
    check if a server is alive (accepting ssh connections and running commands)
    """
    def __init__(self, host=None, timeout=get_config("COMMAND_FAST_TIMEOUT")):
        SshCommand.__init__(self, command='uname', host=host, timeout=timeout)

    def run(self):
        err = None
        try:
            out, err = SshCommand.run(self)
            ans = out.strip() in ('Linux',)
        except Exception, ex:
            self.log.info("sshalive on host %s failed with %s" % (self.host, ex))
            self.log.debug(traceback.format_exc())
            ans = False
            err = ex
        self.log.debug("sshalive host %s: response: %s" % (self.host, out))
        return ans, err


class ServerAliveCommand(NetWorkCommand):
    """
    check if a server is alive (responding to ping)
    Sort of tcptraceroute this host
    - default ssh port
    -  http://www.thomas-guettler.de/scripts/tcptraceroute.py.txt
    """
    def __init__(self, host, port=22, timeout=get_config("COMMAND_FAST_TIMEOUT")):
        NetWorkCommand.__init__(self, host=host, port=port, timeout=timeout)

    def run(self):
        ttl = 3
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, struct.pack('I', ttl))
        s.settimeout(self.timeout)
        ans = True
        err = None
        try:
            s.connect((self.host, self.port))
        except Exception, ex:
            self.log.info("tcpping on host %s failed with %s" % (self.host, ex))
            self.log.debug(traceback.format_exc())
            ans = False
            err = ex
        s.close()
        self.log.debug("tcpping host %s port %s returns %s" % (self.host, self.port, ans))
        return ans, err


class SoftPoweroffCommand(SshCommand):
    """
    A soft poweroff command
    this will try to power of the node in a clean way
    preferably call this before trying a hard poweroff
    """
    def __init__(self, host):
        """
        constructor
        """
        SshCommand.__init__(self, "poweroff", host)


class SoftRebootCommand(SshCommand):
    """
    A soft reboot command
    this will try to reboot of the node in a clean way
    preferably call this before trying a powercycle
    """
    def __init__(self, host):
        """
        constructor
        """
        SshCommand.__init__(self, "reboot", host)


class PbsmomCommand(SshCommand):
    """
    pass a command to pbsmom on a given node
    only use start, stop, restart or status here
    """
    def __init__(self, host, command):
        """
        constructor
        """
        command = "service pbs_mom %s" % command
        SshCommand.__init__(self, command, host)


class PbsmomCleanupCommand(SshCommand):
    """
    run the pbsmom cleanup command
    """
    def __init__(self, host, mastername):
        cmd = "export PBS_HOME=%(home)s && export PBS_SERVER=%(server)s && %(home)s/scripts/cleanup" % \
              {'home': '/var/spool/pbs', 'server': mastername}
        SshCommand.__init__(self, cmd, host)


class PBSNodeStateCommand(Command):
    def __init__(self, host, masternode):
        self.node = host.split(".")[0]
        self.masternode = masternode
        self.command = "PBSNodeStateCommand on %s" % self.node
        self.host = None

    def run(self):
        # TODO: out,err in this
        return self.masternode.getPbsStatusForNode(self.node)


class FixDownOnErrorCommand(SshCommand):
    """
    Fixes the DownOnError message on nodes:
    - remove healthscript.error file on node
    """
    def __init__(self, hostname):
        SshCommand.__init__(self, command='momctl -q clearmsg && /bin/rm -f /var/tmp/healthscript.error',
                            host=hostname, user='root')


# master commands

class MasterStatusCommand(CompositeCommand):
    """
    returns  the full status of a master
    (this is without the pbsstate)
    """
    def __init__(self, host, timeout=get_config("COMMAND_FAST_TIMEOUT")):
        """
        constructor
        """
        CompositeCommand.__init__(self)
        self.addCommand(ServerAliveCommand(host, timeout=timeout))
        self.addCommand(ServerRespondingCommand(host, timeout=timeout))


class MasterCommand(SshCommand):
    """
    run a commad on the master for a list of nodes
    The command will have to be a template with one string in it
    for interpolation.
    This command will be run on the master over ssh, with every string in nodelist used once
    as an argument for string interpolation in the command string.
    """
    def __init__(self, master, nodelist, commandtpl):
        """
        constructor
        """
        self.commandtpl = commandtpl
        self.setNodeList(nodelist)
        SshCommand.__init__(self, self.command, master)

    def setNodeList(self, nodelist):
        """
        Set the NodeList to run this command on
        """
        self.command = ";".join([self.commandtpl % node for node in nodelist])


class SetOnlineMasterCommand(MasterCommand):
    """
    set a list of nodes online on the master
    the list of nodes should be a list of strings with the names of the nodes
    as known by psbnodes
    """
    def __init__(self, master, nodelist=[]):
        """
        constructor
        """
        MasterCommand.__init__(self, master, nodelist, "pbsnodes -c %s ")


class SetOfflineMasterCommand(MasterCommand):
    """
    set a list of nodes offline on the master with pbsnodes
    the list of nodes should be a list of strings with the names of the nodes
    as known by psbnodes
    """
    def __init__(self, master, nodelist=[]):
        """
        constructor
        """
        MasterCommand.__init__(self, master, nodelist, "pbsnodes -o %s ")


# custom commands


class FullStatusCommand(MasterStatusCommand):
    """
    returns  the full status of a node
    """
    def __init__(self, host, masternode, timeout=get_config("COMMAND_FAST_TIMEOUT")):
        """
        constructor
        """
        MasterStatusCommand.__init__(self, host, timeout)
        self.addCommand(PBSNodeStateCommand(host, masternode))


class PBSStateCommand(SshCommand):
    """
    returns  the full pbsstate of a node
    """
    def __init__(self, host, timeout=get_config("COMMAND_TIMEOUT")):
        """
        constructor
        """
        SshCommand.__init__(self, command='pbsnodes | grep -v status', host=host, user='root', timeout=timeout)
        self.masternode = host

    def run(self):
        """
        runs the commando
        """
        out, err = SshCommand.run(self)
        try:
            # no templates here, commands are basically the templates themselves.
            out = re.findall("(node\d+).*?.vsc\n.*state = (.*?)\n", out)
            out = dict(out)
        except Exception, ex:
            self.log.warning("could not parse pbsnodes output : %s" % ex)
            self.log.debug(traceback.format_exc())
            err = ex
        return out, err


class MoabPauseCommand(SshCommand):
    """
    pauses moab
    """
    def __init__(self, host, timeout=get_config("COMMAND_TIMEOUT")):
        SshCommand.__init__(self, command='mschedctl -p', host=host, user='root', timeout=timeout)


class MoabResumeCommand(SshCommand):
    """
    resumes moab
    """
    def __init__(self, host, timeout=get_config("COMMAND_TIMEOUT")):
        SshCommand.__init__(self, command='mschedctl -r', host=host, user='root', timeout=timeout)


class MoabRestartCommand(SshCommand):
    """
    restarts moab
    """
    def __init__(self, host, timeout=get_config("COMMAND_TIMEOUT")):
        SshCommand.__init__(self, command='mschedctl -R', host=host, user='root', timeout=timeout)

# IMM's


class ImmCommand(TelnetCommand):
    COMMAND = 'power state'

    def __init__(self, host, cluster, command=None):
        if not command:
            command = self.COMMAND
        TelnetCommand.__init__(self, command=command, host=host, user=get_config("IMM_USER_%s" % cluster.upper()),
                               passwd=get_config("IMMPASSWD"))


class ImmPoweroffCommand(ImmCommand):
    COMMAND = 'power off'


class ImmSoftPoweroffCommand(ImmCommand):
    COMMAND = 'power off -s'


class ImmPoweronCommand(ImmCommand):
    COMMAND = 'power on'


class ImmRebootCommand(ImmCommand):
    COMMAND = 'power cycle'


class ImmSoftRebootCommand(ImmCommand):
    COMMAND = 'power cycle -s'


class ImmStateCommand(ImmCommand):
    COMMAND = 'power state'

    def run(self):
        out, err = ImmCommand.run(self)
        if err or not out:
            return out, err
        # power state\r\nPower: On\r\nState: Booting OS\r\n\r\nsystem>
        reg = re.search(r"Power:\s+(\S+)", out)
        if reg:
            return reg.group(1), None
        else:
            self.log.warning("Regexp did not match in IdpxStateCommand.run")
            return out, NetworkCommandException("Regexp did not match in IdpxStateCommand.run")


class FullImmStatusCommand(FullStatusCommand):
    """
    returns  the full status of a idpx node
    """
    def __init__(self, host, adminhost, masternode, cluster):
        """
        constructor
        """
        FullStatusCommand.__init__(self, host, masternode)
        self.addCommand(ImmStateCommand(adminhost, cluster))


# blade
class BladeCommand(SshCommand):
    """
    commands for blades
    these should be run on the chassis
    """
    COMMAND = 'power -state'

    def __init__(self, chassisname, slot, command=None):
        if not command:
            command = self.COMMAND
        real_command = "%s -T system:blade[%s]" % (command, slot)
        SshCommand.__init__(self, command=real_command, host=chassisname, user=get_config("BLADEUSER"),
                            passwd=get_config("BLADEPASSWD"))


class BladePoweroffCommand(BladeCommand):
    COMMAND = 'power -off'


class BladeSoftPoweroffCommand(BladeCommand):
    COMMAND = 'power -softoff'


class BladePoweronCommand(BladeCommand):
    COMMAND = 'power -on'


class BladeRebootCommand(BladeCommand):
    COMMAND = 'power -cycle'


class BladeStateCommand(BladeCommand):
    COMMAND = 'power -state'

    def run(self):
        """
        parse the output of the bladestatecommand
        """
        out, err = BladeCommand.run(self)
        if err:
            return out, err

        try:
            out = out.strip().split("\n")[-1]
        except Exception, ex:
            err = ex

        return out, err


class FullBladeStatusCommand(FullStatusCommand):
    """
    returns  the full status of a blade node
    """
    def __init__(self, host, masternode, chassisname, slot):
        """
        constructor
        """
        FullStatusCommand.__init__(self, host, masternode)
        # this is run on the mmodule interface
        self.addCommand(BladeStateCommand(chassisname, slot))


# drac
class DracCommand(Command):
    """
    commands for dracs
    """
    COMMAND = 'powerstatus'

    def __init__(self, adminhost, command=None):
        if not command:
            command = self.COMMAND
        real_command = "idracadm -r %s -u root -p '%s' serveraction %s" % (adminhost, get_config("DRACPASSWD"), command)
        Command.__init__(self, command=real_command)


class DracPoweroffCommand(DracCommand):
    COMMAND = 'powerdown'


class DracPoweronCommand(DracCommand):
    COMMAND = 'powerup'


class DracRebootCommand(DracCommand):
    COMMAND = 'hardreset'


class DracStatusCommand(DracCommand):
    COMMAND = 'powerstatus'

    def run(self):
        """
        parse the output of the DracStatusCommand
        """
        out, err = DracCommand.run(self)
        if err:
            return out, err

        try:
            out = out.strip().split(':')[-1].strip()
        except IndexError:
            err = "Unexpected output"

        return out, err


class DracFullStatusCommand(FullStatusCommand):
    """
    returns  the full status of a blade node
    """
    def __init__(self, host, adminhost, masternode):
        """
        constructor
        """
        FullStatusCommand.__init__(self, host, masternode)
        # this is run on the mmodule interface
        self.addCommand(DracStatusCommand(adminhost))


# ipmitool commands (crappy bmc and HP gen8)
# TODO: write an python-api for ipmitool.
class IpmiCommand(Command):
    """
    commands for ipmi enabled bmc/dracs
    """
    PROTOCOL = 'lanplus'
    COMMAND = 'status'

    def __init__(self, hostname, clustername, command=None):
        if not command:
            command = self.COMMAND
        real_command = "sudo ipmitool -I %s -H %s -U %s -P '%s' chassis power %s" % (
            self.PROTOCOL, hostname, get_config('IMM_USER_%s' % clustername.upper()), get_config('IMMPASSWD'), command
        )
        Command.__init__(self, real_command)


class IpmiPoweroffCommand(IpmiCommand):
    COMMAND = 'off'


class IpmiSoftPoweroffCommand(IpmiCommand):
    COMMAND = 'soft'


class IpmiPoweronCommand(IpmiCommand):
    COMMAND = 'on'


class IpmiRebootCommand(IpmiCommand):
    COMMAND = 'reset'


class IpmiStatusCommand(IpmiCommand):
    COMMAND = 'status'


class IpmiFullStatusCommand(FullStatusCommand):
    """
    returns  the full status of a blade node
    """
    def __init__(self, host, clustername, adminhost, masternode):
        """
        constructor
        """
        FullStatusCommand.__init__(self, host, masternode)
        # this is run on the nat
        self.addCommand(IpmiStatusCommand(adminhost, clustername))


class DMTFSMASHCLPLEDOnCommand(SshCommand):
    """
    Class implementing a command that turns on the location LED on a
    node that supports the Distributed Management Task Force,
    Systems Management Architecture for Server Hardware,
    Command Line Protocol"""
    def __init__(self, adminhost):
        """
        constructor, turns on the location led of the node
        """
        cmd = "start /system1/led1"
        # these are quite slow to respond
        SshCommand.__init__(self, command=cmd, host=adminhost, user='USERID', passwd=get_config("IMMPASSWD"),
                            timeout=30)


class DMTFSMASHCLPLEDOffCommand(SshCommand):
    """
    Class implementing a command that turns off the location LED on a
    node that supports the Distributed Management Task Force,
    Systems Management Architecture for Server Hardware,
    Command Line Protocol"""
    def __init__(self, adminhost):
        """
        constructor, turns on the location led of the node
        """
        cmd = "stop /system1/led1"
        SshCommand.__init__(self, command=cmd, host=adminhost, user='USERID', passwd=get_config("IMMPASSWD"),
                            timeout=30)


class NotSupportedCommand(Command):
    """
    Class implementing a Command for unsupported operation
    """
    def run(self):
        self.log.warning("command not supported (yet) %s" % self.command)
        return self.command, "Not supported yet by manage!"


# test commands
class TestCommand(Command):
    """
    test command
    does nothing but echoing the command back
    """
    def run(self):
        self.log.info("testcommand: %s" % self.command)
        return "running testcommand: %s" % self.command, None


# Exceptions
class NetworkCommandException(Exception):
    """
    NetworkCommandException
    thrown when an exception occurs in a network command
    """
    pass


class CommandException(Exception):
    """
    CommandException
    thrown when an exception occurs in with a command
    """
    pass
