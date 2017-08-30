import boto3
import json
import redis

from kev.backends.redis.db import RedisDB
from kev.exceptions import QueryError


class S3RedisDB(RedisDB):

    db_class = boto3.resource
    indexer_class = redis.StrictRedis
    backend_id = 's3redis'

    def __init__(self,**kwargs):

        if 'aws_secret_access_key' in kwargs and 'aws_access_key_id' in kwargs:
            boto3.Session(aws_secret_access_key=kwargs['aws_secret_access_key'],
                aws_access_key_id=kwargs['aws_access_key_id'])
        self._db = boto3.resource('s3')
        self.bucket = kwargs['bucket']

        self._indexer = self.indexer_class(**kwargs['indexer'])

    #CRUD Operation Methods

    def save(self,doc_obj):
        doc_obj, doc = self._save(doc_obj)

        self._db.Object(self.bucket, doc_obj._id).put(
                Body=json.dumps(doc))
        pipe = self._indexer.pipeline()
        pipe = self.add_to_model_set(doc_obj, pipe)
        pipe = self.add_indexes(doc_obj, doc, pipe)
        pipe = self.remove_indexes(doc_obj, pipe)
        pipe.execute()

        return doc_obj

    def get(self,doc_class,doc_id):
        doc = json.loads(self._db.Object(
                self.bucket, doc_class.get_doc_id(
                doc_id)).get().get('Body').read().decode())
        return doc_class(**doc)

    def flush_db(self):
        self._indexer.flushdb()
        obj_list = self._db.Bucket(self.bucket).objects.all()
        for i in obj_list:
            i.delete()

    def delete(self, doc_obj):
        self._db.Object(self.bucket,doc_obj._id).delete()
        pipe = self._indexer.pipeline()
        pipe = self.remove_from_model_set(doc_obj, pipe)
        doc_obj._index_change_list = doc_obj.get_indexes()
        pipe = self.remove_indexes(doc_obj, pipe)
        pipe.execute()

    def all(self, doc_class, skip, limit):
        id_list = [self.parse_id(id) for id in self._indexer.smembers(
            '{0}:all'.format(
            doc_class.get_class_name()))]
        for id in id_list:
            if skip and skip > 0:
                skip -= 1
                continue
            if limit is not None and limit == 0:
                break
            elif limit:
                limit -= 1
            yield self.get(doc_class,id)

    def evaluate(self, filters_list, sortingp_list, doc_class):
        id_list = self.get_id_list(filters_list, sortingp_list, doc_class)
        if len(sortingp_list) > 0:
            docs_list = [doc_class.get(self.parse_id(id)) for id in id_list]
            sorted_list = self.sort(sortingp_list, docs_list, doc_class)
            for doc in sorted_list:
                yield doc
        else:
            for id in id_list:
                yield doc_class.get(self.parse_id(id))
