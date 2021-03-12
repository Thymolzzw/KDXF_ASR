import audioop
import math
import multiprocessing
import os
import subprocess
import tempfile
import wave

import pysrt
import six

from KDXF_api import ASR, Converter

class Subtitle:

    def which(self, program):
        """
        Return the path for a given executable.
        """
        def is_exe(file_path):
            """
            Checks whether a file is executable.
            """
            return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

        fpath, _ = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                path = path.strip('"')
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file
        return None


    def extract_audio(self, filename, channels=1, rate=16000):
        """
        Extract audio from an input file to a temporary WAV file.
        """
        temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        if not os.path.isfile(filename):
            print("The given file does not exist: {}".format(filename))
            raise Exception("Invalid filepath: {}".format(filename))
        if not self.which("ffmpeg"):
            # print("ffmpeg: Executable not found on machine.")
            # raise Exception("Dependency not found: ffmpeg")
            pass
        command = ["ffmpeg", "-y", "-i", filename,
                   "-ac", str(channels), "-ar", str(rate),
                   "-loglevel", "error", temp.name]
        use_shell = True if os.name == "nt" else False
        subprocess.check_output(command, stdin=open(os.devnull), shell=use_shell)
        # print(temp.name)
        return temp.name, rate


    def percentile(self, arr, percent):
        """
        Calculate the given percentile of arr.
        """
        arr = sorted(arr)
        index = (len(arr) - 1) * percent
        floor = math.floor(index)
        ceil = math.ceil(index)
        if floor == ceil:
            return arr[int(index)]
        low_value = arr[int(floor)] * (ceil - index)
        high_value = arr[int(ceil)] * (index - floor)
        return low_value + high_value


    def find_speech_regions(self, filename, frame_width=4096, min_region_size=0.5, max_region_size=6): # pylint: disable=too-many-locals
        """
        Perform voice activity detection on a given audio file.
        """
        reader = wave.open(filename)
        sample_width = reader.getsampwidth()
        rate = reader.getframerate()
        n_channels = reader.getnchannels()
        chunk_duration = float(frame_width) / rate

        n_chunks = int(math.ceil(reader.getnframes()*1.0 / frame_width))
        energies = []

        for _ in range(n_chunks):
            chunk = reader.readframes(frame_width)
            energies.append(audioop.rms(chunk, sample_width * n_channels))

        threshold = self.percentile(energies, 0.2)

        elapsed_time = 0

        regions = []
        region_start = None

        for energy in energies:
            is_silence = energy <= threshold
            max_exceeded = region_start and elapsed_time - region_start >= max_region_size

            if (max_exceeded or is_silence) and region_start:
                if elapsed_time - region_start >= min_region_size:
                    regions.append((region_start, elapsed_time))
                    region_start = None

            elif (not region_start) and (not is_silence):
                region_start = elapsed_time
            elapsed_time += chunk_duration
        return regions

    def srt_formatter(self, subtitles, padding_before=0, padding_after=0):
        """
        Serialize a list of subtitles according to the SRT format, with optional time padding.
        """
        sub_rip_file = pysrt.SubRipFile()
        for i, ((start, end), text) in enumerate(subtitles, start=1):
            item = pysrt.SubRipItem()
            item.index = i
            item.text = six.text_type(text)
            item.start.seconds = max(0, start - padding_before)
            item.end.seconds = end + padding_after
            sub_rip_file.append(item)
        return '\n'.join(six.text_type(item) for item in sub_rip_file)


    def generate_subtitles(self,
            source_path,
            concurrency=10,
            src_language='en_us',
            out_file_path='default.srt'
        ):
        """
        Given an input audio/video file, generate subtitles in the specified language and format.
        """
        audio_filename, audio_rate = self.extract_audio(source_path)

        regions = self.find_speech_regions(audio_filename)

        # print("regions", regions)

        pool = multiprocessing.Pool(concurrency)
        asr = ASR(language=src_language)
        converter = Converter(source_path=audio_filename)

        transcripts = []
        if regions:
            try:
                extracted_regions_files = []
                for i, extracted_regions_file in enumerate(pool.imap(converter, regions)):
                    extracted_regions_files.append(extracted_regions_file)
                # print("extracted_regions_files", extracted_regions_files)
                for i, transcript in enumerate(pool.imap(asr, extracted_regions_files)):
                    transcripts.append(transcript)
                # print("transcripts", transcripts)

            except KeyboardInterrupt:
                pool.terminate()
                pool.join()
                print("Cancelling transcription")
                raise

        timed_subtitles = [(r, t) for r, t in zip(regions, transcripts) if t]
        os.remove(audio_filename)

        # print(timed_subtitles)

        formatted_subtitles = self.srt_formatter(timed_subtitles)
        with open(out_file_path, 'wb') as output_file:
            output_file.write(formatted_subtitles.encode("utf-8"))



if __name__ == '__main__':
    subtitle = Subtitle()
    subtitle.generate_subtitles(source_path='wed.mkv', src_language='en_us',
                                out_file_path="wed.srt")
