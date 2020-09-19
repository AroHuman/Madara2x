#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    This file is part of the Dandere2x project.
    Dandere2x is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    Dandere2x is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with Dandere2x.  If not, see <https://www.gnu.org/licenses/>.
""""""
========= Copyright aka_katto 2018, All rights reserved. ============
Original Author: aka_katto 
Purpose: 
====================================================================="""

import logging
import math
import threading
from context import Context
from dandere2xlib.utils.dandere2x_utils import get_lexicon_value, get_list_from_file_and_wait

from wrappers.frame.frame import DisplacementVector, Frame


class Residual(threading.Thread):

    def __init__(self, context):
        self.context = context

        # load variables from context
        self.workspace = context.workspace
        self.residual_upscaled_dir = context.residual_upscaled_dir
        self.residual_images_dir = context.residual_images_dir
        self.residual_data_dir = context.residual_data_dir
        self.pframe_data_dir = context.pframe_data_dir
        self.input_frames_dir = context.input_frames_dir
        self.frame_count = context.frame_count
        self.block_size = context.block_size
        self.extension_type = context.extension_type
        self.debug_dir = context.debug_dir
        self.debug = context.debug
        self.temp_image = context.temp_image_folder + "tempimage.jpg"
        self.log = logging.getLogger()
        self.start_frame = self.context.start_frame

        # Threading Specific
        threading.Thread.__init__(self, name="ResidualThread")

    def join(self, timeout=None):
        self.log.info("Join called.")
        threading.Thread.join(self, timeout)
        self.log.info("Join finished.")

    def set_start_frame(self, start_frame: int):
        self.start_frame = start_frame

    def run(self):
        self.log.info("Run called.")

        for x in range(self.start_frame, self.frame_count):

            # Stop if thread is killed
            if not self.context.controller.is_alive():
                break

            # Files needed to create a residual image
            f1 = Frame()
            f1.load_from_string_controller(self.input_frames_dir + "frame" + str(x + 1) + self.extension_type,
                                           self.context.controller)
            # Load the neccecary lists to compute this iteration of residual making
            residual_data = get_list_from_file_and_wait(self.residual_data_dir + "residual_" + str(x) + ".txt",
                                                        self.context.controller)

            prediction_data = get_list_from_file_and_wait(self.pframe_data_dir + "pframe_" + str(x) + ".txt",
                                                          self.context.controller)

            # stop if thread is killed
            if not self.context.controller.is_alive():
                break

            # Create the output files..
            debug_output_file = self.debug_dir + "debug" + str(x + 1) + self.extension_type
            output_file = self.residual_images_dir + "output_" + get_lexicon_value(6, x) + ".jpg"

            # Save to a temp folder so waifu2x-vulkan doesn't try reading it, then move it
            out_image = self.make_residual_image(self.context, f1, residual_data, prediction_data)

            if out_image.get_res() == (1, 1):
                """
                If out_image is (1,1) in size, then frame_x and frame_x+1 are identical.

                We still need to save an outimage for sake of having N output images for N input images, so we
                save these meaningless files anyways.

                However, these 1x1 can slow whatever waifu2x implementation down, so we 'cheat' d2x 
                but 'fake' upscaling them, so that they don't need to be processed by waifu2x.
                """

                # Location of the 'fake' upscaled image.
                out_image = Frame()
                out_image.create_new(2, 2)
                output_file = self.residual_upscaled_dir + "output_" + get_lexicon_value(6, x) + ".png"
                out_image.save_image(output_file)

            else:
                # This image has things to upscale, continue normally
                out_image.save_image_temp(output_file, self.temp_image)

            # With this change the wrappers must be modified to not try deleting the non existing residual file
            if self.context.debug == 1:
                self.debug_image(self.block_size, f1, prediction_data, residual_data, debug_output_file)

    @staticmethod
    def make_residual_image(context: Context, raw_frame: Frame, list_residual: list, list_predictive: list):
        """
        This section can best be explained through pictures. A visual way of expressing what 'make_residual_image'
        is doing is this section in the wiki.

        https://github.com/aka-katto/dandere2x/wiki/How-Dandere2x-Works#observation_3

        Inputs:
            - frame(x)
            - Residual vectors mapping frame(x)_residual -> frame(x)

        Output:
            - frame(x)_residual
        """

        # Some conditions to check before making a residual image, in both cases, we don't need to do any actual
        # processing in the function call, if these conditions hold true.
        if not list_residual and list_predictive:
            """
            If there are no items in 'list_residuals' but have list_predictives then the two frames are identical,
            so no residual image needed.
            """
            residual_image = Frame()
            residual_image.create_new(1, 1)
            return residual_image

        if not list_residual and not list_predictive:
            """ 
            If there are neither any predictive or inversions, then the frame is a brand new frame with no resemblence
            to previous frame. In this case, copy the entire frame over.
            """
            residual_image = Frame()
            residual_image.create_new(raw_frame.width, raw_frame.height)
            residual_image.copy_image(raw_frame)
            return residual_image

        buffer = 5
        block_size = context.block_size
        bleed = context.bleed
        """
        First make a 'bleeded' version of input_frame, as we need to create a buffer in the event the 'bleed'
        ends up going out of bounds. In other words, crop the image into an even larger image, so that if if we need
        to access out of bounds pixels, and place black pixels where it would be out of bounds. 
        """
        bleed_frame = raw_frame.create_bleeded_image(buffer)

        # size of output image is determined based off how many residuals there are
        image_size = int(math.sqrt(len(list_residual) / 4) + 1) * (block_size + bleed * 2)
        residual_image = Frame()
        residual_image.create_new(image_size, image_size)

        for x in range(int(len(list_residual) / 4)):
            # load every element in the list into a vector
            vector = DisplacementVector(int(list_residual[x * 4 + 0]),
                                        int(list_residual[x * 4 + 1]),
                                        int(list_residual[x * 4 + 2]),
                                        int(list_residual[x * 4 + 3]))

            # apply that vector to the image by copying over their respective blocks.
            residual_image.copy_block(bleed_frame, block_size + bleed * 2,
                                      vector.x_1 + buffer - bleed, vector.y_1 + buffer + - bleed,
                                      vector.x_2 * (block_size + bleed * 2), vector.y_2 * (block_size + bleed * 2))

        return residual_image

    @staticmethod
    def debug_image(block_size, frame_base, list_predictive, list_differences, output_location):
        """
        Note:
            I haven't made an effort to maintain this method, as it's only for debugging.

        This section can best be explained through pictures. A visual way of expressing what 'debug'
        is doing is this section in the wiki.

        https://github.com/aka-katto/dandere2x/wiki/How-Dandere2x-Works#part-1-identifying-what-needs-to-be-drawn

        In other words, this method shows where residuals are, and is useful for finding good settings to use for a video.

        Inputs:
            - frame(x)
            - Residual vectors mapping frame(x)_residual -> frame(x)

        Output:
            - frame(x) minus frame(x)_residuals = debug_image
        """
        logger = logging.getLogger(__name__)

        difference_vectors = []
        predictive_vectors = []
        out_image = Frame()
        out_image.create_new(frame_base.width, frame_base.height)
        out_image.copy_image(frame_base)

        black_image = Frame()
        black_image.create_new(frame_base.width, frame_base.height)

        if not list_predictive and not list_differences:
            out_image.save_image(output_location)
            return

        if list_predictive and not list_differences:
            out_image.copy_image(frame_base)
            out_image.save_image(output_location)
            return

        # load list into vector displacements
        for x in range(int(len(list_differences) / 4)):
            difference_vectors.append(DisplacementVector(int(list_differences[x * 4]),
                                                         int(list_differences[x * 4 + 1]),
                                                         int(list_differences[x * 4 + 2]),
                                                         int(list_differences[x * 4 + 3])))
        for x in range(int(len(list_predictive) / 4)):
            if (int(list_predictive[x * 4 + 0]) != int(list_predictive[x * 4 + 1])) and \
                    (int(list_predictive[x * 4 + 2]) != int(list_predictive[x * 4 + 3])):
                predictive_vectors.append(DisplacementVector(int(list_predictive[x * 4 + 0]),
                                                             int(list_predictive[x * 4 + 1]),
                                                             int(list_predictive[x * 4 + 2]),
                                                             int(list_predictive[x * 4 + 3])))

        # copy over predictive vectors into new image
        for vector in difference_vectors:
            out_image.copy_block(black_image, block_size,
                                 vector.x_1, vector.y_1,
                                 vector.x_1, vector.y_1)

        out_image.save_image_quality(output_location, 25)
