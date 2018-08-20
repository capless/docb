import valley
import sammy as sm
import docb.document
import docb.properties
import docb.utils




class DocbHandler(object):

    def __init__(self, databases):
        # Created for get_db method
        self._databases = dict()
        self._connections = dict()
        self._labels = list()
        self.doc_list = dict()
        for db_label, db_info in databases.items():
            db_klass = valley.utils.import_util(db_info.get('backend'))
            self._databases[db_label] = dict()
            self._databases[db_label]['connection'] = db_klass(**db_info.get('connection'))
            self._databases[db_label]['config'] = db_info.get('config')
            self.doc_list[db_label] = list()

    def get_db(self, db_label):
        return self._databases.get(db_label).get('connection')

    def get_table_config(self, db_label):
        return self._databases.get(db_label).get('config')

    def add_docs(self,docs,db_label):
        if isinstance(docs,docb.document.Document):
            self.doc_list[db_label].append(docs)
        elif isinstance(docs,(set,list,tuple)):
            self.doc_list[db_label].extend(docs)

    def get_index_names(self,db_label):
        indexes = dict()
        for i in self.doc_list[db_label]:
            indexes.update(i().get_indexed_props_dict())
        return indexes

    def validate_table_config(self,db_label):
        tc = docb.utils.TableConfig(**self._databases[db_label]['config'])
        tc.validate()
        return tc

    def build_cf_resource(self,resource_name,table_name,db_label):
        table_config = self.validate_table_config(db_label)
        indexes = self.get_index_names(db_label).items()
        return docb.utils.build_cf_resource(resource_name,table_name,
                                            table_config,indexes)

    def build_cf_template(self,resource_name,table_name,db_label):
        return docb.utils.build_cf_template(resource_name,table_name,
                                            self.build_cf_resource(db_label))
