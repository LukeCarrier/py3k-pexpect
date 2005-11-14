#!/usr/bin/env python
"""Rippy!

This script converts video to different formats.
It is useful for coverting DVDs to DivX videos.

Run the script with no arguments to start with interactive prompts.
    rippy.py
Run the script with the filename of a options config to start automatic mode.
    rippy.conf

After rippy is finished it saves the current configuation in
a file called 'rippy.conf' in the local directoy. This can be used to
rerun the rippy process using the exact same settings.
Just pass the filename of the conf file as an argument to rippy
and it will read that file instead of asking your for options interactively.
    rippy.py rippy.conf
So if you run rippy with 'dry_run=1' then you can run the process again
later using the 'rippy.conf' file. Don't forget to edit 'rippy.conf'
to set 'dry_run=0'!

Note that mplayer has poor handling of mixing MP3 files to AVI format.
I have had better luck with Metroshka (MKV) format containers.
Currently only MKV format is supported. Hopefully I can fix AVI later.

Remember:
    a 180MB CDR (21 minutes) holds 193536000 bytes.
    a 550MB CDR (63 minutes) holds 580608000 bytes.
    a 650MB CDR (74 minutes) holds 681984000 bytes.
    a 700MB CDR (80 minutes) holds 737280000 bytes.

2005 Noah Spurrier [noah@noah.org]
"""
import sys, os, re, math, stat, getopt, pickle, traceback, types
from pexpect import *

def convert (options):
    """This is the heart of it all -- this performs an end-to-end conversion of
    a video from one format to another. It requires a dictionary of options.
    The conversion process will also add some keys to the dictionary
    such as length of the video and crop area. The dictionary is returned.
    """
    print "# Extract audio to %s" % (options['audio_raw_filename'])
    apply_smart (extract_audio, options)

    if options['video_length']=='calc':
        options['video_length'] = apply_smart (get_length, options)
        print "# Length of raw audio file : %d seconds (%0.2f minutes)" % (options['video_length'], float(options['video_length'])/60.0)

    print "# Compress raw audio"
    apply_smart (compress_audio, options)

    if options['video_bitrate']=='calc':
        options['video_bitrate'] = apply_smart (calc_video_bitrate, options) 
    print "# video bitrate : ", options['video_bitrate']

    if options['video_crop_area']=='detect':
        options['video_crop_area'] = apply_smart (crop_detect, options)
    print "# crop area : ", options['video_crop_area']

    print "# Transcode video"
    apply_smart (compress_video, options)

    print "# Mix video and audio together to final video container"
    apply_smart (mux, options)

    print "# Delete temporary files"
    if options['delete_tmp_files_flag']:
        apply_smart (delete_tmp_files, options)

    o = ["# options used to create video\n"]
    for k,v in options.iteritems():
        o.append (" %30s : %s\n" % (k, v))
    conf_string = ''.join(o)
    print conf_string
    fout = open("rippy.conf","wb").write(conf_string)
    
    return options

def exit_with_usage(exit_code=1):
    print globals()['__doc__']
    os._exit(exit_code)

def input_option (message, default_value="", help=None):
    if default_value != '':
        message = "%s [%s] " % (message, default_value)
    while 1:
        user_input = raw_input (message)
        if user_input=='?':
            print help
        elif user_input=='':
            return default_value
        else:
            break
    return user_input

def progress_callback (d=None):
    print ".",

def apply_smart (func, args):
    """This is similar to func(**args), but this won't complain about 
    extra keys in 'args'. This ignores keys in 'args' that are 
    not required by 'func'. This passes None to arguments that are
    not defined in 'args'. That's fine for arguments with a default valeue, but
    that's a bug for required arguments. I should probably raise a TypeError.
    """
    if hasattr(func,'im_func'): # Handle case when func is a class method.
        func = func.im_func
    argcount = func.func_code.co_argcount
    required_args = dict([(k,args.get(k)) for k in func.func_code.co_varnames[:argcount]])
    return func(**required_args)

def count_unique (items):
    """This takes a list and returns a sorted list of tuples with a count of each unique item in the list.
    Example 1:
        count_unique(['a','b','c','a','c','c','a','c','c'])
    returns:
        [(5,'c'), (3,'a'), (1,'b')]
    Example 2 -- get the most frequent item in a list:
        count_unique(['a','b','c','a','c','c','a','c','c'])[0][1]
    returns:
        'c'
    """
    stats = {}
    for i in items:
        if i in stats:
            stats[i] = stats[i] + 1
        else:
            stats[i] = 1
    stats = [(v, k) for k, v in stats.items()]
    stats.sort()
    stats.reverse()
    return stats

def get_aid_list (video_source_filename):
    """This returns a list of audio ids in the source video file.
    """
    result = run ("mplayer %s -vo null -ao null -frames 0 -identify" % video_source_filename)
    idl = re.findall("ID_AUDIO_ID=([0-9]*)", result)
    idl.sort()
    return idl
    
def extract_audio (video_source_filename, audio_id=128, verbose_flag=0, dry_run_flag=0):
    """This extracts the given audio_id track as uncompressed PCM from the given source video.
        Note that mplayer always saves this to audiodump.wav.
        At this time there is no way to set the output audio name.
    """
    cmd = "mplayer %(video_source_filename)s -vo null -aid %(audio_id)s -ao pcm -noframedrop -vc dummy" % locals()
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print

def get_length (audio_raw_filename):
    """This attempts to get the length of the media file (length is time in seconds).
    Not to be confused with size (in bytes) of the file data.
    This is best used on a PCM AUDIO file because mplayer cannot get an accurate
    time for many compressed video and audio formats -- notably MPEG4 and MP3.
    Weird...
    This returns -1 if it cannot get the length of the given file.
    """
    result = run ("mplayer %s -vo null -ao null -frames 0 -identify" % audio_raw_filename)
    idl = re.findall("ID_LENGTH=([0-9]*)", result)
    idl.sort()
    if len(idl) != 1:
        return -1
    return int(idl[0])

def calc_video_bitrate (video_final_target_size, audio_compressed_filename, video_length, extra_space=0):
    """This gives an estimate of the video bitrate
    necessary to fit the final target size.
    This will take into account room to fit the audio_compressed_filename
    and extra space if given.
    video_final_target_size is in MB,
    audio_compressed_filename is a string, 
    video_length is in seconds,
    extra_space is in bytes.
    a 180MB CDR (21 minutes) holds 193536000 bytes.
    a 550MB CDR (63 minutes) holds 580608000 bytes.
    a 650MB CDR (74 minutes) holds 681984000 bytes.
    a 700MB CDR (80 minutes) holds 737280000 bytes.
    """
    if extra_space is None: extra_space = 0
    audio_size = os.stat(audio_compressed_filename)[stat.ST_SIZE]
#a 700MB CDR holds 737280000 bytes.
    video_final_target_size = 737280000 - audio_size - extra_space
    return calc_video_kbitrate (video_final_target_size, video_length)

def calc_video_kbitrate (target_size, length_secs):
    """Given a target byte size free for video data, this returns the bitrate in kBit/S.
    For mencoder vbitrate 1 kBit = 1000 Bits -- not 1024 bits.
        target_size = bitrate * 1000 * length_secs / 8
        target_size = bitrate * 125 * length_secs
        bitrate     = target_size/(125*length_secs)
    """
    return int(1.2 * target_size / (125.0 * length_secs))

def crop_detect (video_source_filename, video_length):
    """This attempts to figure out the best crop for the given video file.
    Basically it runs crop detect for 5 seconds on three different places in the video.
    It picks the crop area that was most often detected.
    """
    skip = int(video_length/9)
    sample_length = 5
    cmd1 = "mencoder %s -quiet -ss %d -endpos %d -o /dev/null -nosound -ovc lavc -vf cropdetect" % (video_source_filename,   skip, sample_length)
    cmd2 = "mencoder %s -quiet -ss %d -endpos %d -o /dev/null -nosound -ovc lavc -vf cropdetect" % (video_source_filename, 2*skip, sample_length)
    cmd3 = "mencoder %s -quiet -ss %d -endpos %d -o /dev/null -nosound -ovc lavc -vf cropdetect" % (video_source_filename, 3*skip, sample_length)
    result1 = run(cmd1)
    result2 = run(cmd2)
    result3 = run(cmd3)
    idl = re.findall("-vf crop=([0-9]+:[0-9]+:[0-9]+:[0-9]+)", result1)
    idl = idl + re.findall("-vf crop=([0-9]+:[0-9]+:[0-9]+:[0-9]+)", result2)
    idl = idl + re.findall("-vf crop=([0-9]+:[0-9]+:[0-9]+:[0-9]+)", result3)
    items_count = count_unique(idl)
    return items_count[0][1]

def compress_video (video_source_filename, video_transcoded_filename, video_bitrate=1000, video_codec='mpeg4', video_gray_flag=0, video_key_interval=0, video_crop_area=None, video_scale=None, video_encode_passes=2, video_deinterlace_flag=0, verbose_flag=0, dry_run_flag=0):
    """This compresses the given source video filename to the transcoded filename.
        This does a two-pass compression (I'm assuming mpeg4, I should probably make this smarter for other formats).
    """
    # build filter expression
    filter = ''
    if video_crop_area and video_crop_area.lower()!='none':
        filter = filter + "crop=%s" % video_crop_area
    if video_deinterlace_flag:
        if filter != '':
            filter = filter + ','
        filter = filter + 'pp=md'
    if video_scale and video_scale.lower()!='none':
        if filter != '':
            filter = filter + ','
        filter = filter + "scale=%s" % video_scale
    if filter != '':
        filter = '-vf ' + filter

    # build lavcopts expression
    if video_encode_passes=='2':
        lavcopts1 = '-lavcopts vcodec=%s:vbitrate=%d:mbd=2:vpass=1' % (video_codec,video_bitrate)
        lavcopts2 = '-lavcopts vcodec=%s:vbitrate=%d:mbd=2:vpass=2' % (video_codec,video_bitrate)
    else:
        lavcopts1 = '-lavcopts vcodec=%s:vbitrate=%d:mbd=2:vpass=1' % (video_codec,video_bitrate)
        lavcopts2 = ''
    if video_key_interval:
        lavcopts1 = lavcopts1 + ":keyint=%d" % int(video_key_interval)
        lavcopts2 = lavcopts2 + ":keyint=%d" % int(video_key_interval)
    if video_gray_flag:
        lavcopts1 = lavcopts1 + ":gray"
        lavcopts2 = lavcopts2 + ":gray"
    
    cmd = "mencoder %s -o %s -oac copy -ovc lavc -nosound %s %s" % (video_source_filename, video_transcoded_filename, lavcopts1, filter)
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print
    # If not doing two passes then return early.
    if video_encode_passes!='2':
        return
    cmd = "mencoder %s -o %s -oac copy -ovc lavc -nosound %s %s" % (video_source_filename, video_transcoded_filename, lavcopts2, filter)
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print

def compress_audio (audio_raw_filename, audio_compressed_filename, audio_lowpass_filter=None, audio_sample_rate=None, audio_bitrate=None, verbose_flag=0, dry_run_flag=0):
    """This compresses the raw audio file to the compressed audio filename.
    """
    cmd = "lame -h --athaa-sensitivity 1 --cwlimit 11"
    if audio_lowpass_filter:
        cmd = cmd + " --lowpass " + audio_lowpass_filter
    if audio_bitrate:
        cmd = cmd + " --abr " + audio_bitrate
    if audio_sample_rate:
        cmd = cmd + " --resample " + audio_sample_rate
    cmd = cmd + " " + audio_raw_filename + " " + audio_compressed_filename
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print

def mux (video_final_filename, video_transcoded_filename, audio_compressed_filename, video_container_format, verbose_flag=0, dry_run_flag=0):
    if video_container_format.lower() == "mkv":
        mux_mkv (video_final_filename, video_transcoded_filename, audio_compressed_filename, verbose_flag, dry_run_flag)
    if video_container_format.lower() == "avi":
        mux_avi (video_final_filename, video_transcoded_filename, audio_compressed_filename, verbose_flag, dry_run_flag)

def mux_mkv (video_final_filename, video_transcoded_filename, audio_compressed_filename, verbose_flag=0, dry_run_flag=0):
    cmd = "mkvmerge -o %s --noaudio %s %s" % (video_final_filename, video_transcoded_filename, audio_compressed_filename)
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print

def mux_avi (video_final_filename, video_transcoded_filename, audio_compressed_filename, verbose_flag=0, dry_run_flag=0):
    print "NOT IMPLEMENTED YET"
    return
    cmd = "mkvmerge -o %s --noaudio %s %s" % (video_final_filename, video_transcoded_filename, audio_compressed_filename)
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print

def delete_tmp_files (video_transcoded_filename, audio_raw_filename, audio_compressed_filename, verbose_flag=0, dry_run_flag=0):
    file_list = ' '.join(['divx2pass.log', video_transcoded_filename, audio_raw_filename, audio_compressed_filename])
    cmd = "rm -f " + file_list
    if verbose_flag: print cmd
    if not dry_run_flag:
        run(cmd, timeout=5, events={TIMEOUT:progress_callback})
        print
    
##############################################################################

# This defines the prompts and defaults used for interactive mode.
prompts = {
'video_source_filename':("dvd://1", 'Video source filename?', """This is the filename of the video that you want to convert from.
It can be any file that mencoder supports.
You can also choose a DVD device using the dvd://1 syntax.
Title 1 is usually the main title on a DVD."""),
'video_transcoded_filename':("~video.avi", 'Video transcoded filename?', """This is the temporary file where the video will be stored in the new format.
This is before the audio track is mixed into the final video container."""),
'video_final_filename':("video_final", "Video final filename?", """This is the name of the final video."""),
'audio_raw_filename':("audiodump.wav", "Audio raw filename?", """This is the audio raw PCM filename. This is prior to compression.
Note that mplayer automatically names this audiodump.wav, so
normally you should not change this."""),
'audio_compressed_filename':("audiodump.mp3","Audio compressed filename?", """This is the name of the compressed audio that will be mixed
into the final video. Normally you don't need to change this."""),
'video_length':("calc","Video length in seconds?","""This sets the length of the video in seconds. Set to 'calc' to calculate the length from the
raw audio stream. That's a hack because mplayer cannot get the length of
the video from the source video file. Normally you don't need to change this."""),
'video_scale':("none","Video scale?","""This scales the video to the given output size. The default is to do no scaling.
You may type in a resolution such as 320x240 or you may use presets.
  qntsc:   352x240 (NTSC quarter screen)
  qpal:    352x288 (PAL quarter screen)
  ntsc:    720x480 (standard NTSC)
  pal:     720x576 (standard PAL)
  sntsc:   640x480 (square pixel NTSC)
  spal:    768x576 (square pixel PAL)"""),
'video_codec':("mpeg4","Video codec?","""This is the video compression to use. This is passed directly to mencoded, so
any format that it recognizes will work. For DivX use 'mpeg4'.
Some common codecs include:
mjpeg, h263, h263p, h264, mpeg4, msmpeg4, wmv1, wmv2, mpeg1video, mpeg2video, huffyuv, ffv1.
See mencoder manual for details."""),
'video_encode_passes':("2","Encode passes?","""This sets how many passes to use to encode the video. You can choose 1 or 2.
Using two pases takes twice as long as one pass, but produces a better
quality video. I found that the effect is not that noticable."""),
'video_key_interval':("12","Video key-frame interval?","""This sets how often a key-frame is inserted into the stream.
Normally you don't need to change this."""),
'verbose_flag':("Y","Verbose output?","""This sets verbose output. If true then all commands and arguments are printed
before they are run. This is useful to see exactly how commands are run."""),
'dry_run_flag':("N","Dry run?","""This sets 'dry run' mode. If true then commands are not run. This is useful
if you want to see what would happen by running the script."""),
'video_final_target_size':("700","Video final target size in MB?","""This sets the final video target size that you want to end up with.
Due to the unpredictable nature of compression the final video size may not
exactly match. Most CDRs hold 650MB or 700MB. Mini-CDRs hold 180MB."""),
'video_bitrate':("calc","Video bitrate","""This sets the video bitrate. Set to 'calc' to automatically estimate
the bitrate necessary to fill the video final target size."""),
'video_crop_area':("detect","Crop area?","""This sets the crop area to remove black bars from the top and sides of the video.
This helps save space. Set to 'detect' to automatically detect the crop area.
Set to 'none' to not crop the video. Normally you don't need to change this."""),
'video_container_format':('mkv',"Final video format (avi or mkv)?","""This sets the final video container format. Metroshka is 'mkv' format.
Currently 'avi' format doesn't work due to a bug in mencoder."""),
'video_deinterlace_flag':("N","Is the video interlaced?","""This sets the deinterlace flag. If set then mencoder will be instructed
to filter out interlace artifacts."""),
'video_gray_flag':("N","Is the video black and white (gray)?","""This improves output for black and white video."""),
'audio_id':("128","Audio ID stream?","""This selects the audio stream to extract from the source video.
If your source is a VOB file (DVD) then stream IDs start at 128.
Normally, 128 is the main audio track for a DVD.
Tracks with higher numbers may be other language dubs or audio commentary."""),
'audio_sample_rate':("32","Audio sample rate (kHz) 48, 44.1, 32, 24, 12","""This sets the rate at which the compressed audio will be resampled.
DVD audio is 48 kHz whereas music CDs use 44.1 kHz. The higher the sample rate
the more space the audio track will take. That will leave less space for video.
32 kHz is a good trade-off if you are trying to fit a video onto a CD."""),
'audio_bitrate':("96","Audio bitrate (kbit/s) 192, 128, 96?","""This sets the bitrate for MP3 audio compression.
The higher the bitrate the more space the audio track will take.
That will leave less space for video. Most people find music to be acceptable
at 128 kBitS. 96 kBitS is a good trade-off if you are trying to fit a video onto a CD."""),
'audio_lowpass_filter':("16","Audio lowpass filter (kHz)?","""This sets the low-pass filter for the audio.
Normally this should be half of the audio sample rate.
This improves audio compression and quality.
Normally you don't need to change this."""),
'delete_tmp_files_flag':("N","Delete temporary files when finished?","""If Y then video_transcoded_filename, audio_raw_filename, audio_compressed_filename,
and 'divx2pass.log' will be deleted at the end.""")
}
prompts_key_order = ('video_source_filename','video_transcoded_filename','video_final_filename','audio_raw_filename',
'audio_compressed_filename','video_length','video_scale','video_codec','video_encode_passes','video_key_interval','verbose_flag','dry_run_flag','video_final_target_size','video_bitrate','video_crop_area',
'video_container_format','video_deinterlace_flag','video_gray_flag','audio_id','audio_sample_rate','audio_bitrate',
'audio_lowpass_filter','delete_tmp_files_flag')

def interactive_convert ():
    global prompts, prompts_key_order

    print globals()['__doc__']
    print
    print """Enter '?' at any question to get extra help."""
    print
    options = {}
    for k in prompts_key_order:
        if k == 'audio_id':
            aid_list = get_aid_list (options['video_source_filename'])
            if len(aid_list) > 1:
                print "This video has more than one audio stream. The following stream audio IDs were found:"
                for aid in aid_list:
                    print "    " + aid
            else:
                print "Unable to get the list of audio streams from the vide. Setting default to 128."
                aid_list=["128"]
            options[k] = input_option (prompts[k][1], aid_list[0], prompts[k][2])
        elif k == 'audio_lowpass_filter':
            lowpass_default =  "%.1f" % (math.floor(float(options['audio_sample_rate']) / 2.0))
            options[k] = input_option (prompts[k][1], lowpass_default, prompts[k][2])
        else:
            options[k] = input_option (prompts[k][1], prompts[k][0], prompts[k][2])

    options['video_final_filename'] = options['video_final_filename'] + "." + options['video_container_format']

    print "=========================================================================="
    print "Ready to Rippy!"
    print
    print "The following options will be used:"
    for k,v in options.iteritems():
        print "%27s : %s" % (k, v)

    print
    c = input_option("Continue?", "Y")
    if c != 'Y':
        print "Exiting..."
        os._exit(1)
    return options

def clean_options (d):
    """This validates and cleans up the options dictionary.
    After reading options interactively or from a conf file
    we need to make sure that the values are converted or make sense.
    """
    for k in d:
        d[k] = d[k].strip()
        if '_flag' in k:
            if type(d[k]) is types.StringType:
                if d[k].strip().lower()[0] in 'yt1': #Yes, True, 1
                    d[k] = 1
                else:
                    d[k] = 0
    d['video_bitrate'] = int(d['video_bitrate'])
    d['video_scale'] = d['video_scale'].lower()
    if d['video_scale'][0]=='n':
        d['video_scale']='none'
    else:
        al = re.findall("([0-9]+).*?([0-9]+)", d['video_scale'])
        d['video_scale']=al[0][0]+':'+al[0][1]
    d['video_crop_area'] = d['video_crop_area'].lower()
    if d['video_crop_area'][0]=='n':
        d['video_crop_area']='none'
    d['video_length'] = d['video_length'].lower()
    if d['video_length'][0]=='c':
        d['video_length']='calc'
    return d

def main ():
    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'h?', ['help','h','?'])
    except Exception, e:
        print str(e)
        exit_with_usage()
    command_line_options = dict(optlist)
    # There are a million ways to cry for help. These are but a few of them.
    if [elem for elem in command_line_options if elem in ['-h','--h','-?','--?','--help']]:
        exit_with_usage(0)

    if len(args) > 0:
        options = dict(re.findall('([^: \t\n]*)\s*:\s*(".*"|[^ \t\n]*)', file(args[0]).read()))
        options = clean_options(options)
        convert (options)
    else:
        options = interactive_convert ()
        options = clean_options(options)
        convert (options)
    print "Done!"
    
if __name__ == "__main__":
    try:
        main ()
    except Exception, e:
        print "ERROR -- Unexpected exception in script."
        print str(e)
        traceback.print_exc()
        exit_with_usage(2)
        os._exit(3)

