import unittest
from .loading import DocbHandler
from envs import env

docb_handler = DocbHandler({
    'dynamodb': {
        'backend': 'docb.backends.dynamodb.db.DynamoDB',
        'connection': {
            'table': env('DYNAMO_TABLE_TEST'),
            'endpoint_url': env('DYNAMO_ENDPOINT_URL_TEST')
        }
    },
})


class DocbTestCase(unittest.TestCase):

    def tearDown(self):
        for db_label in list(docb_handler._databases.keys()):
            docb_handler.get_db(db_label).flush_db()
