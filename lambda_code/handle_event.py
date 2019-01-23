import boto3
import os
import hmac
import base64
import hashlib
import logging


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def lambda_handler(event, context):
    if not event.get('shopify_hmac'):
        LOGGER.warning('Request did not contain a Shopify HMAC digest header')
        LOGGER.warning(event)
        return

    authentic_key_digest = hmac.HMAC(os.environ['SHOPIFY_AUTHENTICATION_KEY'].encode(), event['body'].encode(),
                                     hashlib.sha256).digest()
    request_digest = base64.b64decode(event['shopify_hmac'])
    if not hmac.compare_digest(authentic_key_digest, request_digest):
        LOGGER.warning('Computed digest does not match value from Shopift HMAC digest header')
        LOGGER.warning(event)
        return

    # New line character is required so that Athena will read multiple JSON objects in a single file
    # For details, see here: https://stackoverflow.com/\
    # questions/48226472/kinesis-firehose-putting-json-objects-in-s3-without-seperator-comma/51273983#51273983
    body = event['body'] + '\n'
    client = boto3.client('firehose')
    client.put_record(
        DeliveryStreamName=os.environ['KINESIS_FIREHOSE'],
        Record={
            'Data': body.encode()
        }
    )

    LOGGER.info('Successfully added event to Kinesis Firehose')
