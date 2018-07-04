import decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr, And
from botocore.exceptions import ClientError

from ...backends import DocDB
from ...exceptions import DocNotFoundError, ResourceError, ImproperlyConfigured
from ... import properties


class DynamoDB(DocDB):

    db_class = boto3
    backend_id = 'dynamodb'
    default_index_name = '{0}-index'
    index_field_name = 'index_name'

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._boto3_session_cache = None
        self._boto3_session
        self._dynamodb_cache = None
        self._indexer = self._dynamodb

    @property
    def _dynamodb(self):
        if self._dynamodb_cache is None:
            self._dynamodb_cache = self.db_class.resource(
                'dynamodb', endpoint_url=self._kwargs.get('endpoint_url', None))\
                .Table(self._kwargs['table'])
        return self._dynamodb_cache

    @property
    def _boto3_session(self):
        if self._boto3_session_cache is None:
            if 'aws_secret_access_key' in self._kwargs and 'aws_access_key_id' in self._kwargs:
                self._boto3_session_cache = boto3.Session(
                    aws_secret_access_key=self._kwargs['aws_secret_access_key'],
                    aws_access_key_id=self._kwargs['aws_access_key_id'])
        return self._boto3_session_cache

    # CRUD Operations
    def save(self, doc_obj):
        doc_obj, doc = self._save(doc_obj)
        # DynamoDB requires Decimal type instead of Float
        for key, value in doc.items():
            if type(value) == float:
                doc[key] = decimal.Decimal(str(value))
        try:
            self._indexer.put_item(Item=doc)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ResourceError('Table doesn\'t exist.')
        return doc_obj

    def delete(self, doc_obj):
        self._indexer.delete_item(Key={'_id': doc_obj._data['_id']})

    def all(self, cls, skip, limit):
        kwargs = {}
        if limit is not None:
            kwargs.update({'Limit': limit})
        while True:
            response = self._indexer.scan(**kwargs)
            for doc in response['Items']:
                if skip and skip > 0:
                    skip -= 1
                    continue
                yield cls(**doc)
            if 'LastEvaluatedKey' not in response:
                break
            else:
                if limit is not None and response['Count'] == limit:
                    break
                elif limit is not None:
                    limit = limit - response['Count']
                    kwargs.update({'Limit': limit})
                kwargs.update({'ExclusiveStartKey': response['LastEvaluatedKey']})

    def get(self, doc_obj, doc_id):
        response = self._indexer.get_item(Key={'_id': doc_obj.get_doc_id(doc_id)})
        doc = response.get('Item', None)
        if not doc:
            raise DocNotFoundError
        return doc_obj(**doc)

    def flush_db(self):
        kwargs = {}
        while True:
            response = self._indexer.scan(**kwargs)
            for doc in response['Items']:
                self._indexer.delete_item(Key={'_id': doc['_id']})
            if 'LastEvaluatedKey' not in response:
                break
            else:
                kwargs.update({'ExclusiveStartKey': response['LastEvaluatedKey']})

    def create_table(self, doc_class):
        """
        Creates a table according to a table_config
        """
        if getattr(doc_class.Meta, 'table_config', None):
            raise ImproperlyConfigured("'table_config' is missing")
        table_config = TableConfig(doc_class.Meta.table_config, self.table, doc_class)
        self._db.create_table(**table_config.parse_config())

    # Indexing Methods
    def get_doc_list(self, filters_list, doc_class):
        result = []
        query_params = self.parse_filters(filters_list, doc_class)
        response = self._indexer.query(**query_params)
        result = response['Items']
        while 'LastEvaluatedKey' in response:
            query_params.update({'ExclusiveStartKey': response['LastEvaluatedKey']})
            response = self._indexer.query(**query_params)
            result.extend(response['Items'])
        return result

    def parse_filters(self, filters, doc_class):
        index_name = None
        filter_expression_list = []
        query_params = {}
        for idx, filter in enumerate(filters):
            prop_name, prop_value = filter.split(':')[3:5]
            if idx == 0:
                prop = doc_class()._base_properties[prop_name]
                index_name = prop.kwargs.get(self.index_field_name, None) or \
                             self.default_index_name.format(prop_name)
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


class TableConfig(object):
    rcu_name = 'read_capacity'
    wcu_name = 'write_capacity'
    hash_key_name = 'hash_key'
    sort_key_name = 'sort_key'
    secondary_indexes_name = 'secondary_indexes'

    def __init__(self, table_config, table_name, doc_class):
        self.table_config = table_config
        self.table_name = table_name
        self.doc_class = doc_class

    def parse_config(self):
        key_schema = self.get_key_schema(self.table_config)
        provisioned_throughput = self.get_provisioned_throughput(self.table_config)
        return {'TableName': self.table_name, 'KeySchema': key_schema,
                'ProvisionedThroughput': provisioned_throughput,
                'AttributeDefinitions': self.get_attribute_definitions(),
                'GlobalSecondaryIndexes': self.get_secondary_indexes()}

    def get_key_schema(self, obj):
        hash_key, sort_key = [obj.get(param, None) for param in
                              [self.hash_key_name, self.sort_key_name]]
        key_schema = []
        if hash_key:
            key_schema.append({'AttributeName': hash_key, 'KeyType': 'HASH'})
        else:
            raise ImproperlyConfigured("'%s' value is missing" % self.hash_key_name)
        if sort_key:
            key_schema.append({'AttributeName': sort_key, 'KeyType': 'RANGE'})
        return key_schema

    def get_provisioned_throughput(self, obj):
        rcu, wcu = [obj.get(param, None) for param in [self.rcu_name, self.wcu_name]]
        if rcu is None or wcu is None:
            raise ImproperlyConfigured("Both '%s' and '%s' should be provided." %
                                       (self.rcu_name, self.wcu_name))
        return {'ReadCapacityUnits': rcu,
                'WriteCapacityUnits': wcu}

    def get_attribute_definitions(self):
        attributes_dict = {}
        definitions = []
        hash_key, sort_key = [self.table_config.get(param, None) for param in
                              [self.hash_key_name, self.sort_key_name]]
        if hash_key:
            attributes_dict.update({hash_key: self.get_type(hash_key)})
        if sort_key:
            attributes_dict.update({sort_key: self.get_type(sort_key)})
        secondary_indexes = self.table_config.get(self.secondary_indexes_name, None)
        for index in secondary_indexes:
            hash_key, sort_key = [secondary_indexes[index].get(param, None) for param in
                                  [self.hash_key_name, self.sort_key_name]]
            if hash_key:
                attributes_dict.update({hash_key: self.get_type(hash_key)})
            else:
                raise ImproperlyConfigured("'%s' value is missing" % self.hash_key_name)
            if sort_key:
                attributes_dict.update({sort_key: self.get_type(sort_key)})
        for prop_name, prop_type in attributes_dict.items():
            definitions.append({'AttributeName': prop_name,
                                'AttributeType': prop_type})
        return definitions

    def get_secondary_indexes(self):
        secondary_indexes = self.table_config.get(self.secondary_indexes_name, None)
        indexes_schema = []
        for index_name in secondary_indexes:
            root_obj = secondary_indexes[index_name]
            index_key_schema = self.get_key_schema(root_obj)
            indexes_schema.append({'IndexName': index_name, 'Projection': {'ProjectionType': 'ALL'},
                                   'ProvisionedThroughput': self.get_provisioned_throughput(root_obj),
                                   'KeySchema': index_key_schema})
        return indexes_schema

    def get_type(self, property_name):
        if property_name == '_id':
            return 'S'
        property_to_dynamodb = {properties.CharProperty: 'S',
                                properties.SlugProperty: 'S',
                                properties.EmailProperty: 'S',
                                properties.IntegerProperty: 'N',
                                properties.FloatProperty: 'N',
                                properties.BooleanProperty: 'S',
                                properties.DateProperty: 'S',
                                properties.DateTimeProperty: 'S'}
        property_class = self.doc_class._base_properties.get(property_name, None).__class__
        return property_to_dynamodb[property_class]
