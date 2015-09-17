manage
======

[![Build Status](https://jenkins1.ugent.be/buildStatus/icon?job=vsc-manage-python26)](https://jenkins1.ugent.be/view/VSC%20tools/job/vsc-manage-python26/)

manage is a python library to manage the clusters (power on, off, set offline, online, stop the scheduler, torn on/off locator leds, acknowledge events in the monitoring) based on a selection of nodes (onfline, offline, down, worker nodes, master nodes, storage)  it works toghether with pbs and vsc-quattor to get cluster information.

installation: change into the directory where you checked this out, and run:
`easy_install --user .`

The command line tool to interface with the manage library is called misty.

To see what it can do, run
`misty -H`
```
Usage: misty [options]


Options:
  -h, --shorthelp       show short help message and exit
  -H, --help            show full help message and exit

  Node actions:
    Use these to select the sepecific action you want to do on the
    selected node(s).You can select multiple actions. They will be run in
    the order as shown here. (configfile section action)

    --co=CO             Run a quattor component on the selected nodes, e.g.
                        spma,cron (type string)
    --fix-downonerror   Fix the down on error status (for the selected
                        workernodes) (def False)
    --hardreboot        Power cycle the selected nodes (def False)
    --ledoff            Turn off the locator led of the selected nodes (def
                        False)
    --ledon             Turn on the locator led of the selected nodes (def
                        False)
    --pbsmomcleanup     Run pbs cleanupscripts (def False)
    --pbsmomrestart     Restart pbs_mom on the selected nodes (def False)
    --pbsmomstatus      gives the status of pbsmom on the selected nodes (def
                        False)
    --pbsmomstop        Stop pbs_mom on selected nodes (def False)
    --powercut          Power off the selected nodes as soon as possible (def
                        False)
    --poweroff          Power off the selected nodes in a clean way (def
                        False)
    --poweron           Power on the selected nodes (def False)
    --reboot            Reboot the selected nodes in a clean way (def False)
    --runcmd=RUNCMD     Run a (bash) command on the selected nodes (type
                        string)
    --setoffline        Set the selected nodes offline (def False)
    --setonline         Set the selected nodes online (def False)
    -s, --state         State information (tcp, ssh, nodestate, power).This
                        will run instantly (on the master), no test-run here
                        (def False)

  Cluster actions:
    Use these to select the specific action you want to run on the
    selected cluster. These are run in the order as listed here
    (configfile section clusteraction)

    -p, --pause         Pause the scheduler (def False)
    --restart           Restart the scheduler, Warning: will pass all jobs
                        through GOLD before 1st rescheduling,--force needed
                        (def False)
    -r, --resume        Resume the scheduler (def False)

  General Options:
    General options for Manage (configfile section general)

    -C CLUSTER, --cluster=CLUSTER
                        Specify the cluster to run on, When not specified, the
                        script will attempt to detect the current cluster. All
                        operations can only affect one cluster at a time
    -f, --forced        Included as a dummy protection. If a special node is
                        selected, --forced is required as well (def False)
    --non-threaded      Disable threading, do commands one by one (def False)
    -t, --test-run      Print what would be done, without actually doing
                        anything (def False)
    -v, --verbose       Enable extra output, use -vv for even more output (def
                        0)

  Monitoring options:
    Use these to enable notification of the monitoring service (configfile
    section monitoring)

    --ack               Acknowledge a problem with all selected nodes. (def
                        False)
    --ack-service=ACK-SERVICE
                        Acknowledge a problem with a service on all selected
                        nodes (type string)
    --comment=COMMENT   Set the comment for the acknowledgement or scheduled
                        downtime (type string)
    --downtime=DOWNTIME
                        Schedule all selected nodes and it's services for a
                        downtime (in hours) (type string)
    --imms              also select the imms of the selected nodes, this is
                        only used for acknowleding problems to monitoring (def
                        False)

  Node selection:
    Use these to select a node or a group of nodes. All selections will be
    added up. F.ex. -od will select all nodes that are either down or
    offline (configfile section node)

    --all-nodes         Select all servers, WARNING: THIS WILL INCLUDE MASTERS
                        (def False)
    --chassis=CHASSIS   Select all nodes in a chassis, as it is listed in
                        quattor, e.g. mmodule01.gengar.gent/vscWARNING: this
                        might also include masters (type string)
    --down              Select all down nodes (def False)
    -i, --idle          Select all free/idle nodes (def False)
    --master=MASTER     Select a master node WARNING: this will bypass the PBS
                        server.Multiple nodes can be given separated by ',',
                        no spaces. (type string)
    -n NODE, --node=NODE
                        Select a specific node. Multiple worker nodes can be
                        given separated by ',', no spaces.This will bypass pbs
                        server. You can also specify a range of nodes, when
                        separated by '-'. e.g.'node601,605-608,203-208 (type
                        string)
    -o, --offline       Select all offline nodes (def False)
    -q, --quattor       Use quattor to select nodes instead of pbsnodes on the
                        master. this might be faster, and also works if the
                        master is offline. This option will be ignored when
                        using the idle, down or offline node selection. (def
                        False)
    --storage=STORAGE   Select this master (type string)
    -a, --worker        Select all worker nodes (def False)

  Debug and logging options (configfile section MAIN):
    -d, --debug         Enable debug log mode (def False)
    --info              Enable info log mode (def False)
    --quiet             Enable info quiet/warning mode (def False)

  Configfile options (configfile section MAIN):
    --configfiles=CONFIGFILES
                        Parse (additional) configfiles (type comma-separated
                        list)
    --ignoreconfigfiles=IGNORECONFIGFILES
                        Ignore configfiles (type comma-separated list)

Boolean options support disable prefix to do the inverse of the action, e.g.
option --someopt also supports --disable-someopt.

All long option names can be passed as environment variables. Variable name is
MISTY_<LONGNAME> eg. --some-opt is same as setting MISTY_SOME_OPT in the
environment.
```

example:
`misty -C gengar --chassis=mmodule05 --status`
```
Nodes - Chassis interface - Location         tcpping - alivessh - pbs state - hwstate
----------------------------------------------------------------------------------------
node045 mmodule05           2                [True, True, 'offline', 'On']
node055 mmodule05           1                [True, True, 'offline', 'On']
node059 mmodule05           5                [True, True, 'offline', 'On']
node060 mmodule05           6                [True, True, 'offline', 'On']
node061 mmodule05           7                [True, True, 'offline', 'On']
node062 mmodule05           8                [True, True, 'offline', 'On']
node063 mmodule05           9                [True, True, 'offline', 'On']
node065 mmodule05           11               [True, True, 'offline', 'On']
node066 mmodule05           12               [True, True, 'offline', 'On']
node067 mmodule05           13               [True, True, 'offline', 'On']
node068 mmodule05           14               [True, True, 'offline', 'On']
```

Disclaimer
---------
This tool is not so usefull yet for anyone who is not running a batch cluster with pbs, or does not have a list of quattor profile for his/her nodes.
However, making node discovery and cluster configuration an easy option in the config file should be fairly easy. (generaloption.py is very flexible)

How it works
-------------
- currently manage uses the .json.tgz profiles created by quattor (http://quattor.org) to figure out what clusters exist, and what nodes are in which
cluster.
 - TODO: allow for a section in the config file to list all your machines per cluster (or group)
- Then in clusters.py we defined what this cluster is made up of (what master node, what workernode)
 - TODO: Let this also be configureable in the config file
- Then depending on what type of node a different command will be run on that host (or it's ipmi)
 - Commands are first built up, this allows for a dry run, or (TODO) maybe in the future also have a save and undo function for every command.
 - Commands can be ssh, or telnet, we support a lot of ipmi commands, initial support for DTMF SMASH, support for icinga/nagios for automatically scheduling downtime, or acknowledging problems.
 - We also have full support for pbs:starting, pausing the server, setting offline, fixing down state, or restarting the mom on the workernodes...
