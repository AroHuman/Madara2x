import logging
import os

import math

from Dandere2xUtils import get_lexicon_value
from Dandere2xUtils import wait_on_text
from Frame import DisplacementVector
from Frame import Frame


def generate_difference_image(raw_frame, block_size, bleed, list_difference, list_predictive, out_location):
    difference_vectors = []
    buffer = 5

    # first make a 'bleeded' version of input_frame
    # so we can preform numpy calculations w.o having to catch
    bleed_frame = raw_frame.create_bleeded_image(buffer)

    # if there are no items in 'differences' but have list_predictives
    # then the two frames are identical, so no differences image needed.
    if not list_difference and list_predictive:
        out_image = Frame()
        out_image.create_new(1, 1)
        out_image.save_image(out_location)
        return

    # if there are neither any predictive or inversions
    # then the frame is a brand new frame with no resemblence to previous frame.
    # in this case copy the entire frame over
    if not list_difference and not list_predictive:
        out_image = Frame()
        out_image.create_new(raw_frame.width, raw_frame.height)
        out_image.copy_image(raw_frame)
        out_image.save_image(out_location)
        return

    # turn the list of differences into a list of vectors
    for x in range(int(len(list_difference) / 4)):
        difference_vectors.append(DisplacementVector(int(list_difference[x * 4]), int(list_difference[x * 4 + 1]),
                                                     int(list_difference[x * 4 + 2]), int(list_difference[x * 4 + 3])))

    # size of image is determined based off how many differences there are
    image_size = int(math.sqrt(len(list_difference) / 4) + 1) * (block_size + bleed * 2)
    out_image = Frame()
    out_image.create_new(image_size, image_size)

    # move every block from the complete frame to the differences frame using vectors.
    for vector in difference_vectors:
        out_image.copy_block(bleed_frame, block_size + bleed * 2, vector.x_1 + buffer - bleed,
                             vector.y_1 + buffer + - bleed,
                             vector.x_2 * (block_size + bleed * 2), vector.y_2 * (block_size + bleed * 2))

    out_image.save_image(out_location)


def difference_loop(workspace, start_frame, count, block_size, file_type):
    logger = logging.getLogger(__name__)
    bleed = 1
    logger.info((workspace, start_frame, count, block_size))
    for x in range(start_frame, count):
        f1 = Frame()
        f1.load_from_string_wait(workspace + "inputs" + os.path.sep + "frame" + str(x + 1) + file_type)
        logger.info("waiting on text")
        logger.info(f1)
        difference_data = wait_on_text(workspace + "inversion_data" + os.path.sep + "inversion_" + str(x) + ".txt")
        prediction_data = wait_on_text(workspace + "pframe_data" + os.path.sep + "pframe_" + str(x) + ".txt")

        generate_difference_image(f1, block_size, bleed, difference_data, prediction_data,
                                  workspace + "outputs" + os.path.sep + "output_" + get_lexicon_value(6, x) + ".png")


# def difference_loop(workspace, start_frame, count, block_size):
def difference_loop_resume(workspace, count, block_size, file_type):
    logger = logging.getLogger(__name__)
    last_found = count
    while last_found > 0:
        exists = os.path.isfile(
            workspace + os.path.sep + "outputs" + os.path.sep + "output_" + get_lexicon_value(6, last_found) + ".png")

        if not exists:
            last_found -= 1

        elif exists:
            break

    last_found += 1
    logger.info("difference loop last frame found: " + str(last_found))

    difference_loop(workspace, last_found, count, block_size, file_type)


def main():
    print("path sep", os.path.sep)
    difference_loop_resume("C:\\Users\\windwoz\\Desktop\\workspace\\stealpython\\", 95, 16)


if __name__ == "__main__":
    main()