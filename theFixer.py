#!/usr/bin/python

import os
import sys
import re
import shutil
import subprocess
import argparse
import ffmpy
import json
import datetime

# Edit options here ##################################################
outmode = 'mp4'                                                     #Extension of output file
outformat = 'mp4'                                                   #Format of output file
remover = True                                                      #Delete original file after conversion complete
accept_ext = '3gp flv mov mp4 mkv avi divx m4v mpeg mpg wmv ts'     #Extensions of video files to convert

temp_path = "/tmp"                                          #Directory for encode prior to moving back
mkvextract_exe = "/usr/bin/mkvextract"                               #Path to mkvextract executable
atomicparsely_exe = "/usr/bin/AtomicParsley"                         #Path to AtomicParsley executable
mkvpropedit_exe = "/usr/bin/mkvpropedit"                             #Path to mkvpropedit executable

strip_title = True                                          #Strip 'Title' field from metadata
video_codec = 'libx264'                                     #Video codec to use
video_type = 'h264'                                         #Name of video codec to check for remux
audio_codec = 'aac'                                         #Audio codec to use
audio_type = 'aac'                                          #Name of audio codec to check for remux
crf = "18"                                                  #Default crf
vbr = ""                                                    #Default audio vbr rate (CBR is used if this is blank)
extract_subtitle = True                                     #Extract subtitles?
subtitle_languages = "en eng english"                       #Codes for languages to extract
threads = 0                                                 #Number of threads to use in ffmpeg, 0 defaults to all
additional_ffmpeg = '-preset slow -movflags +faststart'     #Default Additional flags for ffmpeg, preset sets speed and compression, movflags to make file web optimized
deinterlace_ffmpeg = 'yadif'                                #Deinterlacing options

## END OPTIONS - DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING ##

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
         return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
         return False
    else:
         raise argparse.ArgumentTypeError('Boolean value expected.')
                                        
class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

parser = argparse.ArgumentParser(description='Simple mp4 converter')
parser.add_argument('-i','--input', help='Input file name/path', required=True)
parser.add_argument('-m','--mode',help='Processing mode', choices=['quality', 'speed'], required=True)
parser.add_argument('-f','--force', type=str2bool, nargs='?', const=True, default=False, help="Force reprocess")
args = parser.parse_args()

if args.mode == 'speed':
    crf = "22"
    additional_ffmpeg = '-preset superfast -movflags +faststart'

if outmode == 'mp4':
    outformat = 'mp4'
elif outmode == 'mkv':
    outformat = 'matroska'

print("Validating FFMpeg configuration...\n")
        
format_resp = ffmpy.FFprobe(
    inputs={'': None},
    global_options=[
        '-v', 'quiet',
        '-formats', '2']
).run(stdout=subprocess.PIPE,stderr=subprocess.PIPE)

if ('E mp4' in format_resp[0]) and ('E matroska' in format_resp[0]):
    print("You have the suitable formats")
else:
    print("You do not have both the mkv and mp4 formats...Exiting!")
    exit(1)

codec_resp = ffmpy.FFprobe(
    inputs={'': None},
    global_options=[
        '-v', 'quiet',
        '-codecs', '2']
).run(stdout=subprocess.PIPE,stderr=subprocess.PIPE)

if video_codec in codec_resp[0]:
    print("Check " + video_codec + " Video Encoder ... OK")
else:
    print("Check " + video_codec + " Video Encoder ... NOK")
    exit(1)

if audio_codec in codec_resp[0]:
    print("Check " + audio_codec + " Audio Encoder ... OK")
else:
    print("Check " + audio_codec + " Audio Encoder ... NOK")
    exit(1)

print("Your FFMpeg is OK!\n\nEntering File Processing...\n")

subtitle_languages = subtitle_languages.lower()

def process_file(path, file):
    extension = os.path.splitext(file)[1].replace(".", "").lower()
    filename = os.path.splitext(file)[0]

    if extension in accept_ext and extension != "":
        print(file + " is an acceptable extension. Checking file...")
    else:
        print(file + " is not an acceptable extension. Skipping...")
        return

    print('Processing Started: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
    try:
        tup_resp = ffmpy.FFprobe(
            inputs={os.path.join(path, file): None},
            global_options=[
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams']
        ).run(stdout=subprocess.PIPE)
    
        metaData = json.loads(tup_resp[0].decode('utf-8'))
    except Exception as file_info_ex:
        print("File " + file + " is unable to be converted. Adding .PROBE_FAIL to file")
        shutil.move(os.path.join(path, filename + "." + extension), os.path.join(path, filename + "." + extension + ".PROBE_FAIL"))
        return

    vcodec = ''
    acodec = ''
    encode_crf = []

    for vs in metaData["streams"]:
        if "codec_type" in vs and vs["codec_type"] == "video":
            if vs["codec_name"] == video_type:
                vcodec = 'copy'
                print("Video in stream " + str(vs["index"]) + " is " + video_type + ", no conversion needed...")
            elif vs["codec_name"] != 'mjpeg':
                vcodec = video_codec
                if crf:
                    encode_crf = ["-crf", "" + crf]
                print("Video in stream " + str(vs["index"]) + " is currently " + color.BOLD + color.YELLOW + vs["codec_name"] + color.END + ". Converting to " + color.BOLD + color.YELLOW + video_type + color.END + "...")

    encode_dif = []
    for vs in metaData["streams"]:
        if "codec_type" in vs and vs["codec_type"] == "video" and vcodec != 'copy':
            if "field_order" in vs and vs["field_order"].find("progressive") == -1:
                if deinterlace_ffmpeg:
                    encode_dif = ["-vf", "" + deinterlace_ffmpeg]
                print("Video in stream " + str(vs["index"]) + " is interlaced, deinterlacing...")
            else:
                print("Video in stream " + str(vs["index"]) + " is not interlaced, no deinterlacing needed...")

    encode_vbr = []
    for vs in metaData["streams"]:
        if "codec_type" in vs and vs["codec_type"] == "audio":
            if vs["codec_name"] == audio_type:
                acodec = 'copy'
                print("Audio in stream " + str(vs["index"]) + " is " + audio_type + ", no conversion needed...")
            else:
                acodec = audio_codec
                if vbr:
                    encode_vbr = ["-vbr", "" + vbr]
                print("Audio in stream " + str(vs["index"]) + " is currently " + color.BOLD + color.GREEN + vs["codec_name"] + color.END + ". Converting to " + color.BOLD + color.GREEN + audio_type + color.END +"...")

    if extension == outmode and vcodec == 'copy' and acodec == 'copy' and args.force == False:
        print(file + " is already encoded properly. (" + outmode + " file and " + video_type + " / " + audio_type + ")\nNo conversion needed. Skipping...\n\n")
        if strip_title:
            print("Removing title metadata...")
            striptitle_out = subprocess.check_output([atomicparsely_exe, os.path.join(path, file),'--title','','--comment','','--overWrite'],stderr=subprocess.STDOUT)
            print(striptitle_out)
        return

    print("Using video codec: " + vcodec + " audio codec: " + acodec + " and Container format " + outformat + " for " + file)
    print("Duration of current video: " + "{:0>8}".format(datetime.timedelta(seconds=float(metaData["format"]["duration"]))))
    
    filename = filename.replace("XVID", video_type)
    filename = filename.replace("xvid", video_type)
    enc_resp = ""
    
    try:
        ffargs = ['-y', '-f', outformat, '-acodec', acodec]
        if encode_dif:
            ffargs.extend(encode_dif)
        ffargs.extend(['-vcodec', vcodec])
        if encode_crf:
            ffargs.extend(encode_crf)
        if additional_ffmpeg:
            ffargs.extend(additional_ffmpeg.split(" "))
        if threads:
            ffargs.extend(['-threads', str(threads)])

        if temp_path:
            enc_resp = ffmpy.FFmpeg(
                global_options='-v quiet -stats',
                inputs={os.path.join(path, file): None},
                outputs={os.path.join(temp_path, filename + '.temp'): ffargs}
            ).run(stdout=subprocess.PIPE)
            shutil.move(os.path.join(temp_path, filename + '.temp'), os.path.join(path, filename + '.' + outmode))
        else:
            enc_resp = ffmpy.FFmpeg(
                global_options='-v quiet -stats',
                inputs={os.path.join(path, file): None},
                outputs={os.path.join(path, filename + '.temp'): ffargs}
            ).run(stdout=subprocess.PIPE)
            shutil.move(os.path.join(path, filename + '.temp'), os.path.join(path, filename + '.' + outmode))

        if strip_title:
            print("Removing title metadata...")
            striptitle_out = subprocess.check_output([atomicparsely_exe, os.path.join(path, filename + '.' + outmode),'--title','','--comment','','--overWrite'],stderr=subprocess.STDOUT)
            print(striptitle_out)

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

    if extract_subtitle:
        sub_resp = ""
        print("\nExtracting Subtitles...\n")
        for m in metaData["streams"]:
            if 'subtitle' in m["codec_type"]:
                if 'tags' in m:
                    if 'language' in m["tags"]:
                        if m["tags"]["language"] in subtitle_languages.split(" "):
                            try:
                                if 'subrip' in m["codec_name"]:
                                    sub_format = 'copy'
                                    sub_ext = '.srt'
                                elif mkvextract_exe and 'hdmv_pgs' in m["codec_name"]:
                                    mkvextract_out = subprocess.check_output([mkvextract_exe, 'tracks', os.path.join(path, file),
                                                             str(m["index"]) + ':' + os.path.join(path, filename + '.'
                                                             + m["tags"]["language"] + '.' + str(m["index"]) + '.sup')],stderr=subprocess.STDOUT)
                                    continue
                                else:
                                    sub_format = 'srt'
                                    sub_ext = '.srt'
                                enc_resp = ffmpy.FFmpeg(
                                    global_options='-v quiet -stats',
                                    inputs={os.path.join(path, file): None},
                                    outputs={os.path.join(path, filename + '.' + m["tags"]["language"] + '.' + str(m["index"]) + sub_ext): ['-y', '-map', '0:' + str(m["index"]), '-c:s:0', sub_format]}
                                ).run(stdout=subprocess.PIPE)
                                print("")
                            except Exception as e:
                                print("Error: %s" % e)
                                print("Deleting subtitle.")
                                if os.path.isfile(os.path.join(path, filename + '.' + m["tags"]["language"] + '.' + str(m["index"]) + sub_ext)):
                                    os.remove(re.escape(os.path.join(path, filename + '.' + m["tags"]["language"] + '.' + str(m["index"]) + sub_ext)))

    if remover and filename + '.' + outmode != file:
        print("Deleting original file: " + file)
        os.remove(os.path.join(path, file))
    
    print('Processing Started: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))


def process_directory(path):
    if os.path.isfile(os.path.join(path, ".noconvert")):
        return
    for file in sorted(os.listdir(path)):
        filepath = os.path.join(path, file)
        if os.path.isdir(filepath):
            process_directory(filepath)
        elif os.path.isfile(filepath):
            process_file(path, file)


if os.path.isdir(args.input):
    process_directory(args.input)
elif os.path.isfile(args.input):
    process_file(os.path.dirname(args.input), os.path.basename(args.input))


