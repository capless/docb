import decimal
import json
import hashlib
import uuid
import datetime

import boto3
from boto3.dynamodb.conditions import Attr, Key, And
from botocore.exceptions import ClientError
from valley.exceptions import ValidationException

from docb.exceptions import DocNotFoundError, ResourceError
from docb.utils import get_doc_type


class DynamoDB(object):
    db_class = boto3
    backend_id = 'dynamodb'
    default_index_name = '{0}-index'
    index_field_name = 'index_name'
    doc_id_string = '{doc_id}:id:{backend_id}:{class_name}'
    index_id_string = ''

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._dynamodb_cache = None


    def delete(self, doc_obj):
        self._dynamodb.delete_item(Key={'_id': doc_obj._data['_id']})

    def get(self, doc_obj, doc_id):
        response = self._dynamodb.get_item(Key={'_id': doc_obj.get_doc_id(doc_id)})
        doc = response.get('Item', None)
        if not doc:
            raise DocNotFoundError
        return doc_obj(**doc)

    def parse_id(self, doc_id):
        try:
            return doc_id.split(':')[0]
        except TypeError:
            return doc_id.decode().split(':')[0]

    def create_pk(self, doc_obj,doc):
        doc = doc.copy()
        doc['_date'] = str(datetime.datetime.now())
        doc['_uuid'] = str(uuid.uuid4())
        hash_pk = hashlib.md5(bytes(json.dumps(doc),'utf-8')).hexdigest()[:10]
        doc_obj.set_pk(self.doc_id_string.format(doc_id=hash_pk,
            backend_id=self.backend_id, class_name=doc_obj.get_class_name()))
        return doc_obj

    def check_unique(self, doc_obj, key, value):
        obj = doc_obj.objects().filter({key: value})
        if len(obj) == 0:
            return True
        if hasattr(doc_obj, '_id') and len(obj) == 1:
            if doc_obj._id == obj[0]._id:
                return True
        raise ValidationException(
            'There is already a {key} with the value of {value}'
            .format(key=key, value=value))

    @property
    def _dynamodb(self):
        if self._dynamodb_cache is None:
            self._dynamodb_cache = self.db_class.resource(
                'dynamodb', endpoint_url=self._kwargs.get('endpoint_url', None)) \
                .Table(self._kwargs['table'])
        return self._dynamodb_cache

    def prepare_doc(self, doc_obj):
        doc_obj, doc = self._save(doc_obj)
        # DynamoDB requires Decimal type instead of Float
        for key, value in doc.items():
            if type(value) == float:
                doc[key] = decimal.Decimal(str(value))
        return (doc_obj, doc)

    # CRUD Operations
    def save(self, doc_obj):
        doc_obj, doc = self.prepare_doc(doc_obj)
        try:
            self._dynamodb.put_item(Item=doc)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ResourceError('Table doesn\'t exist.')
        return doc_obj

    def bulk_save(self, doc_list):
        prep_doc_obj_list = []
        with self._dynamodb.batch_writer() as batch:
            for i in doc_list:
                doc_obj, doc = self.prepare_doc(i)
                prep_doc_obj_list.append(doc_obj)
                batch.put_item(Item=doc)
        return prep_doc_obj_list

    def prep_doc(self, doc_obj):
        """
        This method Validates, gets the Python value, checks unique indexes,
        gets the db value, and then returns the prepared doc dict object.
        Useful for save and backup functions.
        @param doc_obj:
        @return:
        """
        doc = doc_obj._data.copy()
        for key, prop in list(doc_obj._base_properties.items()):
            prop.validate(doc.get(key), key)
            raw_value = prop.get_python_value(doc.get(key))
            if prop.unique:
                self.check_unique(doc_obj, key, raw_value)
            value = prop.get_db_value(raw_value)
            doc[key] = value

        doc['_doc_type'] = get_doc_type(doc_obj.__class__)
        return doc

    def _save(self, doc_obj):
        doc = self.prep_doc(doc_obj)

        if '_id' not in doc:
            self.create_pk(doc_obj,doc)
            doc['_id'] = doc_obj._id
        return (doc_obj, doc)

    def get_id_list(self, filters_list):
        l = self.parse_filters(filters_list)
        if len(l) == 1:
            return self._dynamodb.smembers(l[0])
        else:
            return self._dynamodb.sinter(*l)

    def parse_filters(self, filters, doc_class):
        index_name = None
        filter_expression_list = []
        query_params = {}
        for idx, filter in enumerate(filters):
            prop_name, prop_value = filter.split(':')[3:5]
            if idx == 0:
                if prop_name != '_doc_type':
                    prop = doc_class()._base_properties[prop_name]
                    index_name = prop.kwargs.get(self.index_field_name, None) or \
                             self.default_index_name.format(prop_name)
                else:
                    index_name = self.default_index_name.format(prop_name)
                query_params['KeyConditionExpression'] = Key(prop_name).eq(prop_value)
            else:
                filter_expression_list.append(Attr(prop_name).eq(prop_value))
        if len(filter_expression_list) > 1:
            query_params['FilterExpression'] = And(*filter_expression_list)
        elif len(filter_expression_list) == 1:
            query_params['FilterExpression'] = filter_expression_list[0]
        if index_name != '_id':
            query_params['IndexName'] = index_name
        return query_params

    def evaluate(self, filters_list, doc_class):
        docs_list = self.get_doc_list(filters_list, doc_class)
        for doc in docs_list:
            yield doc_class(**doc)


    def create_table(self, doc_class):
        """
        Creates a table according to a table_config
        """
        pass

    # Indexing Methods
    def get_doc_list(self, filters_list, doc_class):
        result = []
        query_params = self.parse_filters(filters_list, doc_class)
        response = self._dynamodb.query(**query_params)
        result = response['Items']
        while 'LastEvaluatedKey' in response:
            query_params.update({'ExclusiveStartKey': response['LastEvaluatedKey']})
            response = self._dynamodb.query(**query_params)
            result.extend(response['Items'])
        return result

