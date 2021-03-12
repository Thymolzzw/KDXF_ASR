from pydub import AudioSegment
from pydub.silence import split_on_silence
import os

from moviepy.editor import *


path = "testzzw.mp4"
audio_path = 'testzzw.wav'
audiotype = 'wav'

video = VideoFileClip(path)
audio = video.audio
audio.write_audiofile(audio_path)

sound = AudioSegment.from_file(audio_path, format=audiotype)
# sound = sound[:3 * 60 * 1000]

print('开始分割')
chunks = split_on_silence(sound, min_silence_len=500,
                          silence_thresh=-100)  # min_silence_len: 拆分语句时，静默满1秒则拆分。silence_thresh：小于-70dBFS以下的为静默。
# 创建保存目录

chunks_path = './chunks/'
print(chunks_path)
if not os.path.exists(chunks_path):
    os.mkdir(chunks_path)
# 保存所有分段
print('开始保存')

print(chunks)
print(len(chunks))
for i in range(len(chunks)):
    new = chunks[i]
    save_name = chunks_path + '%04d.%s' % (i, audiotype)
    new.export(save_name, format=audiotype)
    print('%04d' % i, len(new))
print('保存完毕')