from flask import Flask, jsonify, make_response, request, abort, Response
from differ import Differ
import json


app = Flask(__name__)

# Config

EXAMPLE_IMG_A = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_IMG_B = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_DST = 'compare'
EXAMPLE_BUCKET = 'img-diff'
EXAMPLE_BUCKET_PREFIX = 'compare'


def build_response(resp_dict, status_code):
    response = Response(json.dumps(resp_dict), status_code)
    return response


def diff(payload):
    differ = Differ()
    differ.diff(
        payload['before_image_url'],
        payload['after_image_url'],
        payload['dst'],
        payload['bucket'],
        payload['bucket_prefix']
    )


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.route('/')
def differ():
    return "Image Differ!"


@app.route('/v1/diff', methods=['GET', 'POST'])
def diff():
    if not (request.json):
        abort(400)
    diff(request.json)

    return build_response({"status": "success"}, 200)

if __name__ == '__main__':
    app.run()
