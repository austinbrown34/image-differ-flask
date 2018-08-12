from flask import Flask, jsonify, make_response, request, abort
from differ import Differ


app = Flask(__name__)

# Config

EXAMPLE_IMG_A = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_IMG_B = 'https://s3.amazonaws.com/img-diff/pica.png'
EXAMPLE_DST = 'compare'
EXAMPLE_BUCKET = 'img-diff'
EXAMPLE_BUCKET_PREFIX = 'compare'


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
    differ = Differ()
    response = differ.diff(
        request.json['before_image_url'],
        request.json['after_image_url'],
        request.json['dst'],
        request.json['bucket'],
        request.json['bucket_prefix']
    )

    return jsonify(response)

if __name__ == '__main__':
    app.run()
