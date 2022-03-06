"""
UCLA CS118 17S
Project 2 grading script
"""

import unittest
from gradescope_utils.autograder_utils.decorators import weight, tags, visibility
from .fixtures import BasicTest, TestWithSavedData

import subprocess
import signal

class MiscChecks(BasicTest):
    @weight(2.5)
    @visibility("visible")
    def test_1_1(self):
        """1.1. At least 3 git commits (at least one from each group member)"""
        (stdout, retcode) = self.runApp(f'git -C "{self.SUBMISSION}" log --pretty=format:"%h - %ai: (%an <%ae>) %s" | grep -v -e "Xinyu Ma" -e "zhaojinghao" -e "Varun Patil"')
        self.assertGreaterEqual(len(stdout.splitlines()), 4, "At least 3 git commits are expected")

    @weight(1.25)
    @visibility("visible")
    def test_1_2(self):
        """1.2. Client handles incorrect hostname"""

        process = self.startSubmission('client', ['1wronghost', str(self.PORTNO), self.FILE_10k])
        process.wait()
        self.assertNotEqual(process.retcode, 0, "Client should have returned non-zero exit code")
        self.assertEqual(process.stderr.startswith("ERROR:"), True, "stderr should have started with ERROR: (%s)" % process.stderr)

    @weight(1.25)
    @visibility("visible")
    def test_1_3(self):
        """1.3. Client handles incorrect port"""
        process = self.startSubmission('client', [self.HOSTNAME, "-1", self.FILE_10k])
        process.wait()
        self.assertNotEqual(process.retcode, 0, "Client should have returned non-zero exit code")
        self.assertEqual(process.stderr.startswith("ERROR:"), True, "stderr should have started with ERROR: (%s)" % process.stderr)

    @weight(2.5)
    @visibility("visible")
    def test_1_4(self):
        """1.4. Server handles incorrect port"""
        process = self.startSubmission('server', ['-1', '/tmp'])
        process.wait()
        self.assertNotEqual(process.retcode, 0, "Client should have returned non-zero exit code")
        self.assertEqual(process.stderr.startswith("ERROR:"), True, "stderr should have started with ERROR: (%s)" % process.stderr)
