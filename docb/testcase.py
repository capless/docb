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
    'cloudant': {
        'backend': 'docb.backends.cloudant.db.CloudantDB',
        'connection': {
            'username': env('CLOUDANT_USERNAME_TEST'),
            'password': env('CLOUDANT_PASSWORD_TEST'),
            'url': env('CLOUDANT_URL_TEST'),
            'account': env('CLOUDANT_ACCOUNT_TEST'),
            'table': env('CLOUDANT_TABLE_TEST'),
        }
    }
})


class DocbTestCase(unittest.TestCase):

    def tearDown(self):
        for db_label in list(docb_handler._databases.keys()):
            docb_handler.get_db(db_label).flush_db()
