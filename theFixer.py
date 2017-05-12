#!/usr/bin/python

import os
import sys
import re
import shutil
import subprocess


# Edit options here ##################################################
outmode = 'mp4'                          #Extension of file
remover = True                           # Delete original file after conversion complete
accept_ext = '3gp flv mov mp4 mkv avi divx m4v mpeg mpg wmv ts'   #Extensions of video files to convert

temp_path = "/tmp"                #Directory for encode prior to moving back
ffmpeg_exe = "ffmpeg"                #Path to ffmpeg executable
ffprobe_exe = "ffprobe"              #Path to ffprove executable
mkvextract_exe = "mkvextract"        #Path to mkvextract executable
video_codec = 'libx264'                  #Video codec to use
video_type = 'h264'                      #Name of video codec to check for remux
audio_codec = 'aac'               #Audio codec to use
audio_type = 'aac'                       #Name of audio codec to check for remux
crf = "18"                               #Video quality for libx264
vbr = ''                                 #Audio quality
extract_subtitle = True                  #Extract subtitles?
subtitle_languages = "en eng english"    #Codes for languages to extract
threads = 16                             #Number of threads to use in ffmpeg, 0 defaults to all
additional_ffmpeg = '-preset slow -movflags +faststart'     #Additional flags for ffmpeg, preset sets speed and compression, movflags to make file web optimized

## END OPTIONS - DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING ##

outformat = 'mp4'
if outmode == 'mp4':
    outformat = 'mp4'
elif outmode == 'mkv':
    outformat = 'matroska'


def ffmpeg(*args, **kwargs):
    largs = [ffmpeg_exe, ]
    largs.extend(args)
    try:
        return subprocess.check_output(largs, **kwargs).decode('utf-8')
    except:
        return None

def getoutput(cmd):
    if sys.version < '3':
        try:
            return subprocess.check_output(cmd.split(' '))
        except:
            return None
    else:
        return subprocess.getoutput(cmd)

formats = ""
if getoutput(ffmpeg_exe + ' -formats'):
    formats = getoutput(ffmpeg_exe + ' -formats 2')
else:
    exit(1)

if ('E mp4' in formats) and ('E matroska' in formats):
    print("You have the suitable formats")
else:
    print("You do not have both the mkv and mp4 formats...Exiting!")
    exit(1)

codecs = getoutput(ffmpeg_exe + ' -codecs 2')

if video_codec in codecs:
    print("Check " + video_codec + " Audio Encoder ... OK")
else:
    print("Check " + video_codec + " Audio Encoder ... NOK")
    exit(1)

if audio_codec in codecs:
    print("Check " + audio_codec + " Audio Encoder ... OK")
else:
    print("Check " + audio_codec + " Audio Encoder ... NOK")
    exit(1)

print("Your FFMpeg is OK\nEntering File Processing\n")

subtitle_languages = subtitle_languages.lower()

def process_file(path, file):
    extension = os.path.splitext(file)[1].replace(".", "").lower()
    filename = os.path.splitext(file)[0]

    if extension in accept_ext:
        print(file + " is an acceptable extension. Checking file...")
    else:
        print(file + " is not an acceptable extension. Skipping...")
        return

    if ffprobe_exe:
        file_info = subprocess.check_output([ffprobe_exe, os.path.join(path, file)], stderr=subprocess.STDOUT)
    else:
        file_info = ffmpeg("-i", os.path.join(path, file))

    print(file_info)
    if 'Invalid data found' in file_info:
        print("File " + file + " is NOT A VIDEO FILE cannot be converted!")
        return

    encode_crf = []
    if file_info.find("Video: " + video_type) != -1:
        vcodec = 'copy'
        print("Video is " + video_type + ", remuxing....")
    else:
        vcodec = video_codec
        if crf:
            encode_crf = ["-crf", "" + crf]
        print("Video is not " + video_type + ", converting...")

    encode_vbr = []
    if "Audio: " + audio_type in file_info:
        acodec = 'copy'
        print("Audio is " + audio_type + ", remuxing....")
    else:
        acodec = audio_codec
        if vbr:
            encode_vbr = ["-vbr", "" + vbr]
        print("Audio is not " + audio_type + ", converting...")

    if extension == outmode and vcodec == 'copy' and acodec == 'copy':
        print(file + " is already " + outmode + " and no conversion needed. Skipping...")
        return

    print(
        "Using video codec: " + vcodec + " audio codec: " + acodec + " and Container format " + outformat + " for\nFile: " + file + "\nStarting Conversion...\n")

    filename = filename.replace("XVID", video_type)
    filename = filename.replace("xvid", video_type)

    try:
        args = ['-i', os.path.join(path, file), '-y', '-f', outformat, '-acodec', acodec]
        if encode_vbr:
            args.extend(encode_vbr)
        args.extend(['-vcodec', vcodec])
        if encode_crf:
            args.extend(encode_crf)
        if additional_ffmpeg:
            args.extend(additional_ffmpeg.split(" "))
        if threads:
            args.extend(['-threads', str(threads)])
        if temp_path:
            args.append(os.path.join(temp_path, filename + '.temp'))
        else:
            args.append(os.path.join(path, filename + '.temp'))
        ffmpeg(*args)
        print("")
    except Exception as e:
        print("Error: %s" % e)
        print("Removing temp file and skipping file")
        if temp_path:
            if os.path.isfile(os.path.join(temp_path, filename + '.temp')):
                os.remove(os.path.join(temp_path, filename + '.temp'))
        else:
            if os.path.isfile(os.path.join(path, filename + '.temp')):
                os.remove(os.path.join(path, filename + '.temp'))
        return

    if extract_subtitle and (file_info.find("Subtitle:") != -1):
        print("Extracting Subtitles")
        matches = re.finditer("Stream #(\d+):(\d+)\((\w+)\): Subtitle: (.*)", file_info)
        for m in matches:
            if m.group(3).lower() not in subtitle_languages.split(" "):
                continue
            try:
                if 'subrip' in m.group(4):
                    sub_format = 'copy'
                    sub_ext = '.srt'
                elif mkvextract_exe and 'hdmv_pgs' in m.group(4):
                    subprocess.check_output([mkvextract_exe, 'tracks', os.path.join(path, file),
                                             m.group(2) + ':' + os.path.join(path, filename + '.' + m.group(
                                                 3) + '.' + m.group(2) + '.sup')])
                    continue
                else:
                    sub_format = 'srt'
                    sub_ext = '.srt'
                ffmpeg("-i", os.path.join(path, file), '-y', '-map', m.group(1) + ':' + m.group(2), '-c:s:0',
                       sub_format,
                       os.path.join(path, filename + '.' + m.group(3) + '.' + m.group(2) + sub_ext))
                print("")
            except Exception as e:
                print("Error: %s" % e)
                print("Deleting subtitle.")
                if os.path.isfile(os.path.join(path, filename + '.' + m.group(3) + '.' + m.group(2) + sub_ext)):
                    os.remove(re.escape(os.path.join(path, filename + '.' + m.group(3) + '.' + m.group(2) + sub_ext)))

    if remover:
        print("Deleting original file: " + file)
        os.remove(os.path.join(path, file))

#    if outmode == extension:
#        shutil.move(os.path.join(path, filename + ".temp"), os.path.join(path, filename + ".enc." + outmode))
#        filename += ".enc"
#    else:
    if temp_path:
        shutil.move(os.path.join(temp_path, filename + ".temp"), os.path.join(path, filename + "." + outmode))
    else:
        shutil.move(os.path.join(path, filename + ".temp"), os.path.join(path, filename + "." + outmode))


def process_directory(path):
    if os.path.isfile(os.path.join(path, ".noconvert")):
        return
    for file in sorted(os.listdir(path)):
        filepath = os.path.join(path, file)
        if os.path.isdir(filepath):
            process_directory(filepath)
        elif os.path.isfile(filepath):
            process_file(path, file)


for arg in sys.argv[1:]:
    if os.path.isdir(arg):
        process_directory(arg)
    elif os.path.isfile(arg):
        process_file(os.path.dirname(arg), os.path.basename(arg))

