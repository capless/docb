# Docb
Opinionated Python ORM for DynamoDB
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
        'backend': 'docb.db.DynamoDB',
        'connection': {
            'table': 'your-dynamodb-table',
        },
        'config':{ # This is optional read below
            'write_capacity':2,
            'read_capacity':2,
            'secondary_write_capacity':2,
            'secondary_read_capacity':2
        }
    }
})
```

#### Handler Configuration

##### Backend
Specify what backend the document should use to interact with the DB.

**Question:** Why have a backend mechanism if this library only supports DynamoDB?

**Answer:** There are two reasons. First, we may choose to support a database like FaunaDB in the future. Second, someone might want to implement something differently for their project.

##### Connection
This basically specifies the table name and optionally the endpoint url.

##### Config
DocB allows you to use one table for all _Document_ classes, use one table per _Document_ class, or a mixture of the two.

###### One Table Per Document Class Model
If you want to specify one table per _Document_ class and there are different capacity requirements for each table you should specify those capacities in the Meta class (see example below).

```python
from docb import (Document,CharProperty,DateTimeProperty,
                 DateProperty,BooleanProperty,IntegerProperty,
                 FloatProperty)
from .loading import docb_handler

class TestDocument(Document):
    name = CharProperty(required=True,unique=True,min_length=3,max_length=20)
    last_updated = DateTimeProperty(auto_now=True)
    date_created = DateProperty(auto_now_add=True)
    is_active = BooleanProperty(default_value=True,index=True,key_type='HASH')
    city = CharProperty(required=False,max_length=50)
    state = CharProperty(required=True,index=True,max_length=50)
    no_subscriptions = IntegerProperty(default_value=1,index=True,min_value=1,max_value=20)
    gpa = FloatProperty(index=True,key_type='RANGE')

    def __unicode__(self):
        return self.name

    class Meta:
        use_db = 'dynamodb'
        handler = docb_handler
        config = { # This is optional read above
            'write_capacity':2,
            'read_capacity':2,
            'secondary_write_capacity':2,
            'secondary_read_capacity':2
        }
```
###### One Table for Multiple Document Classes Model
Specify the capacity in the handler if you want to use one table for multiple classes.

**IMPORTANT:** This will not work yet if you need different 
```python
from docb.loading import DocbHandler


docb_handler = DocbHandler({
    'dynamodb': {
        'backend': 'docb.db.DynamoDB',
        'connection': {
            'table': 'your-dynamodb-table',
        },
        'config':{ # This is optional read below
            'write_capacity':2,
            'read_capacity':2,
            'secondary_write_capacity':2,
            'secondary_read_capacity':2
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
**IMPORTANT:** This is a query (not a scan) of all of the documents with **_doc_type** of the Document you're using. So if you're using one table for multiple document types you will only get back the documents that fit that query.
```python
>>>TestDocument.objects().all()

[<TestDocument: Kev:ec640abfd6>,<TestDocument: George:aff7bcfb56>,<TestDocument: Sally:c38a77cfe4>]

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

### DynamoDB Deployment

```python


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
