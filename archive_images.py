import argparse
import datetime
import glob
import logging
import os
import shutil
import sys

from PIL import Image


class ArchiveImages:

    def __init__(self, args_in=sys.argv[1:]):

        self.args = None
        self.images = None

        self.setup_logging()
        self.parse_args(args_in)
        self.find_images()

        for image in self.images:
            timestamp = self.get_timestamp(image)
            if timestamp is not None:
                self.archive_image(image, timestamp)
            else:
                logging.warning('Skip "{}" due to missing exif data!'.format(image))

        sys.exit(0)

    @staticmethod
    def setup_logging():
        """Set up and start logger."""
        logger = logging.getLogger()  # create logger
        logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)  # create console handler
        ch.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s|%(levelname)s: %(message)s')
        ch.setFormatter(formatter)

        logger.addHandler(ch)  # add the handlers to the logger

    def parse_args(self, args_in):
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
        parser.add_argument('-d', '--deleteDuplicates',
                            help='Delete image in "imageFolder" if a duplicate is already present in "imageArchive"?',
                            dest='deleteDuplicates', required=False, default=False, action='store_true')
        self.args = parser.parse_args(args_in)

        if self.args.imageFolder == self.args.imageArchive:
            logging.error('Same paths provided for "imageFolder" and "imageArchive"!')
            sys.exit(1)

    def find_images(self):
        """Find all images recursively."""
        self.images = []
        for ext in self.args.imageExtensions:
            images_to_add = glob.glob(os.path.join(self.args.imageFolder, '**/*.' + ext), recursive=True)
            if images_to_add:
                self.images.extend(images_to_add)
        if not self.images:
            logging.error('No images found in "{}"!'.format(self.args.imageFolder))
            sys.exit(1)

    @staticmethod
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

    def archive_image(self, image_source, timestamp):
        """Add an image to the image archive."""
        year = timestamp.strftime('%Y')
        month = timestamp.strftime('%m')
        file = timestamp.strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]  # %f gives microseconds, but we only want milliseconds
        ext = os.path.splitext(image_source)[1]
        image_target = os.path.join(self.args.imageArchive, year, month, file + ext)
        if not os.path.exists(image_target):
            logging.info('{} "{}" to "{}"'.format(self.args.mode, image_source, image_target))
            os.makedirs(os.path.dirname(image_target), exist_ok=True)
            if self.args.mode == 'copy':
                shutil.copy(image_source, image_target)
            elif self.args.mode == 'move':
                shutil.move(image_source, image_target)
        else:
            if self.isduplicate(image_source, image_target):
                if self.args.deleteDuplicates:
                    logging.warning('Delete "{}" as it is a duplicate of "{}"!'.format(image_source, image_target))
                    # os.remove(image_source)
                else:
                    logging.warning('Skip "{}" as it is a duplicate of "{}"!'.format(image_source, image_target))
            else:
                pass

    @staticmethod
    def isduplicate(image1, image2):
        return open(image1, 'rb').read() == open(image2, 'rb').read()


if __name__ == '__main__':  # if called directly
    ArchiveImages(sys.argv[1:])  # pass command line arguments to class constructor (stored in sys.argv)

