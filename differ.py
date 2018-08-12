import boto3
import math, operator
from functools import reduce
from PIL import Image, ImageChops
import os
import requests
import uuid

# Config

EXAMPLE_IMG_A = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_IMG_B = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_DST = 'compare'
EXAMPLE_BUCKET = 'img-diff'
EXAMPLE_BUCKET_PREFIX = 'compare'


class Differ(object):
    """Differ is responsible for handling visual diff generation and delivery.

    """

    def __init__(self, aws_server_public_key=None, aws_server_secret_key=None):
        """Initialization creates an AWS session to access S3.

        Differ is initialized with AWS public key and secret key for creating
        an S3 session used for uploading finished image diffs to a provided S3
        bucket.  If no arguments are provided, boto3 attempts to authorize the
        session from credentials stored on the local machine.

        Args:
            aws_server_public_key (str, optional): AWS Public Key.
            aws_server_secret_key (str, optional): AWS Secret key.

        """
        if all([aws_server_public_key, aws_server_secret_key]):
            self.session = boto3.Session(
                aws_access_key_id=aws_server_public_key,
                aws_secret_access_key=aws_server_secret_key,
            )
        else:
            self.session = boto3.Session()
        self.s3 = self.session.resource('s3')

    def rmsdiff_1997(self, im1, im2):
        "Calculate the root-mean-square difference between two images"

        h = ImageChops.difference(im1, im2).histogram()

        # calculate rms
        return math.sqrt(
            reduce(operator.add,
                map(
                    lambda h,
                    i: h*(i**2),
                    h,
                    range(256)
                )
            ) / (float(im1.size[0]) * im1.size[1])
        )

    def download(self, image_url, dst, filename):
        """Downloads image from url to local disk.

        Args:
            image_url: URL of image to be downloaded.
            dst: Destination folder.
            filename: Destination filename.

        Returns:
            Path to local path of downloaded image.

        """
        try:
            os.makedirs(dst)
        except Exception:
            pass

        r = requests.get(image_url)
        filepath = os.path.join(dst, filename)
        with open(filepath, 'wb') as f:
            f.write(r.content)
        return filepath

    def mask(self, image_a, image_b, dst=None, filename=None):
        """Creates mask image represented from subtraction of two images.

        Args:
            image_a_path: Local image path or image object of minuend.
            image_b_path: Local image path or image object subtrahend.
            dst: Optional destination folder.
            filename: Optional destination filename.

        Returns:
            If dst and filename are provided, the resulting image is saved
            and the path to the saved image is returned. Otherwise, the image
            object is returned.

        """
        def nonzero(a):
            return 0 if a < 10 else 255

        if type(image_a) is str:
            image_a = Image.open(image_a)
        image_a = image_a.convert('RGB')
        if type(image_b) is str:
            image_b = Image.open(image_b)
        image_b = image_b.convert('RGB')
        mask = Image.eval(
            ImageChops.subtract(image_a, image_b), nonzero).convert('1')
        im = Image.composite(image_a, Image.eval(image_b, lambda x: 0), mask)
        if all([dst, filename]):
            destination_path = os.path.join(dst, filename)
            im.save(destination_path)
            return destination_path
        return im

    def color(
            self,
            background,
            mask,
            rgba,
            opacity,
            dst=None,
            filename=None):
        """Replaces non-transparent pixel colors with provided pixel color.

        Args:
            background: Local background image path or image object which will
                not have pixels changed.
            mask: Local mask image path or image object which will have pixels
                changed.
            rgba: Tuple containing rgba values that represent what matching
                pixels will be changed to.
            opacity: Opacity (float) of overlay image.
            dst: Optional destination folder.
            filename: Optional destination filename.

        Returns:
            If dst and filename are provided, the resulting image is saved
            and the path to the saved image is returned. Otherwise, the image
            object is returned.

        """
        if type(background) is str:
            background = Image.open(background)
        background_img = background.copy().convert('RGBA')
        if type(mask) is str:
            mask = Image.open(mask)
        overlay_img = mask.convert('RGBA')
        pixdata = overlay_img.load()
        width, height = mask.size
        for y in range(height):
            for x in range(width):
                if pixdata[x, y] != (255, 255, 255, 0):
                    if pixdata[x, y] == (0, 0, 0, 255):
                        pixdata[x, y] = (255, 255, 255, 0)
                    else:
                        pixdata[x, y] = rgba
        img = Image.alpha_composite(background_img, overlay_img)
        if all([dst, filename]):
            destination_path = os.path.join(dst, filename)
            img.save(destination_path)
            return destination_path
        return img

    def upload(self, file_path, bucket, bucket_prefix=None):
        """Uploads file from local path to destination S3 bucket.

        Args:
            file_path: path of file to be uploaded to S3.

        Todo:
            * Handle exceptions and determine success or failure.
            * Make ACL of uploaded file configurable.
            * Handle ContentType detection intelligently.
            * Make S3 key formatting configurable.

        Returns:
            True if successful, False otherwise.

        """

        fname, file_extension = os.path.splitext(file_path)
        filename = '{}-{}{}'.format(
            fname.split('/')[-1], uuid.uuid4().hex, file_extension)
        if bucket_prefix is not None and bucket_prefix != '':
            filename = '{}/{}-{}{}'.format(
                bucket_prefix,
                fname.split('/')[-1],
                uuid.uuid4().hex,
                file_extension
            )
        self.s3.meta.client.upload_file(
            file_path,
            bucket,
            filename,
            {
                'ACL': 'public-read',
                'ContentType': 'image/{}'.format(
                    file_extension.replace('.', ''))
            }
        )
        return True

    def diff(
            self,
            image_a_url,
            image_b_url,
            dst,
            bucket,
            bucket_prefix='',
            prefix='image',
            opacity=0.65,
            threshold=0):
        """Generates visual diff of two images.

        Args:
            image_a_url: URL of before image.
            image_b_url: URL of after image.
            dst: Local destination folder for downloaded/created images.
            bucket: Destination S3 bucket name for finalized images.
            bucket_prefix: Prefix used when uploading to S3 bucket.
            prefix: Prefix used in finalized S3 filenames.
            opacity: Opacity (float) setting for overlaying diff highlights.
            threshold: Threshold (float) for difference between images.

        Todo:
            * Handle exceptions and determine success or failure.

        Returns:
            True if successful, False otherwise.

        """
        image_a_path = self.download(
            image_a_url,
            dst,
            '{}_a.{}'.format(
                prefix, image_a_url.split('/')[-1].split('.')[-1]))
        image_b_path = self.download(
            image_b_url,
            dst,
            '{}_b.{}'.format(
                prefix, image_b_url.split('/')[-1].split('.')[-1]))
        image_a = Image.open(image_a_path)
        image_b = Image.open(image_b_path)
        diff = self.rmsdiff_1997(image_a, image_b)
        if diff <= threshold:
            return False
        add_mask_img = self.mask(image_b, image_a)
        add_img_path = self.color(
            image_b,
            add_mask_img,
            (0, 255, 0, 255),
            opacity,
            dst,
            'add.png')
        self.upload(
            add_img_path, bucket, bucket_prefix=bucket_prefix)
        remove_mask_img = self.mask(image_a, image_b)
        remove_img_path = self.color(
            image_a,
            remove_mask_img,
            (255, 0, 0, 255),
            opacity,
            dst,
            'remove.png')
        self.upload(remove_img_path, bucket, bucket_prefix=bucket_prefix)
        return True
