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
# #
# All rights reserved.
#
##
"""
vsc-manage distribution setup.py

@author: Jens Timmerman <jens.timmerman@ugent.be>
"""
try:
    import vsc.install.shared_setup as shared_setup
    from vsc.install.shared_setup import ag, kh, sdw, wdp, jt
except ImportError:
    print "vsc.install could not be found, make sure a recent vsc-base is installed"
    print "you might want to try 'easy_install [--user] https://github.com/hpcugent/vsc-base/archive/master.tar.gz'"


def remove_bdist_rpm_source_file():
    """List of files to remove from the (source) RPM."""
    return ['lib/vsc/__init__.py']


shared_setup.remove_extra_bdist_rpm_files = remove_bdist_rpm_source_file
shared_setup.SHARED_TARGET.update({
    'url': 'https://github.ugent.be/hpcugent/vsc-manage',
    'download_url': 'https://github.ugent.be/hpcugent/vsc-manage'
})


PACKAGE = {
    'name': 'vsc-manage',
    'version': '1.6.0',
    'author': [jt],
    'maintainer': [jt],
    'packages': ['vsc', 'vsc.manage'],
    'namespace_packages': ['vsc'],
    'scripts': ['bin/misty.py'],
    'data_files': [('/etc',['config/manage_defaults.cfg'])],
    'install_requires': [
        'libxml2-python',
        'paramiko',
        'pycrypto >= 2.1',
    ],
}

if __name__ == '__main__':
    shared_setup.action_target(PACKAGE)
