# Docb
Python ORM for DynamoDB
[![Build Status](https://travis-ci.org/capless/docb.svg?branch=master)](https://travis-ci.org/capless/docb)

## Python Versions

Docb should work on Python 3.5+ and higher

## Install
```
pip install docb
```

## Example Usage

### Setup the Connection
**Example:** loading.py
```python
from docb.loading import DocbHandler


docb_handler = DocbHandler({
    'dynamodb': {
        'backend': 'docb.backends.dynamodb.db.DynamoDB',
        'connection': {
            'table': 'your-dynamodb-table',
        }
    }
})
```
### Setup the Models
**Example:** models.py
```python
from docb import (Document,CharProperty,DateTimeProperty,
                 DateProperty,BooleanProperty,IntegerProperty,
                 FloatProperty)
from .loading import docb_handler

class TestDocument(Document):
    name = CharProperty(required=True,unique=True,min_length=3,max_length=20)
    last_updated = DateTimeProperty(auto_now=True)
    date_created = DateProperty(auto_now_add=True)
    is_active = BooleanProperty(default_value=True,index=True)
    city = CharProperty(required=False,max_length=50)
    state = CharProperty(required=True,index=True,max_length=50)
    no_subscriptions = IntegerProperty(default_value=1,index=True,min_value=1,max_value=20)
    gpa = FloatProperty()

    def __unicode__(self):
        return self.name
        

    class Meta:
        use_db = 'dynamodb'
        handler = docb_handler

```

### Use the model
#### How to Save a Document
```python
>>>from .models import TestDocument

>>>kevin = TestDocument(name='Kev',is_active=True,no_subscriptions=3,state='NC',gpa=3.25)

>>>kevin.save()

>>>kevin.name
'Kev'

>>>kevin.is_active
True

>>>kevin.pk
ec640abfd6

>>>kevin.id
ec640abfd6

>>>kevin._id
'ec640abfd6:id:s3redis:testdocument'
```
#### Query Documents

##### First Save Some More Docs
```python

>>>george = TestDocument(name='George',is_active=True,no_subscriptions=3,gpa=3.25,state='VA')

>>>george.save()

>>>sally = TestDocument(name='Sally',is_active=False,no_subscriptions=6,gpa=3.0,state='VA')

>>>sally.save()
```
##### Show all Documents
```python
>>>TestDocument.all()

[<TestDocument: Kev:ec640abfd6>,<TestDocument: George:aff7bcfb56>,<TestDocument: Sally:c38a77cfe4>]

>>>TestDocument.all(skip=1)

[<TestDocument: George:aff7bcfb56>,<TestDocument: Sally:c38a77cfe4>]

>>>TestDocument.all(limit=2)

[<TestDocument: Kev:ec640abfd6>,<TestDocument: George:aff7bcfb56>]

```
##### Get One Document
```python
>>>TestDocument.get('ec640abfd6')
<TestDocument: Kev:ec640abfd6>

>>>TestDocument.objects().get({'state':'NC'})
<TestDocument: Kev:ec640abfd6>

```
##### Filter Documents
```python
>>>TestDocument.objects().filter({'state':'VA'})

[<TestDocument: George:aff7bcfb56>,<TestDocument: Sally:c38a77cfe4>]

>>>TestDocument.objects().filter({'no_subscriptions':3})
[<TestDocument: Kev:ec640abfd6>,<TestDocument: George:aff7bcfb56>]

>>>TestDocument.objects().filter({'no_subscriptions':3,'state':'NC'})
[<TestDocument: Kev:ec640abfd6>]
```
##### Chain Filters
The chain filters feature is only available for Redis and S3/Redis backends.
```python
>>>TestDocument.objects().filter({'no_subscriptions':3}).filter({'state':'NC'})
[<TestDocument: Kev:ec640abfd6>]

```

### DynamoDB setup
#### Create a table
* **Table name** should be between 3 and 255 characters long. (A-Z,a-z,0-9,_,-,.)
* **Primary key** (partition key) should be equal to `_id`

#### Filter Documents
If you want to make `filter()` queries, you should create an index for every attribute that you want to filter by.
* **Primary key** should be equal to attribute name.
* **Index name** should be equal to attribute name postfixed by *"-index"*. (It will be filled by AWS automatically).
For example, for attribute *"city"*: *Primary key* = *"city"* and index name = *"city-index"*.
* **Index name** can be directly specified by `index_name` argument:
```python
    name = CharProperty(required=True,unique=True,min_length=5,max_length=20,index_name='name_index')
```
- **IMPORTANT: In other words, if your indexed attribute is named city, then your index name should be city-index,
if you didn't specify `index_name` argument.**
* **Projected attributes**: *All*.

### Use DynamoDB locally
#### Run DynamoDB
* with persistent storage `docker run -d -p 8000:8000 -v /tmp/data:/data/ dwmkerr/dynamodb -dbPath /data/`

#### Configuration
**Example:** loading.py
```python
from docb.loading import DocbHandler


docb_handler = DocbHandler({
    'dynamodb': {
        'backend': 'docb.backends.dynamodb.db.DynamoDB',
        'connection': {
            'table': 'your-dynamodb-table',
            'endpoint_url': 'http://127.0.0.1:8000'
        }
    }
})
```

#### Testing
##### Run DynamoDB
* in memory (best performance) `docker run -d -p 8000:8000 dwmkerr/dynamodb -inMemory`

##### Create a table for testing.

```python
import boto3


table_wcu = 2000
table_rcu = 2000
index_wcu = 3000
index_rcu = 2000
table_name = 'localtable'

dynamodb = boto3.resource('dynamodb', endpoint_url="http://127.0.0.1:8000")
dynamodb.create_table(TableName=table_name, KeySchema=[{'AttributeName': '_id', 'KeyType': 'HASH'}],
                      ProvisionedThroughput={'ReadCapacityUnits': table_rcu,
                                             'WriteCapacityUnits': table_wcu},
                      AttributeDefinitions=[{'AttributeName': '_id', 'AttributeType': 'S'},
                                            {u'AttributeName': u'city', u'AttributeType': u'S'},
                                            {u'AttributeName': u'email', u'AttributeType': u'S'},
                                            {u'AttributeName': u'name', u'AttributeType': u'S'},
                                            {u'AttributeName': u'slug', u'AttributeType': u'S'}],
                      GlobalSecondaryIndexes=[
                          {'IndexName': 'city-index', 'Projection': {'ProjectionType': 'ALL'},
                           'ProvisionedThroughput': {'WriteCapacityUnits': index_wcu,
                                                     'ReadCapacityUnits': index_rcu},
                           'KeySchema': [{'KeyType': 'HASH', 'AttributeName': 'city'}]},
                          {'IndexName': 'name-index', 'Projection': {'ProjectionType': 'ALL'},
                           'ProvisionedThroughput': {'WriteCapacityUnits': index_wcu,
                                                     'ReadCapacityUnits': index_rcu},
                           'KeySchema': [{'KeyType': 'HASH', 'AttributeName': 'name'}]},
                          {'IndexName': 'slug-index', 'Projection': {'ProjectionType': 'ALL'},
                           'ProvisionedThroughput': {'WriteCapacityUnits': index_wcu,
                                                     'ReadCapacityUnits': index_rcu},
                           'KeySchema': [{'KeyType': 'HASH', 'AttributeName': 'slug'}]},
                          {'IndexName': 'email-index', 'Projection': {'ProjectionType': 'ALL'},
                           'ProvisionedThroughput': {'WriteCapacityUnits': index_wcu,
                                                     'ReadCapacityUnits': index_rcu},
                           'KeySchema': [{'KeyType': 'HASH', 'AttributeName': 'email'}]}])
```
##### Setup environment variables.
```bash
export DYNAMO_TABLE_TEST='localtable'
export DYNAMO_ENDPOINT_URL_TEST='http://127.0.0.1:8000'
```


### Backup and Restore

Easily backup or restore your model locally or from S3. The backup method creates a JSON file backup. 

#### Backup 

##### Local Backup

```python
TestDocument().backup('test-backup.json')
```

##### S3 Backup

```python

TestDocument().backup('s3://your-bucket/kev/test-backup.json')
```

#### Restore

##### Local Restore

```python

TestDocument().restore('test-backup.json')
```

#### S3 Restore

```python

TestDocument().restore('s3://your-bucket/kev/test-backup.json')
```

### Author

**Twitter:**:[@brianjinwright](https://twitter.com/brianjinwright)
**Github:** [bjinwright](https://github.com/bjinwright)


### Contributors

**Github:** [armicron](https://github.com/armicron)
