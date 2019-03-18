import time

import boto3
import docb.document
import docb.properties
import docb.utils

REPLICATION_GROUPS = [
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2',
    'ap-southeast-1',
    'eu-west-1'
]


class DocbHandler(object):
    """
    Example:
    handler = DocbHandler({
        'dynamodb':{
            'connection':{
                'table':'testlocal'
            },
            'documents':['docb.testcase.BaseTestDocumentSlug','docb.testcase.DynamoTestCustomIndex'],
            'config':{
                  'endpoint_url':'http://localhost:8000'
                },
            'table_config':{
                'write_capacity':2,
                'read_capacity':3
            }
        }
    })
    """

    def __init__(self, config):
        self.config = config
        self.get_tables()

    def get_tables(self):
        try:
            return self._tables
        except AttributeError:
            self._tables = dict()
            for db_label, conn in self.get_connections().items():
                self._tables[db_label] = conn.Table(self.config[db_label]['connection']['table'])
            return self._tables

    def get_connections(self):
        try:
            return self._connections
        except AttributeError:
            self._connections = dict()
            for db_label, db_info in self.config.items():
                self._connections[db_label] = boto3.resource(
                    'dynamodb', **db_info.get('config', {}))
            return self._connections

    def get_db(self, db_label):
        return self.get_settings(db_label)

    def get_config(self, db_label):
        return self.get_settings(db_label).get('table_config')

    def get_settings(self, db_label):
        return self.config[db_label]

    def get_connection_info(self, db_label):
        return self.get_settings(db_label).get('connection_info')

    def get_documents_by_label(self, label):
        doc_string_list = self.config[label]['documents']
        doc_list = []
        for i in doc_string_list:
            doc_list.append(docb.utils.import_util(i))
        return doc_list

    def get_index_names(self, db_label, index_type='global'):
        indexes = dict()
        for i in self.get_documents_by_label(db_label):
            indexes.update(i()._get_indexed_props_dict(index_type))
        return indexes

    def validate_table_config(self, db_label):
        tc = docb.utils.TableConfig(**self.config[db_label]['table_config'])
        tc.validate()
        return tc

    def validate_table_connection(self, conn):
        tc = docb.utils.TableConnection(**conn)
        tc.validate()
        return tc

    def build_cf_resource(self, resource_name, table_name, db_label, global_table=False):
        table_config = self.validate_table_config(db_label)
        if global_table:
            table_config.stream_enabled = True
        global_indexes = self.get_index_names(db_label).items()
        return docb.utils.build_cf_resource(resource_name, table_name,
                                            table_config, global_indexes)

    def build_cf_template(self, resource_name, table_name, db_label, global_table=False):
        return docb.utils.build_cf_template(
            self.build_cf_resource(resource_name, table_name, db_label, global_table))

    def publish(self, stack_name, resource_name, table_name, db_label):
        sam = self.build_cf_template(resource_name, table_name, db_label)
        sam.publish(stack_name)

    def publish_global(self, stackset_name, resource_name, table_name, db_label, replication_groups=REPLICATION_GROUPS,
                       profile_name='default'):
        """
        Publishes the database in multiple regions via CloudFormation StackSets and creates an DynamoDB Global Table.
        :param stackset_name: Desired CloudFormation StackSets
        :param resource_name: Desired name of the DynamoDB Table in the CloudFormation Template
        :param table_name: Desired name for the actual DynamoDB table
        :param db_label: Name of the DB label in this DocbHandler that you want to deploy
        :param replication_groups: List of AWS region short names that you want to deploy to in the CloudFormation
        :param profile_name: AWS credentials set to use from the ~/.aws/credentials file
        Stackset
        :return: None
        """
        start_time = time.perf_counter()
        sam = self.build_cf_template(resource_name, table_name, db_label, global_table=True)
        sam.build_clients_resources(profile_name=profile_name)
        sam.publish_global(stackset_name, replication_groups)

        # Create Global Table
        print('Creating global table.')
        sess = boto3.Session(profile_name=profile_name)

        dyndb = sess.client('dynamodb')
        dyndb.create_global_table(
            GlobalTableName=table_name,
            ReplicationGroup=[
                {'RegionName': i}
                for i in replication_groups
            ]
        )
        end_time = time.perf_counter()
        print('Total Elapsed Time: {}'.format(end_time - start_time))
