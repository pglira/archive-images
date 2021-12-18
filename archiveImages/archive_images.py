import argparse
import datetime
import glob
import logging
import os
import shutil
import sys

from PIL import Image


def main(args_in=sys.argv[1:]):
    args = parse_args(args_in)
    setup_logging(args_in, args)
    images_source = find_images(args)

    for idx_image, image_source in enumerate(images_source):
        timestamp = get_timestamp(image_source)
        image_target = get_image_target(
            args, image_source, timestamp, idx_image, len(images_source)
        )
        if image_target is not None:
            image_target = check_duplicate(
                args, image_source, image_target, idx_image, len(images_source)
            )
        if image_target is not None:
            image_target = add_suffix(image_target)
            add_image_to_archive(
                args, image_source, image_target, idx_image, len(images_source)
            )

    logging.info("Finished!")
    sys.exit(0)


def parse_args(args_in):
    """Parsing of input arguments."""

    def path_to_folder(input_string):
        path = input_string
        if not os.path.isdir(path):
            msg = 'Folder "{}" not found!'.format(input_string)
            raise argparse.ArgumentTypeError(msg)
        return path

    def image_extensions(input_string):
        return input_string.split(",")

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser._action_groups.pop()
    required = parser.add_argument_group("required arguments")
    optional = parser.add_argument_group("optional arguments")
    required.add_argument(
        "-i",
        "--imageFolder",
        help="Path to folder with images to archive",
        dest="imageFolder",
        required=True,
        type=path_to_folder,
    )
    required.add_argument(
        "-a",
        "--imageArchive",
        help="Path to folder with image archive",
        dest="imageArchive",
        required=True,
        type=path_to_folder,
    )
    optional.add_argument(
        "-e",
        "--imageExtensions",
        help="Extensions of images to archive separated by commas",
        dest="imageExtensions",
        required=False,
        default=["jpg", "jpeg"],
        type=image_extensions,
    )
    optional.add_argument(
        "-m",
        "--mode",
        help="Move or copy image files to archive?",
        dest="mode",
        required=False,
        default="copy",
        choices=["copy", "move"],
    )
    optional.add_argument(
        "-d",
        "--addDuplicates",
        help='Add duplicates to a subfolder "duplicates" in image archive?',
        dest="addDuplicates",
        required=False,
        action="store_true",
    )
    optional.add_argument(
        "-n",
        "--addNoExif",
        help='Add images with no exif information to a subfolder "no_exif" in \
                          image archive?',
        dest="addNoExif",
        required=False,
        action="store_true",
    )
    optional.add_argument(
        "-c",
        "--confirm",
        help="Confirm each operation before execution?",
        dest="confirm",
        required=False,
        action="store_true",
    )
    args = parser.parse_args(args_in)

    if args.imageFolder == args.imageArchive:
        logging.error('Same paths provided for "imageFolder" and "imageArchive"!')
        sys.exit(1)

    return args


def setup_logging(args_in, args):
    """Set up and start logger."""
    output_dir = os.path.join(args.imageArchive, "logs")
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.datetime.now()
    file = "log_" + now.strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    path_to_log = os.path.join(output_dir, file)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create file handler
    fh = logging.FileHandler(path_to_log, mode="w")

    # Create console handler
    ch = logging.StreamHandler(sys.stdout)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter("%(asctime)s|%(levelname)s: %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    # Start and report input arguments
    logging.info("Arguments: " + " ".join(args_in))


def find_images(args):
    """Find all images recursively."""
    images_source = []
    for ext in args.imageExtensions:
        images_to_add = glob.glob(
            os.path.join(args.imageFolder, "**/*." + ext), recursive=True
        )
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
    exif_tags = [(36867, 37521), (36868, 37522), (306, 37520)]
    exif = read_exif(image)
    if exif is not None:
        for tag in exif_tags:
            datetime_exif = exif.get(tag[0])
            subseconds_exif = (
                int(exif.get(tag[1], 0)) / 1000
            )  # subseconds are milliseconds
            if datetime_exif is not None:  # stop if timestamp was found in exif tag
                break
        if datetime_exif is None:
            return None
        else:
            timestamp = datetime.datetime.strptime(
                datetime_exif, "%Y:%m:%d %H:%M:%S"
            ) + datetime.timedelta(0, subseconds_exif)
            return timestamp
    else:  # image has no exif data
        return None


def read_exif(image):
    """Read exif data from image."""
    try:
        img = Image.open(image)
    except IOError:
        logging.error('"{}" can not be opened as image!'.format(image))
        sys.exit(1)
    get_exif = getattr(img, "_getexif", None)
    if callable(
        get_exif
    ):  # if instance 'img' has method 'get_exif' (e.g. not true for png files)
        exif = img._getexif()
    else:
        exif = None
    return exif


def get_image_target(args, image_source, timestamp, idx_image, num_images):
    """Get target filename of image in image archive."""
    if timestamp is not None:
        year = timestamp.strftime("%Y")
        month = timestamp.strftime("%m")
        file = timestamp.strftime("%Y_%m_%d_%H_%M_%S.%f")[
            :-3
        ]  # %f gives microseconds, but we only want milliseconds
        ext = os.path.splitext(image_source)[1]
        image_target = os.path.join(args.imageArchive, year, month, file + ext.lower())
    else:
        if args.addNoExif:
            image_target = os.path.join(
                args.imageArchive, "no_exif_data", os.path.basename(image_source)
            )
        else:
            logging.warning(
                'Image {} of {}: skip "{}" due to missing exif data!'.format(
                    idx_image + 1, num_images, image_source
                )
            )
            image_target = None
    return image_target


def check_duplicate(args, image_source, image_target, idx_image, num_images):
    """Check if a duplicate image exists already in image archive and alter image_target if necessary."""
    if os.path.isdir(os.path.dirname(image_target)):
        files_to_check = [
            name
            for name in os.listdir(os.path.dirname(image_target))
            if name.startswith(os.path.splitext(os.path.basename(image_target))[0])
        ]
        for file in files_to_check:
            if isduplicate(
                image_source, os.path.join(os.path.dirname(image_target), file)
            ):
                if args.addDuplicates:
                    image_target = os.path.join(
                        args.imageArchive,
                        "duplicate_images",
                        os.path.basename(image_target),
                    )
                else:
                    logging.warning(
                        'Image {} of {}: skip "{}" as it is a duplicate of "{}"!'.format(
                            idx_image + 1,
                            num_images,
                            image_source,
                            os.path.join(os.path.dirname(image_target), file),
                        )
                    )
                    image_target = None
                return image_target
    return image_target


def isduplicate(image1, image2):
    """Check if two image files are identical."""
    return open(image1, "rb").read() == open(image2, "rb").read()


def add_suffix(image_target):
    """Adds suffix to image_target if a file with the same path already exists."""
    ext = os.path.splitext(image_target)[1]
    image_target_orig = image_target
    i_suffix = 1
    while os.path.exists(image_target):
        image_target = image_target_orig.replace(ext, "_{:02d}".format(i_suffix) + ext)
        i_suffix += 1
    return image_target


def add_image_to_archive(args, image_source, image_target, idx_image, num_images):
    """Adds image to image archive."""
    logging.info(
        'Image {} of {}: {} "{}" to "{}"'.format(
            idx_image + 1, num_images, args.mode, image_source, image_target
        )
    )
    if args.confirm:
        confirm = input(
            '{} "{}" to "{}"? (y/n) '.format(args.mode, image_source, image_target)
        )
        if confirm == "n":
            return
    os.makedirs(os.path.dirname(image_target), exist_ok=True)
    getattr(shutil, args.mode)(image_source, image_target)


if __name__ == "__main__":
    main(sys.argv[1:])
