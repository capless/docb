import json
import hashlib
import uuid
import datetime

from valley.exceptions import ValidationException
from kev.utils import get_doc_type
from kev.properties import IntegerProperty, FloatProperty, BooleanProperty


class DocDB(object):
    db_class = None
    indexer_class = None
    backend_id = None
    doc_id_string = '{doc_id}:id:{backend_id}:{class_name}'
    index_id_string = ''

    def save(self, doc_obj):
        raise NotImplementedError

    def delete(self, doc_obj):
        raise NotImplementedError

    def get(self, doc_obj, doc_id):
        raise NotImplementedError

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

    def get_id_list(self, filters_list, sortingp_list, doc_class):
        l = self.parse_filters(filters_list)
        if len(l) == 1:
            if len(sortingp_list) == 1:
                sp = sortingp_list[0]
                alphabetical = True
                prop = doc_class._base_properties.get(sp.key, None)
                if prop in [FloatProperty, IntegerProperty, BooleanProperty]:
                    alphabetical = False
                elif prop is None:
                    raise ValueError("Field '{0}' doesn't exists in a document".format(sp.key))
                return self._indexer.sort(l[0], alpha=alphabetical, by='*->{0}'.format(sp.key), desc=sp.reverse)
            elif len(sortingp_list) > 1:
                raise AttributeError("Redis doesn't support sorting on several fields at once.")
            else:
                return self._indexer.smembers(l[0])
        else:
            return self._indexer.sinter(*l)

    def parse_filters(self, filters):
        s = set()
        for f in filters:
            if '*' in f:
                s.update(self._indexer.scan_iter(f))
            else:
                s.add(f)

        if not s:
            return filters

        return list(s)
