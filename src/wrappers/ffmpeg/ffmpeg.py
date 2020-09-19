#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import subprocess

from context import Context
from dandere2xlib.utils.dandere2x_utils import get_a_valid_input_resolution
from dandere2xlib.utils.yaml_utils import get_options_from_section


def trim_video(context: Context, output_file: str):
    """
    Create a trimmed video using -ss and -to commands from FFMPEG. The trimmed video will be named 'output_file'
    """
    # load context

    input_file = context.input_file

    trim_video_command = [context.ffmpeg_dir,
                          "-hwaccel", context.hwaccel,
                          "-i", input_file]

    trim_video_time = get_options_from_section(context.config_yaml["ffmpeg"]["trim_video"]["time"])

    for element in trim_video_time:
        trim_video_command.append(element)

    trim_video_options = \
        get_options_from_section(context.config_yaml["ffmpeg"]["trim_video"]["output_options"], ffmpeg_command=True)

    for element in trim_video_options:
        trim_video_command.append(element)

    trim_video_command.append(output_file)

    console_output = open(context.console_output_dir + "ffmpeg_trim_video_command.txt", "w")
    console_output.write(str(trim_video_command))
    subprocess.call(trim_video_command, shell=False, stderr=console_output, stdout=console_output)


def re_encode_video(context: Context, input_file: str, output_file: str, throw_exception=False):
    """
    Using the "re_encode_video" commands in the yaml to re-encode the input video in an opencv2 friendly
    manner. Without this step, certain containers might not be compatible with opencv2, and will cause
    a plethora of errors.

    throw_exception: Will throw a detailed exception and print statement if conversion failed.
    """
    logger = logging.getLogger(__name__)
    frame_rate = context.frame_rate

    extract_frames_command = [context.ffmpeg_dir,
                              "-hwaccel", context.hwaccel,
                              "-i", input_file]

    extract_frames_options = \
        get_options_from_section(context.config_yaml["ffmpeg"]['re_encode_video']['output_options'],
                                 ffmpeg_command=True)

    for element in extract_frames_options:
        extract_frames_command.append(element)

    extract_frames_command.append("-r")
    extract_frames_command.append(str(frame_rate))
    extract_frames_command.extend([output_file])

    log_file = context.console_output_dir + "ffmpeg_convert_video.txt"
    console_output = open(log_file, "w")
    console_output.write(str(extract_frames_command))
    subprocess.call(extract_frames_command, shell=False, stderr=console_output, stdout=console_output)

    if throw_exception:
        with open(context.console_output_dir + "ffmpeg_convert_video.txt") as f:
            if 'Conversion failed!' in f.read():
                print("Failed to convert: " + input_file + " -> " + output_file + ".")
                print("Check the output file for more information: " + log_file)

                raise TypeError


def check_if_file_is_video(ffprobe_dir: str, input_video: str):
    execute = [
        ffprobe_dir,
        "-i", input_video,
        "-v", "quiet"
    ]

    return_bytes = subprocess.run(execute, check=True, stdout=subprocess.PIPE).stdout

    if "Invalid data found when processing input" in return_bytes.decode("utf-8"):
        return False

    return True


def extract_frames(context: Context, input_file: str):
    """
    Extract frames from a video using ffmpeg.
    """
    input_frames_dir = context.input_frames_dir
    extension_type = context.extension_type
    output_file = input_frames_dir + "frame%01d" + extension_type
    logger = logging.getLogger(__name__)
    frame_rate = context.frame_rate

    extract_frames_command = [context.ffmpeg_dir,
                              "-hwaccel", context.hwaccel,
                              "-i", input_file]

    extract_frames_options = \
        get_options_from_section(context.config_yaml["ffmpeg"]["video_to_frames"]['output_options'],
                                 ffmpeg_command=True)

    for element in extract_frames_options:
        extract_frames_command.append(element)

    extract_frames_command.append("-r")
    extract_frames_command.append(str(frame_rate))

    extract_frames_command.extend([output_file])

    console_output = open(context.console_output_dir + "ffmpeg_extract_frames_console.txt", "w")
    console_output.write(str(extract_frames_command))
    subprocess.call(extract_frames_command, shell=False, stderr=console_output, stdout=console_output)


def create_video_from_extract_frames(context: Context, output_file: str):
    """
    Create a new video by applying the filters that d2x needs to work into it's own seperate video.
    """
    input_file = context.input_file
    logger = logging.getLogger(__name__)

    command = [context.ffmpeg_dir,
               "-hwaccel", context.hwaccel,
               "-i", input_file]

    extract_frames_options = \
        get_options_from_section(context.config_yaml["ffmpeg"]["video_to_frames"]['output_options'],
                                 ffmpeg_command=True)

    for element in extract_frames_options:
        command.append(element)

    command.extend([output_file])

    logger.info("Applying filter to video...")

    console_output = open(context.console_output_dir + "ffmpeg_create_video_from_extract_frame_filters.txt", "w")
    console_output.write(str(command))
    subprocess.call(command, shell=False, stderr=console_output, stdout=console_output)


def append_video_resize_filter(context: Context):
    """
    For ffmpeg, there's a video filter to resize a video to a given resolution.
    For dandere2x, we need a very specific set of video resolutions to work with.  This method applies that filter
    to the video in order for it to work correctly.
    """
    log = logging.getLogger()
    width, height = get_a_valid_input_resolution(context.width, context.height, context.block_size)

    log.info("Dandere2x is resizing the video in order to make the resolution compatible with your settings... ")
    log.info("New width -> %s " % str(width))
    log.info("New height -> %s " % str(height))

    context.width = width
    context.height = height

    context.config_yaml['ffmpeg']['re_encode_video']['output_options']['-vf'] \
        .append("scale=" + str(context.width) + ":" + str(context.height))


def concat_encoded_vids(context: Context, output_file: str):
    """
    Concatonate a video using 2) in this stackoverflow post.
    https://stackoverflow.com/questions/7333232/how-to-concatenate-two-mp4-files-using-ffmpeg

    The 'list.txt' should already exist, as it's produced in realtime_encoding.py
    """

    encoded_dir = context.encoded_dir

    text_file = encoded_dir + "list.txt"
    concat_videos_command = [context.ffmpeg_dir,
                             "-f", "concat",
                             "-safe", "0",
                             "-hwaccel", context.hwaccel,
                             "-i", text_file]

    concat_videos_option = \
        get_options_from_section(context.config_yaml["ffmpeg"]["concat_videos"]['output_options'], ffmpeg_command=True)

    for element in concat_videos_option:
        concat_videos_command.append(element)

    concat_videos_command.extend([output_file])

    console_output = open(context.console_output_dir + "ffmpeg_concat_videos_command.txt", "w")
    console_output.write((str(concat_videos_command)))
    subprocess.call(concat_videos_command, shell=False, stderr=console_output, stdout=console_output)


def migrate_tracks(context: Context, no_audio: str, file_dir: str, output_file: str, copy_if_failed=False):
    """
    Add the audio tracks from the original video to the output video.
    """

    migrate_tracks_command = [context.ffmpeg_dir,
                              "-i", no_audio,
                              "-i", file_dir,
                              "-map", "0:v?",
                              "-map", "1:a?",
                              "-map", "1:s?",
                              "-map", "1:d?",
                              "-map", "1:t?"
                              ]

    migrate_tracks_options = \
        get_options_from_section(context.config_yaml["ffmpeg"]["migrating_tracks"]['output_options'],
                                 ffmpeg_command=True)

    for element in migrate_tracks_options:
        migrate_tracks_command.append(element)

    migrate_tracks_command.extend([str(output_file)])

    console_output = open(context.console_output_dir + "migrate_tracks_command.txt", "w")
    console_output.write(str(migrate_tracks_command))
    subprocess.call(migrate_tracks_command, shell=False, stderr=console_output, stdout=console_output)

    if copy_if_failed:
        with open(context.console_output_dir + "migrate_tracks_command.txt") as f:
            if 'Conversion failed!' in f.read():
                import os
                import shutil

                print("Migrating Tracks failed... copying video in order to continue with dandere2x.")
                os.remove(output_file)
                shutil.copy(no_audio, output_file)


def concat_two_videos(context: Context, video_1: str, video_2: str, output_video: str):
    # load context
    log = logging.getLogger()
    workspace = context.workspace
    temp_concat_file = workspace + "concat_list.txt"

    # we need to create a text file for ffmpeg's concat function to work properly.
    file = open(temp_concat_file, "a")
    file.write("file " + "'" + video_1 + "'" + "\n")
    file.write("file " + "'" + video_2 + "'" + "\n")
    file.close()
    concat_command = [context.ffmpeg_dir,
                      "-f",
                      "concat",
                      "-safe",
                      "0",
                      "-i",
                      temp_concat_file,
                      "-c",
                      "copy",
                      output_video]

    log.info("concat_command: %s" % str(concat_command))
    console_output = open(context.console_output_dir + "concat_video_from_text_file.txt", "w")
    console_output.write(str(concat_command))
    subprocess.call(concat_command, shell=False, stderr=console_output, stdout=console_output)

    import os
    os.remove(temp_concat_file)


def create_video_from_specific_frames(context: Context, file_prefix, output_file, start_number, frames_per_video):
    """
    Create a video using the 'start_number' ffmpeg flag and the 'vframes' input flag to create a video
    using frames for a range of output images.
    """

    # load context
    logger = context.logger
    extension_type = context.extension_type
    input_files = file_prefix + "%d" + extension_type

    video_from_frames_command = [context.ffmpeg_dir,
                                 "-start_number", str(start_number),
                                 "-hwaccel", context.hwaccel,
                                 "-framerate", str(context.frame_rate),
                                 "-i", input_files,
                                 "-vframes", str(frames_per_video),
                                 "-r", str(context.frame_rate)]

    frame_to_video_option = get_options_from_section(context.config_yaml["ffmpeg"]["frames_to_video"]['output_options']
                                                     , ffmpeg_command=True)

    for element in frame_to_video_option:
        video_from_frames_command.append(element)

    video_from_frames_command.extend([output_file])

    logger.info("running ffmpeg command: " + str(video_from_frames_command))

    console_output = open(context.console_output_dir + "video_from_frames_command.txt", "w")
    console_output.write(str(video_from_frames_command))
    subprocess.call(video_from_frames_command, shell=False, stderr=console_output, stdout=console_output)
