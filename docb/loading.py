import boto3
import docb.document
import docb.properties
import docb.utils


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
                    'dynamodb',**db_info.get('config',{}))
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

    def build_cf_resource(self, resource_name, table_name, db_label):
        table_config = self.validate_table_config(db_label)
        global_indexes = self.get_index_names(db_label).items()
        return docb.utils.build_cf_resource(resource_name, table_name,
                                            table_config, global_indexes)

    def build_cf_template(self, resource_name, table_name, db_label):
        return docb.utils.build_cf_template(
            self.build_cf_resource(resource_name,table_name,db_label))
