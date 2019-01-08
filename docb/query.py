from statistics import mean

from .exceptions import QueryError

REPR_OUTPUT_SIZE = 20


def create_list(a):
    if isinstance(a, (set, tuple, list)):
        a = list(a)
    else:
        a = [a]
    return a


def combine_list(a, b):
    a = create_list(a)
    b = create_list(b)
    a.extend(b)
    return a


def combine_dicts(a, b, op=combine_list):
    z = a.copy()
    z.update(b)
    z.update([(k, op(a[k], b[k])) for k in set(b) & set(a)])
    doc_type = z.get('_doc_type')
    if isinstance(doc_type, list):
        doc_type = set(doc_type)
        if len(doc_type) == 1:
            doc_type = tuple(doc_type)[0]
            z['_doc_type'] = doc_type
    return z


class QuerySetMixin(object):
    query_type = None

    def __init__(self, doc_class, q=None, parent_q=None, global_index=False, index_name=None, sort_attr=None,
                 sort_reverse=False, limit=None):
        self.parent_q = parent_q
        self._result_cache = None
        self._doc_class = doc_class
        self.q = q
        self.sort_attr = sort_attr
        self.sort_reverse = sort_reverse
        self.limit = limit
        self.global_index = global_index
        self.index_name = index_name
        self.evaluated = False
        if q and parent_q:
            self.q = self.combine_qs()

    def combine_qs(self):
        return combine_dicts(self.parent_q, self.q)

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __repr__(self):  # pragma: no cover
        data = list(self[:REPR_OUTPUT_SIZE + 1])
        if len(data) > REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."
        return repr(data)

    def __iter__(self):
        self._fetch_all()
        return iter(self._result_cache)

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self.evaluate())

    def count(self):
        return len(list(self.evaluate()))

    def attr_list(self, attr):
        self._doc_class._base_properties[attr]
        return [getattr(i, attr) for i in self.evaluate()]

    def mean(self, attr):
        return mean(self.attr_list(attr))

    def sum(self, attr):
        return sum(self.attr_list(attr))

    def __bool__(self):
        self._fetch_all()
        return bool(self._result_cache)

    def __getitem__(self, index):
        if self._result_cache is not None:
            return self._result_cache[index]
        else:
            self._fetch_all()
            return self._result_cache[index]

    def evaluate(self):
        raise NotImplementedError


class QuerySet(QuerySetMixin):

    def filter(self, q, sort_attr=None, sort_reverse=False, limit=None):
        q.update({'_doc_type': self._doc_class.__name__})
        return QuerySet(self._doc_class, q, self.q, sort_attr=sort_attr, sort_reverse=sort_reverse, limit=limit)

    def gfilter(self, q, index_name=None, sort_attr=None, sort_reverse=False, limit=None):
        return QuerySet(self._doc_class, q, self.q, global_index=True, index_name=index_name, sort_attr=sort_attr,
                        sort_reverse=sort_reverse, limit=limit)

    def get(self, q):
        q.update({'_doc_type': self._doc_class.__name__})
        qs = QuerySet(self._doc_class, q, self.q)
        if len(qs) > 1:
            raise QueryError(
                'This query should return exactly ' \
                'one result. Your query returned {0}'.format(
                    len(qs)))
        if len(qs) == 0:
            raise QueryError('This query did not return a result.')
        return qs[0]

    def all(self, sort_attr=None, sort_reverse=False, limit=None):
        return QuerySet(self._doc_class,
                        {'_doc_type': self._doc_class.__name__}, self.q, sort_attr=sort_attr,
                        sort_reverse=sort_reverse, limit=limit)

    def evaluate(self):
        return self._doc_class().evaluate(self)


class QueryManager(object):

    def __init__(self, cls):
        self._doc_class = cls

        self.filter = QuerySet(self._doc_class).filter
        self.gfilter = QuerySet(self._doc_class).gfilter
        self.get = QuerySet(self._doc_class).get
        self.all = QuerySet(self._doc_class).all
