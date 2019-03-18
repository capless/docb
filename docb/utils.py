import sys
import importlib
import envs as e
import sammy as sm
import valley


BILLING_MODE_CHOICES = {
    'PROVISIONED':'PROVISIONED',
    'PAY_PER_REQUEST':'PAY_PER_REQUEST'
}

STREAM_VIEW_TYPE = {
    'KEYS_ONLY': 'KEYS_ONLY',
    'NEW_IMAGE': 'NEW_IMAGE',
    'OLD_IMAGE': 'OLD_IMAGE',
    'NEW_AND_OLD_IMAGES': 'NEW_AND_OLD_IMAGES'
}

SSE_TYPE_CHOICES = {
    'AES256': 'AES256',
    'KMS': 'KMS'
}


class TableConfig(valley.contrib.Schema):
    billing_mode = valley.CharProperty(required=True, default_value='PROVISIONED', choices=BILLING_MODE_CHOICES)
    write_capacity = valley.IntegerProperty()
    read_capacity = valley.IntegerProperty()
    secondary_write_capacity = valley.IntegerProperty()
    secondary_read_capacity = valley.IntegerProperty()
    autoscaling = valley.BooleanProperty()
    stream_enabled = valley.BooleanProperty()
    stream_view_type = valley.CharProperty(default_value='NEW_AND_OLD_IMAGES', choices=STREAM_VIEW_TYPE)
    sse_enabled = valley.BooleanProperty()
    sse_type = valley.CharProperty(default_value='KMS', choices=SSE_TYPE_CHOICES)
    kms_master_key_id = valley.CharProperty()


class TableConnection(valley.contrib.Schema):
    table = valley.CharProperty(required=True)
    endpoint_url = valley.CharProperty()


def import_mod(imp):
    '''
    Lazily imports a module from a string
    @param imp:
    '''
    __import__(imp, globals(), locals())
    return sys.modules[imp]


def import_util(imp):
    '''
    Lazily imports a utils (class,
    function,or variable) from a module) from
    a string.
    @param imp:
    '''

    mod_name, obj_name = imp.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, obj_name)


def get_doc_type(klass):
    if hasattr(klass.Meta, 'doc_type'):
        if klass.Meta.doc_type is not None:
            return klass.Meta.doc_type
    return klass.__name__


def get_db_kwargs():
    kwargs = dict()
    endpoint_url  = e.env('DYNAMODB_ENDPOINT_URL')
    if endpoint_url:
        kwargs['endpoint_url'] = endpoint_url
    return kwargs


def build_cf_args(table_name, table_config, global_indexes, resource_name=None):
    attr_defs = [
        {'AttributeName': v['name'], 'AttributeType': v['type']}
        for k, v in global_indexes]

    attr_defs.append({'AttributeName': '_id', 'AttributeType': 'S'})
    attr_defs.append({'AttributeName': '_doc_type', 'AttributeType': 'S'})

    args = {
        'TableName':table_name,
        'KeySchema':[{'AttributeName': '_doc_type', 'KeyType': 'HASH'},
                   {'AttributeName': '_id', 'KeyType': 'RANGE'}],
        'AttributeDefinitions':attr_defs,
        'BillingMode': table_config.billing_mode
    }
    if table_config.billing_mode == 'PROVISIONED':
        args['ProvisionedThroughput'] = {
            'ReadCapacityUnits': table_config.read_capacity,
            'WriteCapacityUnits': table_config.write_capacity
        }

    if table_config.sse_enabled:
        args['SSESpecification'] = {
            'Enabled': True,
            'SSEType': table_config.sse_type,
        }
        if table_config.kms_master_key_id:
            args['SSESpecification']['KMSMasterKeyId'] = table_config.kms_master_key_id

    if table_config.stream_enabled:
        args['StreamSpecification'] = {
            'StreamViewType': table_config.stream_view_type
        }
    if len(global_indexes) > 0:
        gi = []
        for k, v in global_indexes:
            gic = {
                'IndexName': k, 'KeySchema': [
                {'AttributeName': v['name'], 'KeyType': v['key_type']}],
                'Projection': {'ProjectionType': 'ALL'},
            }
            if table_config.billing_mode == 'PROVISIONED':
                gic['ProvisionedThroughput'] = {
                    'ReadCapacityUnits': table_config.read_capacity,
                    'WriteCapacityUnits': table_config.read_capacity
                }
            gi.append(gic)
        args['GlobalSecondaryIndexes'] = gi

    if resource_name:
        args['name'] = resource_name
    return args


def build_cf_resource(resource_name, table_name, table_config, global_indexes):
    return sm.DynamoDBTable(
        **build_cf_args(table_name, table_config, global_indexes, resource_name)
    )


def build_cf_template(db_resource):
    tmpl = sm.CFT(render_type='yaml')
    tmpl.add_resource(db_resource)
    return tmpl
