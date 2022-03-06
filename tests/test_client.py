"""
UCLA CS118 17S
Project 2 grading script
"""

import unittest
from gradescope_utils.autograder_utils.decorators import weight, tags, visibility
from .fixtures import BasicTest, TestWithSavedData

import os
import signal
import sys
import pandas as pd
import time

class ClientTests(TestWithSavedData):

    @classmethod
    def setUpClass(cls):
        cls.portOffset = 0

    @weight(2.5)
    @visibility("visible")
    def test2_1(self, small=True, checkFile=False):
        """2.1. Client initiates three-way handshake by sending a SYN packet with correct values in its header"""

        ClientTests.portOffset += 1
        if small:
            file = self.FILE_10k
        else:
            file = self.FILE_1M

        server = self.startReference('server', [str(self.PORTNO + ClientTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('proxy.py', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset),
                                                 self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset + 100)])
        client = self.startSubmission('client', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset), file])

        try:
            client.wait(60)
        except AssertionError:
            pass

        try:
            server.wait(1)
        except AssertionError:
            pass

        try:
            proxy.wait(1)
        except AssertionError:
            pass

        self.LOG.debug("+++++ CLIENT ++++++")
        self.LOG.debug("\n".join(client.stdout.splitlines()[0:10]))
        self.LOG.debug("+++++ SERVER ++++++")
        self.LOG.debug("\n".join(server.stdout.splitlines()[0:10]))

        with open("%s/client.txt" % self.absoluteFolder, 'w') as f:
            f.write(client.stdout)
        with open("%s/server.txt" % self.absoluteFolder, 'w') as f:
            f.write(server.stdout)
        with open("%s/proxy.txt" % self.absoluteFolder, 'w') as f:
            f.write(proxy.stdout)

        self.assertNotEqual(client.stdout, '', 'Client did not create any output')
        self.assertNotEqual(server.stdout, '', 'Server did not create any output')

        self.assertEqual(client.is_alive(), False, "Client didn't exit after finishing the transmission")
        self.assertEqual(client.retcode, 0, "Client exit code is not zero (%d, stderr: %s)" % (client.retcode, client.stderr))

        df = server.getStats(True)
        df = df[df.cmd == 'RECV']

        self.assertTrue('SYN' in df.iloc[0]['flgs'], 'No SYN in the first packet')
        self.assertEqual(len(df.iloc[0]['flgs']), 1, 'Should be only one flag in the first packet')
        self.assertEqual(df.iloc[0]['id'], 0, 'Wrong initial connection ID')

        self.assertTrue('ACK' in df.iloc[1]['flgs'], 'No ACK in the second packet')
        self.assertEqual(len(df.iloc[1]['flgs']), 1, 'Should be only one flag in the second packet')
        self.assertEqual(df.iloc[1]['id'], 1, 'Wrong connection ID')
        self.assertEqual(df.iloc[1]['ack'], 4322, 'Wrong ACKed sequence number')

        if checkFile:
            (diff, diffret) = self.runApp('diff "%s" "%s/1.file"' % (file, self.absoluteFolder))
            self.assertEqual(diffret, 0, "The saved file is different from the original")

        return (server, client)

    @weight(2.5)
    @visibility("visible")
    def test2_2(self):
        """2.2. Client has correct initial values for CWND, SS-THRESH, and Sequence Number"""

        (server, client) = self.test2_1()

        df = client.getStats()
        df = df[df.cmd == 'SEND']

        self.assertTrue('SYN' in df.iloc[0]['flgs'], 'No SYN in the first packet')
        self.assertEqual(len(df.iloc[0]['flgs']), 1, 'Only one flag in the first packet')
        self.assertEqual(df.iloc[0]['id'], 0, 'Wrong initial connection ID')

        self.assertEqual(df.iloc[0]['cwnd'], 512, 'Wrong initial cwnd')
        self.assertEqual(df.iloc[0]['ssthresh'], 10000, 'Wrong initial ssthresh')
        self.assertEqual(df.iloc[0]['seqno'], 12345, 'Wrong initial seqno')

    @weight(5)
    @visibility("visible")
    def test2_3(self):
        """2.3. Data segments that client sends are not exceeding 512 bytes and on average larger than 500 bytes (for 1~MByte file)"""

        (server, client) = self.test2_1(small=False)

        df = pd.read_csv('%s/proxy.txt' % self.absoluteFolder, header=None, names=['pkt'])
        max = int(df.pkt.max())
        mean = int(df.pkt.mean())
        self.assertLess(max, 513 + 12, "Data segment exceeds 512 bytes (actual: %d)" % (max - 12))
        self.assertGreater(mean, 500 + 12, "Average Data segment larger than 500 bytes (actual: %d)" % (mean - 12))

    @weight(2.5)
    @visibility("visible")
    def test2_4(self):
        """2.4 Client should reset its sequence number to zero when the sequence number reaches the maximum value"""

        (server, client) = self.test2_1(small=False)

        df = server.getStats(True)
        df = df[df.cmd == 'RECV']

        wrap = df[df.seqno > 102400 - 512]
        self.assertGreaterEqual(len(wrap), 1, "Not enough sent data")

        subset = df.loc[wrap.index[0]:]
        i = 0
        while subset.iloc[i].seqno > 102400 - 512:
            i += 1

        self.assertGreater(subset.iloc[0].seqno, 102400 - 512, "Seqno before wrap should be > 102400 - 512")
        self.assertLess(subset.iloc[i].seqno, 512, "Seqno after wrap should be < 512")

    @weight(2.5)
    @visibility("visible")
    def test2_5(self):
        """2.5. Client sends a FIN packet after transmitting a file"""

        (server, client) = self.test2_1()
        df = server.getStats(True)
        def hasFin(l):
            return ('FIN' in l)

        df = df[(df.cmd == 'RECV') & (df.flgs.apply(hasFin))]
        self.assertGreaterEqual(len(df), 1, "Client didn't send FIN")

    @weight(2.5)
    @visibility("visible")
    def test2_6(self):
        """2.6. After finishing connection, client responds with ACK for incoming FINs for 2 seconds, dropping packets for this connection afterwards"""

        # Xinyu Ma: The logic of this test was wrong. The server is not promised to send a FIN when it is killed.

        ClientTests.portOffset += 1
        file = self.FILE_10k

        server = self.startReference('server', [str(self.PORTNO + ClientTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('spying-proxy.py', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset),
                                                          self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset + 100)])
        client = self.startSubmission('client', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset), file])

        # os.system("date +%s.%N >&2")

        try:
            client.wait(60)
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

        self.assertNotEqual(server.stdout, '', 'Server did not create any output')

        df = server.getStats(True)
        def hasFin(l):
            return ('FIN' in l)

        df = df[(df.cmd == 'SEND') & (df.flgs.apply(hasFin))]
        # os.system("date +%s.%N >&2")
        self.assertGreaterEqual(len(df), 1, "Server didn't send FIN")

        # clientPort = proxy.stdout.strip()
        # serverPort = str(self.PORTNO + ClientTests.portOffset)
        # seqNo = str(df.iloc[0].seqno)
        # id = str(df.iloc[0].id)

        # server = self.startReference('send-fin.py', [self.HOSTNAME, clientPort, self.HOSTNAME, serverPort, seqNo, id])
        # server.wait(1)

        # time.sleep(2)
        # server = self.startReference('send-fin.py', [self.HOSTNAME, clientPort, self.HOSTNAME, serverPort, seqNo, id])
        # server.wait(1)

        self.assertEqual(client.is_alive(), False, "Client didn't exit after finishing the transmission")
        self.assertEqual(client.retcode, 0, "Client exit code is not zero (%d, stderr: %s)" % (client.retcode, client.stderr))

        self.assertNotEqual(client.stdout, '', 'Client did not create any output')

        df = client.getStats()
        df1 = df[(df.cmd == 'RECV') & (df.flgs.apply(hasFin))]

        for index, row in df1.iterrows():
            self.assertLess(index + 1, len(df), "Client shutdown after receiving FIN without sending ACK")
            self.assertTrue('ACK' in df.loc[index+1]['flgs'], 'RECV FIN must be followed by SEND ACK')

        self.assertGreaterEqual(len(df1), 2, "FIN should be processed within 2 seconds after connection close")

    @weight(5)
    @visibility("after_published")
    def test2_7(self):
        """2.7. Client successfully transmits a small file"""

        (server, client) = self.test2_1(checkFile=True)

    @weight(5)
    @visibility("after_published")
    def test2_8(self):
        """2.8. Client aborts the connection if no incoming packets for more than 10 seconds"""

        ClientTests.portOffset += 1
        file = self.FILE_10k

        server = self.startReference('server', [str(self.PORTNO + ClientTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('broken-proxy.py', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset),
                                                 self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset + 100)])
        client = self.startSubmission('client', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset), file])

        client.wait(15) # should have aborted the connection, as server not accepting data
        self.assertEqual(client.is_alive(), False, "Client didn't exit after finishing the transmission")
        self.assertNotEqual(client.retcode, 0, "Client exit code should have been non-zero (%d, stderr: %s)" % (client.retcode, client.stderr))

        try:
            server.wait(1)
        except AssertionError:
            pass

        try:
            proxy.wait(1)
        except AssertionError:
            pass

    @weight(5)
    @visibility("visible")
    def test2_9(self):
        """2.9. Client properly increases congestion window size in slow start phase"""

        (server, client) = self.test2_1(small=False)

        df = client.getStats()
        df = df[df.cmd == 'RECV']

        prev = None
        for index, row in df.iterrows():
            if 'SYN' in row['flgs']:
                continue

            if 'FIN' in row['flgs']:
                continue

            if prev is None:
                prev = row
                continue

            if row.ack > prev.ack and prev.cwnd < prev.ssthresh:
                self.assertGreater(row.cwnd - prev.cwnd, 400, "Insufficient increase of CWND in SlowStart (only %d for seqno %d, ack %d)" % (row.cwnd - prev.cwnd, row.seqno, row.ack))

            prev = row

    @weight(5)
    @visibility("after_published")
    def test2_10(self):
        """2.10. Client properly increases congestion window size in congestion avoidance phase"""

        (server, client) = self.test2_1(small=False)

        df = client.getStats()
        df = df[df.cmd == 'RECV']

        prev = None
        for index, row in df.iterrows():
            if 'SYN' in row['flgs']:
                continue

            if 'FIN' in row['flgs']:
                continue

            if prev is None:
                prev = row
                continue

            if row.ack > prev.ack and prev.cwnd >= prev.ssthresh:
                self.assertLess(row.cwnd - prev.cwnd, 50, "Too large increase of CWND in CongestionAvoidance (%d for seqno %d, ack %d)" % (row.cwnd - prev.cwnd, row.seqno, row.ack))

            prev = row

    @weight(5)
    @visibility("visible")
    def test2_11(self):
        """2.11. Client detects and retransmits lost data segments"""

        ClientTests.portOffset += 1
        file = self.FILE_10k

        server = self.startReference('server', [str(self.PORTNO + ClientTests.portOffset + 100), self.absoluteFolder])
        proxy = self.startReference('loss-proxy.py', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset),
                                                 self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset + 100)])
        client = self.startSubmission('client', [self.HOSTNAME, str(self.PORTNO + ClientTests.portOffset), file])

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
        def hasDup(l):
            return ('DUP' in l)
        df = df[(df.cmd == 'SEND') & (df.flgs.apply(hasDup))]

        (diff, diffret) = self.runApp('diff "%s" "%s/1.file"' % (file, self.absoluteFolder))
        self.assertEqual(diffret, 0, "The saved file is different from the original")

        self.assertGreaterEqual(len(df), 1, "Segment must have been retransmitted after timeout")

        return (server, client)

    @weight(5)
    @visibility("visible")
    def test2_12(self):
        """2.12. Client sets SS-THRESH and CWND values properly after timeout"""

        (server, client) = self.test2_11()

        df = client.getStats()
        df = df[df.cmd != 'DROP']

        prev = None
        processed = False
        for index, row in df.iterrows():
            if 'SYN' in row['flgs']:
                continue

            if 'FIN' in row['flgs']:
                continue

            if prev is None:
                prev = row
                continue

            if 'DUP' in row['flgs']:
                processed = True
                self.assertAlmostEqual(prev.cwnd / 2, row.ssthresh, 0, "Incorrect setting for SSTHRESH adjustment after timeout (%d != %d)" % (prev.cwnd / 2, row.ssthresh))
                self.assertEqual(row.cwnd, 512, "Incorrect setting for CWND adjustment after timeout")
                break

            prev = row

        self.assertTrue(processed, "Loss was not detected")
