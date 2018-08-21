import unittest
from .loading import DocbHandler

import boto3

from moto import mock_dynamodb2,mock_s3

import docb.document

@mock_dynamodb2
def create_table():
    ddb = boto3.resource('dynamodb')
    table = ddb.create_table(
        AttributeDefinitions=[
            {
                'AttributeName': 'name',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'slug',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'email',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'city',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'gpa',
                'AttributeType': 'N'
            },
            {
                'AttributeName': 'date_created',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'date_created',
                'AttributeType': 'S'
            },
        ],
        TableName='docbtest',
        KeySchema=[
            {
                'AttributeName': '_id',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': '_doc_type',
                'KeyType': 'RANGE'
            },
        ],

        GlobalSecondaryIndexes=[
            {
                'IndexName': 'slug-index',
                'KeySchema': [
                    {
                        'AttributeName': 'slug',
                        'KeyType': 'HASH'
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': '_doc_type-index',
                'KeySchema': [
                    {
                        'AttributeName': '_doc_type',
                        'KeyType': 'HASH'
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': 'email-index',
                'KeySchema': [
                    {
                        'AttributeName': 'email',
                        'KeyType': 'HASH'
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': 'name-index',
                'KeySchema': [
                    {
                        'AttributeName': 'name',
                        'KeyType': 'HASH'
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            },
            {
                'IndexName': 'city-index',
                'KeySchema': [
                    {
                        'AttributeName': 'city',
                        'KeyType': 'HASH'
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 2,
                    'WriteCapacityUnits': 2
                }
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 2,
            'WriteCapacityUnits': 2
        }
    )
    table.meta.client.get_waiter('table_exists').wait(TableName='docbtest')
    return table


def create_handler():
    with mock_dynamodb2():
        return DocbHandler({
            'dynamodb': {
                'backend': 'docb.db.DynamoDB',
                'connection': {
                    'table': 'docbtest',
                    'table_obj': create_table()
                },
                'config':{
                    'write_capacity':2,
                    'read_capacity':2
                }
            },
        })


docb_handler = create_handler()

class TestDocument(docb.document.Document):
    name = docb.properties.CharProperty(
        required=True,
        unique=True,
        min_length=5,
        max_length=20)
    last_updated = docb.properties.DateTimeProperty(auto_now=True)
    date_created = docb.properties.DateProperty(auto_now_add=True)
    is_active = docb.properties.BooleanProperty(default_value=True)
    no_subscriptions = docb.properties.IntegerProperty(
        default_value=1, min_value=1, max_value=20)
    gpa = docb.properties.FloatProperty()

    def __unicode__(self):
        return self.name

    class Meta:
        use_db = 'dynamodb'
        handler = docb_handler


class BaseTestDocumentSlug(TestDocument):
    slug = docb.properties.CharProperty(required=True, unique=True,write_capacity=2,
                        read_capacity=2)
    email = docb.properties.CharProperty(required=True, unique=True,write_capacity=2,
                         read_capacity=2)
    city = docb.properties.CharProperty(required=True, index=True,write_capacity=2,
                        read_capacity=2)


@mock_s3
class DynamoTestDocumentSlug(BaseTestDocumentSlug):
    pass


class DynamoTestCustomIndex(TestDocument):
    slug = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                        read_capacity=2)
    email = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                         read_capacity=2)
    city = docb.properties.CharProperty(required=True, index=True, index_name='custom-index',
                        write_capacity=2,read_capacity=2)


@mock_dynamodb2
@mock_s3
class DocbTestCase(unittest.TestCase):

    doc_class = TestDocument

    def pre_setUp(self):

        self.docb_handler = create_handler()
        self.docb_handler.add_docs(self.doc_class,'dynamodb')
        self.doc_class.Meta.handler = self.docb_handler