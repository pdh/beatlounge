from pprint import pformat
from itertools import cycle

from twisted.trial.unittest import TestCase

from txbeatlounge.testlib import ClockRunner, TestReactor
from txbeatlounge import arp
from txbeatlounge.player import N
from txbeatlounge.scheduler import BeatClock
from txbeatlounge.arp import (AscArp, DescArp, OrderedArp, RandomArp, OctaveArp,
    Adder, PhraseRecordingArp)

class ArpTests(TestCase):


    def setUp(self):
        self.arpeggio = arpeggio = [ 0, 2, 1, 3 ]
        self.ascArp = AscArp(arpeggio)
        self.descArp = DescArp(arpeggio)
        self.ordArp = OrderedArp(arpeggio)
        self.randArp = RandomArp(arpeggio)

    def test_ascArp(self):
        arpeggio = []
        for i in range(8):
            arpeggio.append(self.ascArp())
        self.assertEquals(arpeggio, [0,1,2,3,0,1,2,3])

    def test_descArp(self):
        arpeggio = []
        for i in range(8):
            arpeggio.append(self.descArp())
        self.assertEquals(arpeggio, [3,2,1,0,3,2,1,0])

    def test_orderedArp(self):
        arpeggio = []
        for i in range(8):
            arpeggio.append(self.ordArp())
        self.assertEquals(arpeggio, [0,2,1,3,0,2,1,3])

    def test_randomArp(self):
        r = cycle([1, 2, 0, 0, 2, 0, 1, 0])
        class random:
            @classmethod
            def randint(cls, *blah):
                return r.next()
        self.patch(arp, 'random', random)

        arpeggio = []
        for i in range(8):
            arpeggio.append(self.randArp())
        self.assertEquals(arpeggio, [2, 3, 0, 1, 0, 2, 1, 3])

    def test_numeric_sorting(self):
        """
        Test that numeric values are sorted correctly and
        non-numeric values retain their position in the arpeggio.
        """
        arpeggio = []
        ascarp = AscArp([1, 3, N, 2])
        for i in range(8):
            arpeggio.append(ascarp())
        self.assertEquals(arpeggio, [1,2,None,3,1,2,None,3])

    def test_resetting(self):
        """
        Test various behaviors of resetting values on an arp midstream.
        """

        arpeggio = []
        for i in range(2):
            arpeggio.append(self.ascArp())
        self.ascArp.reset([5,6,7,8])
        for i in range(2):
            arpeggio.append(self.ascArp())
        self.assertEquals(arpeggio, [0,1,7,8])

        arpeggio = []
        self.ascArp.reset([0,1,2,3])
        for i in range(3):
            arpeggio.append(self.ascArp())
        self.ascArp.reset([5,6])
        arpeggio.append(self.ascArp())
        self.assertEquals(arpeggio, [0,1,2,6])

        arpeggio = []
        self.ascArp.reset([0,1,2,3])
        for i in range(3):
            arpeggio.append(self.ascArp())
        self.ascArp.reset([4,5,6,7,8,9,10,11])
        arpeggio.append(self.ascArp())
        self.assertEquals(arpeggio, [0,1,2,10])

        arpeggio = []
        for i in range(2):
            arpeggio.append(self.descArp())
        self.descArp.reset([5,6,7,8])
        for i in range(2):
            arpeggio.append(self.descArp())
        self.assertEquals(arpeggio, [3,2,6,5])

        arpeggio = []
        self.descArp.reset([0,1,2,3])
        for i in range(3):
            arpeggio.append(self.descArp())
        self.descArp.reset([5,6])
        arpeggio.append(self.descArp())
        self.assertEquals(arpeggio, [3,2,1,5])

        arpeggio = []
        self.descArp.reset([0,1,2,3])
        for i in range(3):
            arpeggio.append(self.descArp())
        self.descArp.reset([4,5,6,7,8,9,10,11])
        arpeggio.append(self.descArp())
        self.assertEquals(arpeggio, [3,2,1,5])

    def test_octave_arp_ascending(self):
        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4])
        for i in range(20):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 1, 2, 3, 4,
              13, 14, 15, 16,
              25, 26, 27, 28,
              37, 38, 39, 40,
              1, 2, 3, 4 ])

        arpeggio = []
        octaveArp = OctaveArp(DescArp(), [1,2,3,4])
        for i in range(20):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 4, 3, 2, 1,
              16, 15, 14, 13,
              28, 27, 26, 25,
              40, 39, 38, 37,
              4, 3, 2, 1 ])

        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4], 1)
        for i in range(12):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 1, 2, 3, 4, 13, 14, 15, 16, 1, 2, 3, 4 ])

    def test_octave_arp_descending(self):
        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4], direction=-1)
        for i in range(20):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 37, 38, 39, 40,
              25, 26, 27, 28,
              13, 14, 15, 16,
              1, 2, 3, 4,
              37, 38, 39, 40, ])

    def test_octave_arp_with_0_octaves(self):
        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4], 0)
        for i in range(8):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 1, 2, 3, 4, 1, 2, 3, 4 ])


    def test_octave_arp_oscillate(self):
        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4], oscillate=True)
        for i in range(36):
            arpeggio.append(octaveArp())
        self.assertEquals(arpeggio,
            [ 1, 2, 3, 4,
              13, 14, 15, 16,
              25, 26, 27, 28,
              37, 38, 39, 40,
              25, 26, 27, 28,
              13, 14, 15, 16,
              1, 2, 3, 4,
              13, 14, 15, 16,
              25, 26, 27, 28 ])

    def test_adder(self):
        arpeggio = []
        octaveArp = OctaveArp(AscArp(), [1,2,3,4])
        adder = Adder(octaveArp)
        for i in range(16):
            arpeggio.append(adder())
        self.assertEquals(arpeggio,
            [ 1, 2, 3, 4,
              13, 14, 15, 16,
              25, 26, 27, 28,
              37, 38, 39, 40 ])
        adder.amount = 2
        arpeggio = []
        for i in range(16):
            arpeggio.append(adder())
        self.assertEquals(arpeggio,
            [ v+2 for v in
                [ 1, 2, 3, 4,
                  13, 14, 15, 16,
                  25, 26, 27, 28,
                  37, 38, 39, 40 ]])

    def test_empty_arps(self):
        for klass in (AscArp, DescArp, OrderedArp):
            a = klass([])
            for i in range(4):
                n = a()


class PhraseRecordingArpTests(TestCase, ClockRunner):

    def setUp(self):
        self.clock = BeatClock(135, reactor=TestReactor())
        self.phraseRecorder = PhraseRecordingArp(self.clock)


    def test_phrase_recording(self):
        clock, phraseRecorder = self.clock, self.phraseRecorder

        self.runTicks(96 * 4)
        phrase = phraseRecorder()
        self.failIf(list(phrase))

        self.runTicks(24)
        phraseRecorder.recordNoteOn(60, 110)
        self.runTicks(12)
        phraseRecorder.recordNoteOff(60)
        self.runTicks(96)
        phraseRecorder.recordNoteOn(64, 90)
        self.runTicks(48)
        phraseRecorder.recordNoteOn(67, 90)
        self.runTicks(72)
        phraseRecorder.recordNoteOff(67)
        self.runTicks(130)
        phraseRecorder.recordNoteOff(64)
        self.runTicks(2)

        phrase = phraseRecorder()
        self.assertEquals(phrase,
            [(24, 60, 110, 12), (132, 64, 90, 250), (180, 67, 90, 72)])

        self.runTicks(96 * 4)
        phrase = phraseRecorder()
        self.assertEquals(phrase,
            [(24, 60, 110, 12), (132, 64, 90, 250), (180, 67, 90, 72)])


    def test_noteoff_from_past_phrase(self):
        """
        todo - we should handle noteoff from past phrases better - maybe
        adjust corresponding sustain in the past recorded phrase somehow.
        """
        clock, phraseRecorder = self.clock, self.phraseRecorder
        phraseRecorder.recordNoteOn(60, 120)
        self.runTicks(96)
        phrase = phraseRecorder()
        # note we guess the sustain to be 96 (clock.ticks - when)
        self.assertEquals(phrase, [(0, 60, 120, 96)])
        self.runTicks(24)
        phraseRecorder.recordNoteOff(60)
        self.runTicks(72)
        phrase = phraseRecorder()
        self.failIf(self.flushLoggedErrors())
        # note how the past phrase got updated with a prolonged sustain
        self.assertEquals(phrase, [(0, 60, 120, 120)])


