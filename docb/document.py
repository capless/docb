import datetime
import decimal
import hashlib
import json
import uuid
from operator import itemgetter

import boto3
from urllib.parse import urlparse

from boto3.dynamodb.conditions import (Attr, And, Key, Equals, GreaterThan, LessThan, NotEquals, LessThanEquals,
                                       GreaterThanEquals, In, Between, BeginsWith, Contains, Size, AttributeType,
                                       AttributeExists, AttributeNotExists)
from botocore.exceptions import ClientError
from valley.declarative import DeclaredVars as DV, \
    DeclarativeVariablesMetaclass as DVM
from valley.exceptions import ValidationException
from valley.schema import BaseSchema

import docb.properties
import docb.utils
from docb.exceptions import ResourceError, QueryError, DocSaveError
from .query import QueryManager

CONDITIONS = {
    'eq': Equals,
    'ne': NotEquals,
    'lt': LessThan,
    'lte': LessThanEquals,
    'gt': GreaterThan,
    'gte': GreaterThanEquals,
    'in': In,
    'between': Between,
    'begins': BeginsWith,
    'contains': Contains,
    'attr_type': AttributeType,
    'attr_exists': AttributeExists,
    'attr_not_exists': AttributeNotExists
}


class AndX(And):
    expression_format = ' {operator} '

    def build_format(self):
        return '( ' + self.expression_format.join(['{}' for i in range(len(self._values))]) + ' )'

    def get_expression(self):
        return {'format': self.build_format(),
                'operator': self.expression_operator,
                'values': self._values}


class DeclaredVars(DV):
    base_field_class = docb.properties.BaseProperty
    base_field_type = '_base_properties'


class DeclarativeVariablesMetaclass(DVM):
    declared_vars_class = DeclaredVars


class BaseDocument(BaseSchema):
    """
    Base class for all Docb Documents classes.
    """
    BUILTIN_DOC_ATTRS = ('_id', '_doc_type')
    query_manager = QueryManager
    default_index_name = '{0}-index'
    doc_id_string = '{doc_id}:id:dynamodb:{class_name}'
    index_id_string = ''

    def __init__(self, **kwargs):
        self._data = self.process_schema_kwargs(kwargs)
        self._s3_cache = None
        self._create_error_dict = kwargs.get('create_error_dict') or self._create_error_dict
        if self._create_error_dict:
            self._errors = {}
        if '_id' in self._data:
            self._set_pk(self._data['_id'])

    def __repr__(self):
        return '<{class_name}: {uni}:{id}>'.format(
            class_name=self.__class__.__name__, uni=self.__unicode__(),
            id=self.pk)

    def __setattr__(self, name, value):
        if name in list(self._base_properties.keys()):
            self._data[name] = value
        else:
            super(BaseDocument, self).__setattr__(name, value)

    ############################
    # Connections              #
    ############################

    @property
    def _dynamodb(self):
        """
        Gets the Boto3 Dynamodb Table resource
        :return:
        """
        if self._dynamodb_cache is None:
            self._dynamodb_cache = self.Meta.handler._tables[self.Meta.use_db]
        return self._dynamodb_cache

    @property
    def _connection(self):
        """
        Gets the Boto3 Dynamodb Resource. Only used in unit tests
        :return:
        """
        if self._connection_cache is None:
            self._connection_cache = self.Meta.handler._connections[self.Meta.use_db]
        return self._connection_cache

    @property
    def _s3(self):
        """
        Creates a Boto3 S3 resource
        :return:
        """
        if self._s3_cache is None:
            self._s3_cache = boto3.resource('s3')
        return self._s3_cache

    ######################
    # Deployment         #
    ######################

    def build_cf_resource(self, resource_name, table_name):
        try:
            config = self.Meta.config
        except AttributeError:
            config = self.Meta.handler.config[self.Meta.use_db]['table_config']
        table_config = docb.utils.TableConfig(**config)
        table_config.validate()
        global_indexes = self._get_indexed_props_dict().items()
        return docb.utils.build_cf_resource(
            resource_name, table_name, table_config, global_indexes)

    def build_cf_template(self, resource_name, table_name):
        return docb.utils.build_cf_template(self.build_cf_resource(
            resource_name, table_name))

    def get_unique_props(self):
        unique_list = []
        for key, prop in list(self._base_properties.items()):
            if prop.unique:
                unique_list.append(key)
        return unique_list

    def check_all_unique(self):
        for key in self.get_unique_props():
            try:
                self.check_unique(self, key, self.cleaned_data.get(key))
            except ValidationException as e:
                if self._create_error_dict:
                    self._errors[key] = e.error_msg
                else:
                    raise e

    def get_type(self, property_class):
        property_type = type(property_class)
        property_to_dynamodb = {docb.properties.CharProperty: 'S',
                                docb.properties.SlugProperty: 'S',
                                docb.properties.EmailProperty: 'S',
                                docb.properties.IntegerProperty: 'N',
                                docb.properties.FloatProperty: 'N',
                                docb.properties.BooleanProperty: 'S',
                                docb.properties.DateProperty: 'S',
                                docb.properties.DateTimeProperty: 'S'}
        return property_to_dynamodb[property_type]

    def get_indexes(self):
        index_list = []
        for i in self._get_indexed_props():
            try:
                index_list.append(i)
            except KeyError:
                pass
        return index_list

    @classmethod
    def get_db(cls):
        raise NotImplementedError

    ##################
    # Queries        #
    ##################

    # Basic Operations
    def evaluate(self, filters_list):
        docs_list = self.get_doc_list(filters_list)
        for doc in docs_list:
            yield self.__class__(**doc)

    def flush_db(self):
        kwargs = {}
        while True:
            response = self._dynamodb.scan(**kwargs)
            for doc in response['Items']:
                self._dynamodb.delete_item(Key={'_id': doc['_id'],
                                                '_doc_type': doc['_doc_type']})
            if 'LastEvaluatedKey' not in response:
                break
            else:
                kwargs.update({'ExclusiveStartKey': response['LastEvaluatedKey']})

    def delete(self):
        self._dynamodb.delete_item(Key={'_id': self._data['_id'],
                                        '_doc_type': self._data['_doc_type']})

    @classmethod
    def get(cls, pk):
        c = cls()
        try:
            obj = c.__class__(**c._dynamodb.get_item(Key={'_id':c.get_doc_id(pk),'_doc_type': cls.__name__})['Item'])
        except KeyError:
            try:
                obj = c.__class__(
                    **c._dynamodb.get_item(Key={'_id': pk, '_doc_type': cls.__name__})['Item'])
            except KeyError:
                raise QueryError('No {} with the pk of {} found.'.format(cls.__name__, pk))
        return obj

    # CRUD Operations
    def save(self):
        doc = self.prep_doc()

        if '_id' not in doc:
            self.create_pk(doc)
            doc['_id'] = self._id

        for key, value in doc.items():
            if type(value) == float:
                doc[key] = decimal.Decimal(str(value))

        self._dynamodb.put_item(Item=doc)

        self._data = doc

    def bulk_save(self, doc_list):
        prep_doc_obj_list = []
        with self._dynamodb.batch_writer() as batch:
            for i in doc_list:
                doc = i.prep_doc(create_pk=True)
                prep_doc_obj_list.append(i)
                batch.put_item(Item=doc)
        return prep_doc_obj_list

    @classmethod
    def objects(cls):
        return cls.query_manager(cls)

    # Indexing Methods
    def get_doc_list(self, filters):
        query_params = self.build_query(filters)
        response = self._dynamodb.query(**query_params)
        result = response['Items']
        if filters.limit:
            while 'LastEvaluatedKey' in response and len(result) < filters.limit:
                result = self.get_more_docs(response, query_params, result)
        else:
            while 'LastEvaluatedKey' in response:
                result = self.get_more_docs(response, query_params, result)
        if filters.sort_attr:
            return sorted(result, key=itemgetter(filters.sort_attr), reverse=filters.sort_reverse)
        return result

    def get_more_docs(self, response, query_params, result):
        query_params.update(
            {'ExclusiveStartKey': response['LastEvaluatedKey']})
        response = self._dynamodb.query(**query_params)
        result.extend(response['Items'])
        return result

    def add_expressions(self, expressions):
        if len(expressions) > 1:
            return AndX(*expressions)
        elif len(expressions) == 1:
            return expressions[0]

    def get_condition(self, filter_key):
        condition_keys = CONDITIONS.keys()

        try:
            prop, cond = filter_key.split('__')
        except ValueError:
            prop = filter_key
            cond = 'eq'
        if cond not in condition_keys:
            raise QueryError('{} not a valid condition'.format(cond))
        cond = CONDITIONS[cond]

        return prop, cond

    def get_index_name(self, filters):
        """
        Returns the index name for the query. If the query is using the main hash and range keys the method will return
        "fuzzy". If it uses a Global Secondary Index it will return the name of that index.
        :param filters: QuerySet (docb.query.QuerySet) object.
        :return:
        """
        if not filters.global_index:
            return 'fuzzy', None, None
        if filters.index_name:
            name = self._get_indexed_props_dict()[filters.index_name]['name']
            return filters.index_name, name, filters.q[name]
        indexes = self.get_indexes()
        for k, v in filters.q.items():
            prop, cond = self.get_condition(k)
            prop_obj = self._base_properties.get(prop)
            if prop in indexes and issubclass(cond, Equals):
                return prop_obj.index_name or self.default_index_name.format(prop), prop, v
        raise QueryError('All gfilter queries must have a global secondary index that uses the Equals condition.')

    def build_query_params(self, filter_expressions, key_condition_expressions, index_name, limit=None):
        """
        Returns a dictionary that will be used as the keyword arguments for a query.
        :param filter_expressions: List of filter expressions (filter)
        :param key_condition_expressions: List of key expressions (filter)
        :param index_name: The index name we're using to query the DB
        :param limit: This value limits the number of records returned
        :return: query_params (dict)
        """
        query_params = dict()
        if len(filter_expressions) > 0:
            query_params['FilterExpression'] = self.add_expressions(filter_expressions)
        if len(key_condition_expressions) > 0:
            query_params['KeyConditionExpression'] = self.add_expressions(key_condition_expressions)
        if index_name not in ('_doc_type-index', '_id-index', 'fuzzy'):
            query_params['IndexName'] = index_name
        if isinstance(limit, (float, int, decimal.Decimal)):
            query_params['Limit'] = limit
        return query_params

    def build_query(self, filters):
        """
        Build the query
        :param filters: QuerySet object
        :return: Query dict
        """
        filters_dict = filters.q
        filter_expressions = list()
        key_condition_expressions = list()
        index_name, key_name, key_value = self.get_index_name(filters)

        if index_name == 'fuzzy':
            key_condition_expressions.append(CONDITIONS['eq'](Key('_doc_type'), filters_dict['_doc_type']))
            filters_dict.pop('_doc_type')
            prop_list = list(set(('_id', 'pk')) & filters_dict.keys())

            if len(prop_list) > 0:
                prop = '_id'
                prop_name = prop_list[0]
                if prop_name == '_id':
                    v = filters_dict[prop_name]
                if prop_name == 'pk':
                    v = self.get_doc_id(filters_dict[prop_name])
                key_condition_expressions.append(CONDITIONS['eq'](Key(prop), v))
                filters_dict.pop(prop_name)
        else:
            key_condition_expressions.append(CONDITIONS['eq'](Key(key_name), key_value))
            filters_dict.pop(key_name)

        for k, v in filters_dict.items():
            prop, cond = self.get_condition(k)
            if issubclass(cond, (Between,)):
                filter_expressions.append(cond(Attr(prop), *v))
            elif issubclass(cond, (AttributeNotExists, AttributeExists)):
                filter_expressions.append(cond(Attr(prop)))
            else:
                filter_expressions.append(cond(Attr(prop), v))
        return self.build_query_params(filter_expressions, key_condition_expressions, index_name, limit=filters.limit)

    #####################
    # Document Prep     #
    #####################

    @classmethod
    def get_doc_id(cls, id):
        return cls.doc_id_string.format(
            doc_id=id, backend_id='dynamodb', class_name=cls.get_class_name())

    def _get_short_id(self, doc_id):
        """
        Parses the long id to a shorter one
        :param doc_id: Long doc id
        :return: Short ID (string)
        """
        try:
            return doc_id.split(':')[0]
        except TypeError:
            return doc_id.decode().split(':')[0]

    def _set_pk(self, pk):
        """
        Sets the various with either the long or short ID
        :param pk: Long ID
        :return: None
        """
        self._data['_id'] = pk
        self._id = pk
        self.id = self._get_short_id(pk)
        self.pk = self.id

    def _get_indexed_props(self, index_type='global'):
        if index_type == 'global':
            index_list = ['_doc_type']
        else:
            index_list = []
        for key, prop in list(self._base_properties.items()):
            if index_type == 'global':
                if prop.global_index:
                    index_list.append(key)

        return index_list

    def _get_indexed_props_dict(self, index_type='global'):

        indexes = {}

        for key, prop in list(self._base_properties.items()):
            if index_type == 'global':
                if prop.global_index:
                    indexes[prop.index_name or self.default_index_name.format(key)] = {
                        'type': self.get_type(prop),
                        'name': key,
                        'key_type': prop.key_type
                    }

        return indexes

    def prep_doc(self, create_pk=False):
        """
        This method Validates, gets the Python value, checks unique indexes,
        gets the db value, and then returns the prepared doc dict object.
        Useful for save and backup functions.
        @return:
        """
        doc = self._data.copy()
        for key, prop in list(self._base_properties.items()):
            prop.validate(doc.get(key), key)
            v = doc.get(key)

            raw_value = prop.get_python_value(doc.get(key))
            if prop.unique:
                self.check_unique(key, raw_value)
            if v:
                value = prop.get_db_value(raw_value)
                doc[key] = value
            else:
                doc.pop(key)

        doc['_doc_type'] = docb.utils.get_doc_type(self.__class__)
        if create_pk:
            doc['_id'] = self.create_pk(doc, return_pk=True)
            for key, value in doc.items():
                if type(value) == float:
                    doc[key] = decimal.Decimal(str(value))
        return doc

    def check_unique(self, key, value):
        obj = self.objects().filter({key: value})
        if len(obj) == 0:
            return True
        if hasattr(self, '_id') and len(obj) == 1:
            if self._id == obj[0]._id:
                return True

        raise ValidationException(
            'There is already a {key} with the value of {value}'
                .format(key=key, value=value))

    @classmethod
    def get_class_name(cls):
        return cls.__name__

    def create_pk(self, doc, return_pk=False):
        doc = doc.copy()
        doc['_date'] = str(datetime.datetime.now())
        doc['_uuid'] = str(uuid.uuid4())
        hash_pk = hashlib.md5(bytes(json.dumps(doc), 'utf-8')).hexdigest()[:10]
        if return_pk:
            return self.doc_id_string.format(doc_id=hash_pk, backend_id='dynamodb', class_name=self.get_class_name())
        self._set_pk(self.doc_id_string.format(doc_id=hash_pk,
                                               backend_id='dynamodb', class_name=self.get_class_name()))

    def get_restore_json(self, restore_path, path_type, bucket=None):
        if path_type == 's3':
            return json.loads(self._s3.Object(
                bucket, restore_path).get().get('Body').read().decode())
        else:
            with open(restore_path) as f:
                return json.load(f)

    def get_path_type(self, path):
        if path.startswith('s3://'):
            result = urlparse(path)

            return (result.path[1:], 's3', result.netloc)
        else:
            return (path, 'local', None)

    def restore(self, restore_path):
        file_path, path_type, bucket = self.get_path_type(restore_path)
        docs = self.get_restore_json(file_path, path_type, bucket)
        for doc in docs:
            self.__class__(**doc).save()

    def remove_id(self, doc):
        doc._data.pop('_id')
        return doc

    ########################
    # Backup and Restore   #
    ########################

    def backup(self, export_path):
        file_path, path_type, bucket = self.get_path_type(export_path)
        json_docs = [doc.prep_doc() for doc in self.objects().all()]

        if path_type == 'local':
            with open(export_path, 'w+') as f:
                json.dump(json_docs, f)
        else:
            # Use tmp directory if we are uploading to S3 just in case we
            # are using Lambda
            self._s3.Object(bucket, file_path).put(
                Body=json.dumps(json_docs))

    ########################
    # Unit Tests           #
    ########################

    def create_table(self):
        """
        Creates a table according to a table_config. Please only use
        for unit tests. Please use the build_cf_template and build_cf_resources
        otherwise.
        """
        try:
            config = self.Meta.config
        except AttributeError:
            config = self.Meta.handler.get_config(self.Meta.use_db)

        table_config = docb.utils.TableConfig(**config)
        table_config.validate()

        global_indexes = self._get_indexed_props_dict().items()

        connection = docb.utils.TableConnection(
            **self.Meta.handler.config[
                self.Meta.use_db]['connection'])

        return self._connection.create_table(**docb.utils.build_cf_args(connection.table, table_config,
                                                                        global_indexes))

    def delete_table(self):
        self._dynamodb.delete()

    class Meta:
        use_db = 'default'
        handler = None
        config = None


class Document(BaseDocument, metaclass=DeclarativeVariablesMetaclass):

    @classmethod
    def get_db(cls):
        return cls.Meta.handler.get_db(cls.Meta.use_db)
