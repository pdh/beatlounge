import time
import wave
import struct
import sys

from warnings import warn
try:
    import pyaudio
except ImportError:
    warn('(bl.wavplayer) requirement pyaudio not available - try installing')
    pyaudio = None

from zope.interface import Interface, Attribute, implements

from twisted.python import log
from twisted.python.components import proxyForInterface
from twisted.internet.task import coiterate
from twisted.internet.interfaces import IConsumer, IPushProducer

from bl.debug import DEBUG


DEFAULT_CHUNK_SIZE = 4096 / 2


__all__ = ['PyAudioManager', 'WavPlayer', 'IAudioStream', 'IAudioSource',
           'WavFileReader', 'AudioStream']


class PyAudioManager:

    pyaudio = None

    @classmethod
    def init(cls):
        """
        An idempodent init for pyaudio runtime.
        """
        if cls.pyaudio is None:
            cls.pyaudio = pyaudio.PyAudio()
        return cls.pyaudio

    @classmethod
    def getDeviceIndexByName(cls, name, type=None):
        p = cls.init()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if type == 'output':
                if info['name'] == name and info['maxOutputChannels']:
                    return i
            elif type == 'input':
                if info['name'] == name and info['maxInputChannels']:
                    return i
            else:
                if info['name'] == name:
                    return i


class IAudioStream(IConsumer):

    def availableWrite():
        """
        Get number of bytes available to write in stream's buffer.
        """


class IAudioSource(IPushProducer):

    def beingStreaming(stream):
        """
        Begin streaming bytes of audio to a stream (IAudioStream).
        This returns a called which will fire when streaming pauses
        or stops.
        """


class ISeekableAudioSource(Interface):

    def seek(offset):
        """
        Seek to indexed sample (offset) in the audio source.
        """


class IPlayer(Interface):

    source = Attribute("An IAudioSource provider")
    stream = Attribute("An IAudioStream provider")

    def play():
        """
        Begin playing audio - call beginStreaming() on source.
        """

    def pause():
        """
        Pause - call pauseProducing() on source.
        """

    def resume():
        """
        Resume - call resumeProducing() on source.
        """

    def stop():
        """
        Pause playing and finalize source and stream. play() should
        not be called after stop() - use pause() and resume() to
        temporarily stop and then resume playback.
        """

class WavPlayer:
    implements(IPlayer)

    def __init__(self, stream, source):
        """
        stream: L{IAudioStream}
        source: L{IAudioSource}
        """
        self.stream = stream
        self.source = source

    @classmethod
    def fromPath(cls, path, chunkSize=DEFAULT_CHUNK_SIZE, loop=False, deviceName=None):
        """
        Convenience method to create an WavPlayer from a filesystem path.
        This creates a news player with an AudioStream and WavFileReader.
        """
        wf = wave.open(path, 'rb')
        p = PyAudioManager.init()
        if deviceName is None:
            index = p.get_default_output_device_info()['index']
        else:
            index = PyAudioManager.getDeviceIndexByName(deviceName, type='output')
        s = p.open(
                format = p.get_format_from_width(wf.getsampwidth()),
                channels = wf.getnchannels(),
                rate = wf.getframerate(),
                output_device_index = index,
                output = True)
        stream = AudioStream(s)
        source = WavFileReader(wf, chunkSize=chunkSize, loop=loop)
        return cls(stream, source)

    @classmethod
    def fromInput(cls, inputDeviceName=None, outputDeviceName=None, chunkSize=DEFAULT_CHUNK_SIZE):
        """
        Convenience method to create an WavPlayer which uses a pyaudio input as its
        source.
        """
        p = PyAudioManager.init()
        if inputDeviceName is None:
            info = p.get_default_input_device_info()
            log.msg('using default input device: %s' % info['name'])
            inputIndex = info['index']
        else:
            inputIndex = PyAudioManager.getDeviceIndexByName(inputDeviceName, type='input')
        if outputDeviceName is None:
            info = p.get_default_output_device_info()
            log.msg('using default output device: %s' % info['name'])
            outputIndex = info['index']
        else:
            outputIndex = PyAudioManager.getDeviceIndexByName(outputDeviceName, type='output')
        stream_info = None
        if sys.platform == 'darwin':
            stream_info = pyaudio.PaMacCoreStreamInfo(
                    flags = pyaudio.PaMacCoreStreamInfo.paMacCorePlayNice,
                    channel_map = (0, 1))
        ins = p.open(
                format = pyaudio.paInt16,
                channels = 2,
                rate = 44100,
                input_device_index = inputIndex,
                input = True,
                #input_host_api_specific_stream_info = stream_info,
                frames_per_buffer=chunkSize)
        outs = p.open(
                format = pyaudio.paInt16,
                channels = 2,
                rate = 44100,
                output_device_index = outputIndex,
                output = True,
                #output_host_api_specific_stream_info = stream_info)
                )
        stream = AudioStream(outs)
        source = AudioInput(ins, chunkSize=chunkSize)
        return cls(stream, source)

    def play(self):
        return self.source.beginStreaming(self.stream)

    def pause(self):
        self.source.pauseProducing()

    def resume(self):
        return self.source.resumeProducing()

    def stop(self):
        self.source.stopProducing()



class AudioStream:
    implements(IAudioStream)

    _source = None

    def __init__(self, stream):
        """
        stream: a pyuadio stream instance
        """
        self.stream = stream

    def registerProducer(self, source, streaming):
        self._source = source

    def unregisterProducer(self):
        self._source = None
        self.stream.close()

    def write(self, data):
        self.stream.write(data)

    def availableWrite(self):
        return self.stream.get_write_available()


class _StreamerBase:
    stream = None
    _streaming = False

    def beginStreaming(self, stream):
        self.stream = stream
        self.stream.registerProducer(self, True)
        self._streaming = True
        return coiterate(self._stream())

    def pauseProducing(self):
        self._streaming = False

    def resumeProducing(self):
        self._streaming = True
        return coiterate(self._stream())

    def _stream(self):
        raise NotImplementedError()

class AudioInput(_StreamerBase):
    implements(IAudioSource)

    def __init__(self, pyaudioStream, chunkSize=DEFAULT_CHUNK_SIZE):
        self._pyaudioStream = pyaudioStream
        self.chunkSize = chunkSize

    def _stream(self):
        while self._streaming:
            data = self._try_read()#self._pyaudioStream.read(self.chunkSize)
            while self._streaming:
                avl = self.stream.availableWrite()
                if DEBUG:
                    log.msg('write available: %s' % avl)
                if avl >= self.chunkSize:
                    if data:
                        self.stream.write(data)
                    data = self._try_read()#self._pyaudioStream.read(self.chunkSize)
                    yield data

    def _try_read(self):
        try:
            return self._pyaudioStream.read(self.chunkSize)
        except Exception, e:
            return ''


class WavFileReader:
    implements(IAudioSource, ISeekableAudioSource)

    stream = None
    _streaming = False

    def __init__(self, wavfile, chunkSize=DEFAULT_CHUNK_SIZE, loop=False):
        self.wavfile = wavfile
        self.chunkSize = chunkSize
        self.loop = loop

    def beginStreaming(self, stream):
        self.stream = stream
        self.stream.registerProducer(self, True)
        self._streaming = True
        return coiterate(self._stream())

    def _stream(self):
        while self._streaming:
            data = self.wavfile.readframes(self.chunkSize)
            while data and self._streaming:
                avl = self.stream.availableWrite()
                if DEBUG:
                    log.msg('write available: %s' % avl)
                if avl >= self.chunkSize:
                    self.stream.write(data)
                    data = self.wavfile.readframes(self.chunkSize)
                    yield data
            if self.loop and self._streaming:
                self.wavfile.setpos(0)
            else:
                break
        self._streaming = False

    def pauseProducing(self):
        self._streaming = False

    def resumeProducing(self):
        self._streaming = True
        return coiterate(self._stream())

    def stopProducing(self):
        self.pauseProducing()
        self.wavfile.close()
        self.stream.unregisterProducer()

    def seek(self, offset):
        self.wavfile.setpos(offset)


class AudioNode(proxyForInterface(IAudioStream, originalAttribute='stream')):

    def __init__(self, stream):
        self.stream = stream


class _AudioTransformMixin:

    def setFormat(self, format=pyaudio.paInt16):
        assert format in (pyaudio.paInt16,)
        if format == pyaudio.paInt16:
            self._cast = int
            self._bytes = 2
            self._format = 'h'

    def transform(self, data, func):
        buffer = []
        for i in range(0, len(data), self._bytes):
            f = struct.unpack(self._format, data[i:i+self._bytes])
            buffer.append(struct.pack(self._format, self._cast(func(f[0]))))
        return ''.join(buffer)


class Filter(AudioNode, _AudioTransformMixin):

    def __init__(self, stream, format=pyaudio.paInt16):
        self.setFormat(format)
        super(Filter, self).__init__(stream)

    def write(self, data):
        self.stream.write(self.transform(data, self.filter))

    def filter(self, n):
        return n

class Volume(Filter):

    volume = 1.0

    def filter(self, n):
        return n * self.volume


class Delay(Filter):

    def __init__(self, stream, format=pyaudio.paInt16, decay=0.95, samples=44100/2):
        Filter.__init__(self, stream, format)
        self._delay_buffer = []
        self.decay = decay
        self.samples = samples

    def filter(self, n):
        if len(self._delay_buffer) > self.samples:
            n = (n + self._delay_buffer.pop(0) * self.decay) * 0.5
        self._delay_buffer.append(n)
        return n


