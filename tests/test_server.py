"""
UCLA CS118 17S
Project 2 grading script
"""

import unittest
from gradescope_utils.autograder_utils.decorators import weight, tags, visibility
from .fixtures import BasicTest, TestWithSavedData

import os
import signal
import pandas as pd
import time

class ServerTests(TestWithSavedData):

    @classmethod
    def setUpClass(cls):
        cls.portOffset = 200

    @weight(2.5)
    @visibility("visible")
    def test3_1(self):
        """3.1. Server responses with SYN-ACK packet with correct connection ID"""

        ServerTests.portOffset += 1
        file = self.FILE_10k

        server = self.startSubmission('server', [str(self.PORTNO + ServerTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('proxy.py', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset),
                                                 self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset + 100)])
        client = self.startReference('client', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset), file])

        client.wait(60)
        self.assertEqual(client.is_alive(), False, "Client didn't exit after finishing the transmission")
        self.assertEqual(client.retcode, 0, "Client exit code is not zero (%d, stderr: %s)" % (client.retcode, client.stderr))

        try:
            server.wait(1)
        except AssertionError:
            pass

        try:
            proxy.wait(1)
        except AssertionError:
            pass

        with open("%s/client.txt" % self.absoluteFolder, 'w') as f:
            f.write(client.stdout)
        with open("%s/server.txt" % self.absoluteFolder, 'w') as f:
            f.write(server.stdout)
        with open("%s/proxy.txt" % self.absoluteFolder, 'w') as f:
            f.write(proxy.stdout)

        df = client.getStats()
        df = df[df.cmd == 'RECV']

        self.assertTrue('SYN' in df.iloc[0]['flgs'], 'No SYN in the first packet')
        self.assertTrue('ACK' in df.iloc[0]['flgs'], 'No ACK in the first packet')
        self.assertEqual(len(df.iloc[0]['flgs']), 2, 'Two flags should have been in the first packet')
        self.assertEqual(df.iloc[0]['id'], 1, 'Wrong assigned connection ID')

        return (server, client)

    @weight(2.5)
    @visibility("visible")
    def test3_2(self):
        """3.2. Server has correct initial values for CWND, SS-THRESH, and Sequence Number"""

        (server, client) = self.test3_1()

        df = server.getStats(True)
        df = df[df.cmd == 'SEND']

        self.assertTrue('SYN' in df.iloc[0]['flgs'], 'No SYN in the first packet')
        self.assertTrue('ACK' in df.iloc[0]['flgs'], 'No ACK in the first packet')
        self.assertEqual(len(df.iloc[0]['flgs']), 2, 'Two flags should have been in the first packet')
        self.assertEqual(df.iloc[0]['id'], 1, 'Wrong assigned connection ID')

        # self.assertEqual(df.iloc[0]['cwnd'], 512, 'Wrong initial cwnd')
        # self.assertEqual(df.iloc[0]['ssthresh'], 10000, 'Wrong initial ssthresh')
        self.assertEqual(df.iloc[0]['seqno'], 4321, 'Wrong initial seqno')

        self.assertEqual(df.iloc[1]['seqno'], 4322, 'Wrong subseqeuent seqno')

    @weight(5)
    @visibility("visible")
    def test3_3(self):
        """3.3. Server responds with ACK packets, which include the next expected in-sequence byte to receive (cumulative ACK)"""

        (server, client) = self.test3_1()

        df = server.getStats(True)
        df1 = df[df.cmd == 'RECV']

        processed = False
        for index, row in df1.iterrows():
            if 'ACK' in row['flgs']:
                continue

            if 'SYN' in row['flgs']:
                size = 1
            else:
                size = 512

            sendRow = df.loc[index+1]
            if sendRow.cmd != 'SEND':
                self.LOG.error("Something wrong with %s" % str(row))
                continue

            self.assertTrue('ACK' in sendRow['flgs'], 'ACK should have been sent')
            self.assertEqual(sendRow.ack, row.seqno + size, 'Cumulative ACK should be correct (%d != %d)' % (int(sendRow.ack), int(row.seqno + size)))
            processed = True
            if size > 1:
                break

        self.assertTrue(processed, "Should be some RECV/SEND")

    @weight(5)
    @visibility("after_published")
    def test3_4(self, loss=0.0, delay=0.001):
        """3.4. Server able to receive a large file (10 MiB bytes) and save it in 1.file without delay, loss, and reorder"""

        ServerTests.portOffset += 1
        file = self.FILE_1M

        server = self.startSubmission('server', [str(self.PORTNO + ServerTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('lossy-proxy.py', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset),
                                                       self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset + 100),
                                                       str(loss), str(delay)])
        client = self.startSubmission('client', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset), file])

        try:
            client.wait(120)
        except AssertionError:
            pass
        with open("%s/client.txt" % self.absoluteFolder, 'w') as f:
            f.write(client.stdout)

        try:
            server.wait(1)
        except AssertionError:
            pass
        with open("%s/server.txt" % self.absoluteFolder, 'w') as f:
            f.write(server.stdout)

        try:
            proxy.wait(1)
        except AssertionError:
            pass
        with open("%s/proxy.txt" % self.absoluteFolder, 'w') as f:
            f.write(proxy.stdout)

        self.assertEqual(client.is_alive(), False, "Client didn't exit after finishing the transmission")
        self.assertEqual(client.retcode, 0, "Client exit code is not zero (%d, stderr: %s)" % (client.retcode, client.stderr))

        (diff, diffret) = self.runApp('diff "%s" "%s/1.file"' % (file, self.absoluteFolder))
        self.assertEqual(diffret, 0, "The saved file is different from the original")

        return (server, client)

    @weight(5)
    @visibility("after_published")
    def test3_5(self):
        """3.5. Server able to receive a large file (10 MiB bytes) and save it in 1.file (with reordered and delayed packets)"""

        self.test3_4(loss=0.05, delay=0.01)

    @weight(5)
    @visibility("visible")
    def test3_6(self, parallel=False, loss=0.0, delay=0.001):
        """3.6. Server able to receive 10 small files (1 MiB bytes) in 1.file, 2.file, ..., 10.file without delay, loss, and reorder (sequentially)"""

        ServerTests.portOffset += 1

        server = self.startSubmission('server', [str(self.PORTNO + ServerTests.portOffset), self.absoluteFolder])

        fileRange = range(1, 5)

        files = ["%s_%d" % (self.FILE_10k, i) for i in fileRange]
        fileSizes = {}
        for file in files:
            size = os.stat(file).st_size
            if size in fileSizes:
                fileSizes[size]['count'] += 1
            else:
                fileSizes[size] = {'file': file, 'count': 1}

        def runClient(file, parallel, i):
            proxy = self.startReference('lossy-proxy.py', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset + i),
                                                           self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset),
                                                           str(loss), str(delay)], nodelay=False)
            time.sleep(0.01)
            client = self.startReference('client', [self.HOSTNAME, str(self.PORTNO + ServerTests.portOffset + i), file], nodelay=False)
            if not parallel:
                client.wait(60)
                self.assertEqual(client.is_alive(), False, "The reference client should have finished transmission")

                try:
                    proxy.wait(0)
                except AssertionError:
                    pass
            return client

        i = 300
        clients = []
        for file in files:
            client = runClient(file=file, parallel=parallel, i=i)
            i += 1
            clients.append(client)

        if parallel:
            for client in clients:
                client.wait(60)
                self.assertEqual(client.is_alive(), False, "The reference client should have finished transmission")

        try:
            server.wait(10)
        except AssertionError as e:
            pass

        actualFiles = os.listdir(self.absoluteFolder)
        actualFiles.sort()

        self.LOG.debug("Content of output folder: %s" % actualFiles)
        expected = ["%d.file" % d for d in fileRange]
        expected.sort()
        self.assertEqual(actualFiles, expected, "Not expected number of saved files (expect %d, got the following: [%s])" % (len(fileRange), ", ".join(actualFiles)))

        if not parallel:
            for index, file in enumerate(files):
                (diff, diffret) = self.runApp('diff "%s" "%s/%d.file"' % (file, self.absoluteFolder, index + 1))
                self.assertEqual(diffret, 0, "The saved file [%d.file] is different from the original [%s]" % (index + 1, file))
        else:
            # order not guaranteed, so just check that we have enough files of correct sizes
            for file in actualFiles:
                size = os.stat("%s/%s" % (self.absoluteFolder, file)).st_size
                self.assertEqual(size in fileSizes, True, "Incorrect file")

                origFile = fileSizes[size]['file']
                fileSizes[size]['count'] -= 1
                if fileSizes[size]['count'] == 0:
                    del fileSizes[size]

                (diff, diffret) = self.runApp('diff "%s" "%s/%s"' % (origFile, self.absoluteFolder, file))
                self.assertEqual(diffret, 0, "Saved and original file differ")

    @weight(5)
    @visibility("after_published")
    def test3_7(self):
        """3.7. Server able to receive 10 small files (1 MiB bytes) in 1.file, 2.file, ..., 10.file without delay, loss, and reorder (in parallel)"""

        self.test3_6(parallel=True)

    @weight(7.5)
    @visibility("after_published")
    def test3_8(self):
        """3.8. Server able to receive 10 small files (1 MiB bytes) in 1.file, 2.file, ..., 10.file over lossy and large delay network (sequentially)"""

        self.test3_6(parallel=False, loss=0.04, delay=0.04)

    @weight(7.5)
    @visibility("after_published")
    def test3_9(self):
        """3.9. Server able to receive 10 small files (1 MiB bytes) in 1.file, 2.file, ..., 10.file over lossy and large delay network (in parallel)"""

        self.test3_6(parallel=True, loss=0.05, delay=0.1)
