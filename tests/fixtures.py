from cgitb import text
import unittest
import logging
import time
import threading
import sys
import subprocess
import shutil
import os
import signal
import pandas as pd
from io import StringIO

import logging
log = logging.getLogger("CS118")

from dotenv import load_dotenv
load_dotenv()

def read_shell_cmd(args, showdebug=True, **kwargs):
    # if showdebug:
    if True:
        log.debug("Starting: %s" % " ".join(args))

    p = subprocess.Popen(args, shell=False,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, **kwargs)
    return p

class Worker(threading.Thread):
    def __init__(self, args):
        threading.Thread.__init__(self)
        self.args = args
        self.start()

    def run(self):
        try:
            self.process = read_shell_cmd(self.args)
            # log.error("PID: %d" % self.process.pid)

            (self.stdout, self.stderr) = self.process.communicate()
            self.stdout = self.stdout.decode()
            self.stderr = self.stderr.decode()
            self.retcode = self.process.returncode

            # log.debug("stdout: [%s]" % self.stdout)
            if self.stderr.strip():
                log.debug("stderr: [%s]" % self.stderr)
        except:

            log.debug("Failed to lunch %s" % " ".join(self.args))
            self.stdout = None
            self.stderr = None
            self.retcode = None

    def killall(self, signals):
        for signal in signals:
            # log.debug("SENDING SIGNAL %s to %s (%d)" % (signal, self.args[0], self.process.pid))
            try:
                os.kill(self.process.pid, signal)
            except OSError as e:
                pass
                # log.error(e)

    # for large file transmission, probably 5 is too small
    def wait(self, max_time=5):
        if not self.is_alive():
            if not hasattr(self, 'retcode') or self.retcode is None:
                raise AssertionError("Failed to lunch %s" % self.args[0])
            return

        self.join(max_time)

        if self.is_alive():
            self.killall([signal.SIGINT, signal.SIGTERM, signal.SIGQUIT])
            self.join(1)
            self.killall([signal.SIGKILL])
            self.join(1)
            if self.is_alive():
                os.system('killall -INT -TERM -QUIT "%s"' % self.args[0])
                self.join(1)
                os.system('killall -KILL "%s"' % self.args[0])
                self.join(1)
                log.error("+++++++ FORKED PROCESS DID NOT DIE ++++++++++++")
            # NOTE: I don't know why Alex wrote this but this means the server always fails to quit
            raise AssertionError("Process %s didn't stop as expected" % " ".join(self.args))

        if not hasattr(self, 'retcode') or self.retcode is None:
            raise AssertionError("Failed to lunch %s" % self.args[0])

    def getStats(self, is_server=False):
        df = pd.DataFrame(columns=('cmd', 'seqno', 'ack', 'id', 'cwnd', 'ssthresh', 'flgs'))

        def drop(values):
            return {'cmd': values[0],
                    'seqno': values[1],
                    'ack': values[2],
                    'id': values[3],
                    'cwnd': '0',
                    'ssthresh': '0',
                    'flgs': values[4:]}

        def recvOrSend(values):
            return {'cmd': values[0],
                    'seqno': values[1],
                    'ack': values[2],
                    'id': values[3],
                    'cwnd': values[4],
                    'ssthresh': values[5],
                    'flgs': values[6:]}

        i = 0
        for line in StringIO(self.stdout):
            if not line.strip():
                continue
            values = line.strip().split(" ")
            if values[0] == 'DROP' or is_server:
                row = drop(values)
            else:
                row = recvOrSend(values)
            df.loc[i] = row
            i += 1

        if len(df) > 0:
            # Somehow, if length is zero, it segfaults
            for i in ['seqno', 'ack', 'id', 'cwnd', 'ssthresh']:
                df[i] = pd.to_numeric(df[i], errors='coerce')

        return df

class BasicTest(unittest.TestCase):
    """Base class for tests that don't require cleanups"""

    SUBMISSION = os.getenv('SUBMISSION', default="/autograder/submission")
    REFERENCE = os.getenv('REFERENCE', default="/autograder/source/reference-implementation")
    HOSTNAME = os.getenv('HOSTNAME', default="localhost")
    PORTNO = int(os.getenv('PORTNO', default="5000"))

    FILE_10k  = os.getenv('FILE_10k', default="/file_10k")
    FILE_1M   = os.getenv('FILE_1M', default="/file_1M")
    FILE_10M  = os.getenv('FILE_10M', default="/file_10M")
    LOG = logging.getLogger("CS118")

    def setUp(self):
        self._threads = []

    def tearDown(self):
        for thread in self._threads:
            if thread.is_alive():
                thread.killall([signal.SIGINT, signal.SIGTERM, signal.SIGQUIT])
                thread.join(1)
                thread.killall([signal.SIGKILL])
                thread.join(1)

        self._threads = []

    def _start(self, args, nodelay=False):
        thread = Worker(args)
        self._threads.append(thread)
        if not nodelay:
            time.sleep(0.5) # there is no way to determine that app started, just hope it started within 1 seconds
        return thread

    def startSubmission(self, cmd, args, nodelay=False):
        updatedArgs = ["%s/%s" % (self.SUBMISSION, cmd)] + args
        return self._start(updatedArgs, nodelay)

    def startReference(self, cmd, args, nodelay=False):
        updatedArgs = ["%s/%s" % (self.REFERENCE, cmd)] + args
        return self._start(updatedArgs, nodelay)

    def runApp(self, cmd):
        p = subprocess.Popen(cmd, shell=True,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (stdout, stderr) = p.communicate()
        stdout = stdout.decode()
        stderr = stderr.decode()
        self.LOG.debug("%s" % cmd)
        if stdout.strip():
            self.LOG.debug("stdout: %s" % stdout)
        if stderr.strip():
            self.LOG.debug("stderr: %s" % stderr)
        return (stdout, p.returncode)

class TestWithSavedData(BasicTest):
    """Base class for tests that use disk (will create folder and do cleanup afterwards)"""

    def setUp(self):
        BasicTest.setUp(self)
        self.relativeFolder = "relative/"
        self.absoluteFolder = "%s/absolute/" % os.getcwd()
        shutil.rmtree(self.relativeFolder, ignore_errors = True)
        shutil.rmtree(self.absoluteFolder, ignore_errors = True)

        os.makedirs(self.relativeFolder)
        os.makedirs(self.absoluteFolder)

    def tearDown(self):
        # shutil.rmtree(self.relativeFolder, ignore_errors = True)
        # shutil.rmtree(self.absoluteFolder, ignore_errors = True)
        BasicTest.tearDown(self)
