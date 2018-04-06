import argparse
import datetime
import glob
import logging
import os
import shutil
import sys

from PIL import Image


def main(args_in=sys.argv[1:]):
    setup_logging()
    args = parse_args(args_in)
    images_source = find_images(args)

    for image_source in images_source:
        timestamp = get_timestamp(image_source)
        image_target = get_image_target(args, image_source, timestamp)
        image_target = check_duplicate(args, image_source, image_target)
        image_target = add_suffix(image_target)
        add_image_to_archive(args, image_source, image_target)

    sys.exit(0)


def setup_logging():
    """Set up and start logger."""
    logger = logging.getLogger()  # create logger
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)  # create console handler
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s|%(levelname)s: %(message)s')
    ch.setFormatter(formatter)

    logger.addHandler(ch)  # add the handlers to the logger


def parse_args(args_in):
    """Parsing of input arguments."""

    def path_to_folder(input_string):
        path = input_string
        if not os.path.isdir(path):
            msg = 'Folder "{}" not found!'.format(input_string)
            raise argparse.ArgumentTypeError(msg)
        return path

    def image_extensions(input_string):
        return input_string.split(',')

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--imageFolder', help='Path to folder with images to archive', dest='imageFolder',
                        required=True, type=path_to_folder)
    parser.add_argument('-e', '--imageExtensions', help='Extensions of images to archive separated by commas',
                        dest='imageExtensions', required=False, default=['jpg', 'jpeg'], type=image_extensions)
    parser.add_argument('-a', '--imageArchive', help='Path to folder with image archive', dest='imageArchive',
                        required=True, type=path_to_folder)
    parser.add_argument('-m', '--mode', help='Move or copy image files to archive?', dest='mode',
                        required=False, default='copy', choices=['copy', 'move'])
    args = parser.parse_args(args_in)

    if args.imageFolder == args.imageArchive:
        logging.error('Same paths provided for "imageFolder" and "imageArchive"!')
        sys.exit(1)

    return args


def find_images(args):
    """Find all images recursively."""
    images_source = []
    for ext in args.imageExtensions:
        images_to_add = glob.glob(os.path.join(args.imageFolder, '**/*.' + ext), recursive=True)
        if images_to_add:
            images_source.extend(images_to_add)
    if not images_source:
        logging.error('No images found in "{}"!'.format(args.imageFolder))
        sys.exit(1)
    return images_source


def get_timestamp(image):
    """Get timestamp of an image from exif data."""
    # DateTimeOriginal (36867), SubsecTimeOriginal (37521):
    #   date and time when images was captured
    # DateTimeDigitized (36868), SubsecTimeOriginal (37522):
    #   date and time of when images was digitized, e.g. scanning of an image
    # DateTime (306), SubsecTime (37520):
    #   date and time of when image file was created or last edited
    exif_tags = [(36867, 37521),
                 (36868, 37522),
                 (306, 37520)]
    exif = Image.open(image)._getexif()
    if exif is None:  # image has no exif data
        return None
    else:
        for tag in exif_tags:
            datetime_exif = exif.get(tag[0])
            subseconds_exif = int(exif.get(tag[1], 0)) / 1000  # subseconds are milliseconds
            if datetime_exif is not None:  # stop if timestamp was found in exif tag
                break
        if datetime_exif is None:
            return None
        else:
            timestamp = datetime.datetime.strptime(datetime_exif, '%Y:%m:%d %H:%M:%S') + \
                        datetime.timedelta(0, subseconds_exif)
            return timestamp


def get_image_target(args, image_source, timestamp):
    """Get target filename of image in image archive."""
    if timestamp is not None:
        year = timestamp.strftime('%Y')
        month = timestamp.strftime('%m')
        file = timestamp.strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]  # %f gives microseconds, but we only want milliseconds
        ext = os.path.splitext(image_source)[1]
        image_target = os.path.join(args.imageArchive, year, month, file + ext)
    else:
        image_target = os.path.join(args.imageArchive, 'no_exif_data', os.path.basename(image_source))
    return image_target


def check_duplicate(args, image_source, image_target):
    """Check if a duplicate image exists alread in image archive and alter image_target if necessary."""
    if os.path.exists(image_target):
        if isduplicate(image_source, image_target):
            image_target = os.path.join(args.imageArchive, 'duplicate_images', os.path.basename(image_target))
    return image_target


def isduplicate(image1, image2):
    """Check if two image files are identical."""
    return open(image1, 'rb').read() == open(image2, 'rb').read()


def add_suffix(image_target):
    """Adds suffix to image_target if a file with the same path already exists."""
    ext = os.path.splitext(image_target)[1]
    i_suffix = 1
    while os.path.exists(image_target):
        image_target = image_target.replace(ext, '_{:02d}'.format(i_suffix) + ext)
        i_suffix += 1
    return image_target


def add_image_to_archive(args, image_source, image_target):
    if image_target is not None:
        logging.info('{} "{}" to "{}"'.format(args.mode, image_source, image_target))
        os.makedirs(os.path.dirname(image_target), exist_ok=True)
        if args.mode == 'copy':
            shutil.copy(image_source, image_target)
        elif args.mode == 'move':
            shutil.move(image_source, image_target)
    else:
        pass


if __name__ == '__main__':
    main(sys.argv[1:])