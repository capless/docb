import sys
import importlib
import sammy as sm
import valley


class TableConfig(valley.contrib.Schema):
    write_capacity = valley.IntegerProperty(required=True)
    read_capacity = valley.IntegerProperty(required=True)
    secondary_write_capacity = valley.IntegerProperty()
    secondary_read_capacity = valley.IntegerProperty()
    autoscaling = valley.BooleanProperty()


class TableConnection(valley.contrib.Schema):
    pass


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


def build_cf_resource(resource_name,table_name,table_config,indexes):
    attr_defs = [
        {'AttributeName': v['name'], 'AttributeType': v['type']}
        for k, v in indexes]
    attr_defs.append({'AttributeName': '_id', 'AttributeType': 'S'})
    return sm.DynamoDBTable(
        name=resource_name,
        TableName=table_name,
        KeySchema=[{'AttributeName': '_id', 'KeyType': 'HASH'},
                   {'AttributeName': '_doc_type', 'KeyType': 'RANGE'}],
        GlobalSecondaryIndexes=[
            {
                'IndexName': k, 'KeySchema': [
                {'AttributeName': v['name'], 'KeyType': v['key_type']}],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': table_config.secondary_read_capacity,
                    'WriteCapacityUnits': table_config.secondary_write_capacity}
            }
            for k, v in indexes
        ],
        AttributeDefinitions=attr_defs,
        ProvisionedThroughput={
            'ReadCapacityUnits': table_config.read_capacity,
            'WriteCapacityUnits': table_config.write_capacity
        }
    )


def build_cf_template(db_resource):
    tmpl = sm.SAM(render_type='yaml')
    tmpl.add_resource(db_resource)
    return tmpl