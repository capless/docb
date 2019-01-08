import decimal
import os
import unittest
import datetime


from docb.testcase import (DocbTestCase, DynamoTestDocumentSlug, TestDocument, DynamoTestCustomIndex, Student)

from valley.exceptions import ValidationException


class DocumentTestCase(DocbTestCase):

    doc_class = TestDocument

    def test_default_values(self):
        obj = self.doc_class(name='Fred')
        self.assertEqual(obj.is_active, True)
        self.assertEqual(obj._data.get('is_active'), True)
        self.assertEqual(obj.date_created, datetime.date.today())
        self.assertEqual(obj._data.get('date_created'), datetime.date.today())
        self.assertEqual(type(obj.last_updated), datetime.datetime)
        self.assertEqual(type(obj._data.get('last_updated')), datetime.datetime)
        self.assertEqual(obj.no_subscriptions, 1)
        self.assertEqual(obj._data.get('no_subscriptions'), 1)
        self.assertEqual(obj.gpa,None)

    def test_get_unique_props(self):
        obj = DynamoTestDocumentSlug(name='Brian',slug='brian',email='brian@host.com',
                                 city='Greensboro',gpa=4.0)
        self.assertEqual(obj.get_unique_props().sort(),['name','slug','email'].sort())

    def test_set_indexed_prop(self):
        obj = DynamoTestDocumentSlug(name='Brian', slug='brian', email='brian@host.com',
                                 city='Greensboro', gpa=4.0)
        obj.name = 'Tariq'

    def test_validate_valid(self):
        t1 = self.doc_class(
            name='DNSly',
            is_active=False,
            no_subscriptions=2,
            gpa=3.5)
        t1.validate()

    def test_validate_boolean(self):
        t2 = self.doc_class(name='Google', is_active='Gone', gpa=4.0)
        with self.assertRaises(ValidationException) as vm:
            t2.validate()
        self.assertEqual(str(vm.exception),
                         'is_active: This value should be True or False.')

    def test_validate_datetime(self):
        t2 = self.doc_class(name='Google', gpa=4.0, last_updated='today')
        with self.assertRaises(ValidationException) as vm:
            t2.validate()
        self.assertEqual(str(vm.exception),
                         'last_updated: This value should be a valid datetime object.')

    def test_validate_date(self):
        t2 = self.doc_class(name='Google', gpa=4.0, date_created='today')
        with self.assertRaises(ValidationException) as vm:
            t2.validate()
        self.assertEqual(str(vm.exception),
                         'date_created: This value should be a valid date object.')

    def test_validate_integer(self):
        t2 = self.doc_class(name='Google', gpa=4.0, no_subscriptions='seven')
        with self.assertRaises(ValidationException) as vm:
            t2.validate()
        self.assertEqual(str(vm.exception),
                         'no_subscriptions: This value should be an integer')

    def test_validate_float(self):
        t2 = self.doc_class(name='Google', gpa='seven')
        with self.assertRaises(ValidationException) as vm:
            t2.validate()
        self.assertEqual(str(vm.exception),
                         'gpa: This value should be a float.')

    def test_validate_unique(self):
        t1 = TestDocument(name='Google', gpa=4.0)
        t1.save()
        t2 = TestDocument(name='Google', gpa=4.0)
        with self.assertRaises(ValidationException) as vm:
            t2.save()
        self.assertEqual(str(vm.exception),
                         'There is already a name with the value of Google')


class DynamoTestCase(DocbTestCase):

    doc_class = DynamoTestDocumentSlug

    def setUp(self):
        super(DynamoTestCase, self).setUp()
        self.t1 = self.doc_class(name='Goo and Sons', slug='goo-sons', gpa=3.2,
                                 email='goo@sons.com', city="Durham")
        self.t1.save()
        self.t2 = self.doc_class(name='Great Mountain', slug='great-mountain', gpa=3.2,
                                 email='great@mountain.com', city='Charlotte')
        self.t2.save()
        self.t3 = self.doc_class(name='Lakewood YMCA', slug='lakewood-ymca', gpa=3.2,
                                 email='lakewood@ymca.com', city='Durham')
        self.t3.save()

    def test_get(self):
        obj = self.doc_class.objects().get({'_id':self.t1._id})
        self.assertEqual(obj._id, self.t1._id)

    def test_flush_db(self):
        self.assertEqual(3, len(list(self.doc_class.objects().all())))
        self.doc_class().flush_db()
        self.assertEqual(0, len(list(self.doc_class.objects().all())))

    def test_delete(self):
        qs = self.doc_class.objects().filter({'city': 'Durham'})
        self.assertEqual(2, len(qs))
        qs[0].delete()
        qs = self.doc_class.objects().filter({'city': 'Durham'})
        self.assertEqual(1, len(qs))

    def test_all(self):
        docs = list(self.doc_class.objects().all())
        self.assertEqual(3, len(docs))
        for doc in docs:
            self.assertIn(doc.city, ['Durham', 'Charlotte'])

    def test_all_limit(self):
        docs = list(self.doc_class.objects().all(limit=2))
        self.assertEqual(2, len(docs))

    def test_non_unique_filter(self):
        qs = self.doc_class.objects().filter({'city': 'Durham'})
        self.assertEqual(2, qs.count())

    def test_objects_get_single_indexed_prop(self):
        obj = self.doc_class.objects().get({'name': self.t1.name})
        self.assertEqual(obj.slug, self.t1.slug)

    def test_queryset_chaining(self):
        qs = self.doc_class.objects().filter(
            {'name': 'Goo and Sons'}).filter({'city': 'Durham'})
        self.assertEqual(self.t1.name, qs[0].name)
        self.assertEqual(1, len(qs))

    def test_sort(self):
        qs = self.doc_class.objects().all(sort_attr='name')
        self.assertEqual('Goo and Sons', qs[0].name)
        qs = self.doc_class.objects().all(sort_attr='name', sort_reverse=True)
        self.assertEqual('Lakewood YMCA', qs[0].name)

    def test_filter_limit(self):
        qs = self.doc_class.objects().filter({'city': 'Durham'}, limit=2)
        self.assertEqual(2, len(qs))

    def test_local_backup(self):

        self.doc_class().backup('test-backup.json')
        dc = self.doc_class()
        self.assertEqual(3,
            len(dc.get_restore_json(*dc.get_path_type('test-backup.json'))))
        os.remove('test-backup.json')

    def test_local_restore(self):

        self.doc_class().backup('test-backup.json')
        self.doc_class().flush_db()
        self.assertEqual(len(list(self.doc_class.objects().all())),0)
        self.doc_class().restore('test-backup.json')
        self.assertEqual(len(list(self.doc_class.objects().all())), 3)
        os.remove('test-backup.json')


class ConditionsTestCase(DocbTestCase):

    doc_class = Student

    def setUp(self):
        super(ConditionsTestCase, self).setUp()
        self.t4 = self.doc_class(first_name='Brian', last_name='Jenkins', slug='brian-j', gpa=3.9,
                                 email='brian@docb.com', hometown="Durham", high_school='Jordan')
        self.t4.save()
        self.t5 = self.doc_class(first_name='George', last_name='Jenkins', slug='george-j', gpa=2.5,
                                 email='george@capless.com', hometown="Durham", high_school='Hillside')
        self.t5.save()
        self.t6 = self.doc_class(first_name='Katie', last_name='Hogans', slug='katie', gpa=2.2,
                                 email='katie@capless.com', hometown="Dayton", high_school='Southern')
        self.t6.save()
        self.t6 = self.doc_class(first_name='Kim', last_name='Hopkins', slug='kim', gpa=4.0,
                                 email='kim@autogy.com', hometown="Charlotte", high_school='Hillside')
        self.t6.save()
        self.t7 = self.doc_class(first_name='Joe', last_name='Rogans', slug='joe', gpa=3.0,
                                 email='joe@autogy.com', hometown="Pittsburgh", high_school='Riverside')
        self.t7.save()

    def test_contains(self):
        qs = self.doc_class.objects().filter({'hometown__contains':'Du'})
        self.assertEqual(2, len(qs))

    def test_begins_with(self):
        qs = self.doc_class.objects().filter({'first_name__begins':'K'})
        self.assertEqual(2, len(qs))

    def test_less_than(self):
        qs = self.doc_class.objects().filter({'gpa__lt': 3})
        self.assertEqual(2, len(qs))

    def test_less_than_equal(self):
        qs = self.doc_class.objects().filter({'gpa__lte': 3})
        self.assertEqual(3, len(qs))

    def test_greater_than(self):
        qs = self.doc_class.objects().filter({'gpa__gt': decimal.Decimal(2.5)})
        self.assertEqual(3, len(qs))

    def test_greater_than_equal(self):
        qs = self.doc_class.objects().filter({'gpa__gte': decimal.Decimal(2.5)})
        self.assertEqual(4, len(qs))

    def test_not_equal(self):
        qs = self.doc_class.objects().filter({'gpa__ne': decimal.Decimal(2.5)})
        self.assertEqual(4, len(qs))

    def test_in(self):
        qs = self.doc_class.objects().filter({'last_name__in': ('Rogans', 'Jenkins')})
        self.assertEqual(3, len(qs))

    def test_between(self):
        qs = self.doc_class.objects().filter({'gpa__between': (2, 3)})
        self.assertEqual(3, len(qs))

    def test_attr_exist(self):
        qs = self.doc_class.objects().filter({'country__attr_exists': True})
        self.assertEqual(0, len(qs))
        qs = self.doc_class.objects().filter({'gpa__attr_exists': True})
        self.assertEqual(5, len(qs))

    def test_not_attr_exist(self):
        qs = self.doc_class.objects().filter({'country__attr_not_exists': True})
        self.assertEqual(5, len(qs))
        qs = self.doc_class.objects().filter({'gpa__attr_not_exists': True})
        self.assertEqual(0, len(qs))

    def test_attr_type(self):
        qs = self.doc_class.objects().filter({'hometown__attr_type': 'S'})
        self.assertEqual(5, len(qs))
        qs = self.doc_class.objects().filter({'hometown__attr_type': 'N'})
        self.assertEqual(0, len(qs))
        qs = self.doc_class.objects().filter({'gpa__attr_type': 'N'})
        self.assertEqual(5, len(qs))


class DynamoIndexTestCase(DocbTestCase):
    doc_class = DynamoTestCustomIndex

    def setUp(self):
        super(DynamoIndexTestCase, self).setUp()
        self.db = self.doc_class.get_db()
        self.t1 = self.doc_class(name='Goo and Sons', slug='goo-sons', gpa=3.2,
                                 email='goo@sons.com', city="Durham")
        self.t1.save()

    def check_index(self, index_name, attr_name):
        index_schema = self.db.global_secondary_indexes
        detected = False
        index_info = {}
        for index in index_schema:
            if index['IndexName'] == index_name:
                index_info = index
                detected = True
        self.assertTrue(detected)
        self.assertEqual(index_info['KeySchema'][0]['AttributeName'], attr_name)
        return index_info


if __name__ == '__main__':
    unittest.main()
