import unittest
from .loading import DocbHandler

import docb.document


def create_handler():
    return DocbHandler({
        'dynamodb': {
            'connection': {
                'table': 'docbtest'
            },
            'config': {
                'endpoint_url': 'http://dynamodb:8000'
            },
            'table_config': {
                'write_capacity': 2,
                'read_capacity': 2
            }
        },
    })


class TestDocument(docb.document.Document):
    name = docb.properties.CharProperty(required=True, unique=True, min_length=5, max_length=20)
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


class BaseTestDocumentSlug(TestDocument):
    slug = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                                        read_capacity=2)
    email = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                                         read_capacity=2)
    city = docb.properties.CharProperty(required=True, global_index=True, write_capacity=2,
                                        read_capacity=2)


class DynamoTestDocumentSlug(BaseTestDocumentSlug):
    pass


class DynamoTestCustomIndex(TestDocument):
    slug = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                                        read_capacity=2)
    email = docb.properties.CharProperty(required=True, unique=True, write_capacity=2,
                                         read_capacity=2)
    city = docb.properties.CharProperty(required=True, global_index=True, index_name='custom-index',
                                        write_capacity=2, read_capacity=2)


class Student(docb.document.Document):
    first_name = docb.properties.CharProperty(required=True)
    last_name = docb.properties.CharProperty(required=True)
    slug = docb.properties.CharProperty(required=True,unique=True)
    email = docb.properties.CharProperty(required=True, unique=True)
    gpa = docb.properties.FloatProperty(global_index=True)
    hometown = docb.properties.CharProperty(required=True)
    high_school = docb.properties.CharProperty()

    class Meta:
        use_db = 'dynamodb'


class DocbTestCase(unittest.TestCase):
    doc_class = TestDocument

    @classmethod
    def setUpClass(cls):

        cls.docb_handler = create_handler()
        cls.doc_class.Meta.handler = cls.docb_handler
        cls.doc_class().create_table()

    @classmethod
    def tearDown(cls):
        cls.doc_class().flush_db()

    @classmethod
    def tearDownClass(cls):
        cls.doc_class().delete_table()
