# -*- encoding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import test.managertests as m
import unittest



suite = unittest.TestSuite([x.suite() for x in (m,)])

try:
    import xmlrunner
    rs = xmlrunner.XMLTestRunner(output="test-reports").run(suite)
except ImportError, err:
    rs = unittest.TextTestRunner().run(suite)

if not rs.wasSuccessful():
    sys.exit(1)

if __name__ == '__main__':
    from vsc.utils import fancylogger
    fancylogger.logToScreen(enable=True)
