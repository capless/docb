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
    'dynamodb':{
        'connection':{
            'table':'your-dynamodb-table'
        },
        'config':{
              'endpoint_url':'http://localhost:8000'
            },
        'documents':['docb.testcase.BaseTestDocumentSlug','docb.testcase.DynamoTestCustomIndex'],
        'table_config':{
            'write_capacity': 2,
            'read_capacity': 3,
            'secondary_write_capacity': 2,
            'secondary_read_capacity': 3
        }
    }
})
```

#### Handler Configuration

##### Connection
This basically specifies the table name and optionally the endpoint url.

##### Config
DocB allows you to use one table for all _Document_ classes, use one table per _Document_ class, or a mixture of the two.

##### Documents

The documents keys is used to specify which Document classes and indexes are used for each table. 
This is only for CloudFormation deployment. Specifying `handler` in the `Meta` class of the `Document` class is still required.    
 
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
    state = CharProperty(required=True,global_index=True,max_length=50)
    no_subscriptions = IntegerProperty(default_value=1,global_index=True,min_value=1,max_value=20)
    gpa = FloatProperty(global_index=True,key_type='RANGE')

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
    is_active = BooleanProperty(default_value=True, global_index=True)
    city = CharProperty(required=False,max_length=50)
    state = CharProperty(required=True,global_index=True,max_length=50)
    no_subscriptions = IntegerProperty(default_value=1,global_index=True,min_value=1,max_value=20)
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
#Faster uses pk or _id to perform a DynamoDB get_item 
>>>TestDocument.get('ec640abfd6')
<TestDocument: Kev:ec640abfd6>

#Use DynamoDB query and throws an error if more than one result is found.
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

##### Global Filter Documents (gfilter)

This is just like the ``filter`` method but it uses a Global Secondary Index as the key instead of the main Global Index.
```python
>>>TestDocument.objects().gfilter({'state':'VA'}, index_name='state-index') #Index Name is not required and this option is only provided for when you won't to query on multiple attributes that are GSIs.

[<TestDocument: George:aff7bcfb56>,<TestDocument: Sally:c38a77cfe4>]
```

##### Filter with Conditions
Docb supports the following DynamoDB conditions. Specify conditions by using double underscores (__). Example for GreaterThan you would use ``the_attribute_name__gt``.

Full List of Conditions:
- Equals ``__eq`` (default filter so it is not necessary to specify)
- NotEquals ``__ne`` 
- LessThan ``__lt``
- LessThanEquals ``__lte``
- GreaterThan ``__gt``
- GreaterThanEqual ``__gte``
- In ``__in``
- Between ``__between``
- BeginsWith ``__begins``
- Contains ``__contains``
- AttributeType ``__attr_type``
- AttributeExists ``__attr_exists``
- AttributeNotExists ``__attr_not_exists``

```python
>>>TestDocument.objects().filter({'no_subscriptions__gt':3})
[<TestDocument: Sally:ec640abfd6>]

```
##### Filter with Limits
Limits the amount of records returned from the query.

```python
>>>TestDocument.objects().filter({'no_subscriptions__gt':3}, limit=5)
```

##### Filter with Sorting
Sort the results of the records returned from the query. 

**_WARNING_:** This feature only sorts the results that are returned. It is not an official DynamoDB feature and 
therefore if you use this with the ``limit`` argument your results may not be true. 

```python
>>>TestDocument.objects().filter({'no_subscriptions__gt':3}, sort_attr='state', sort_reverse=True)
```

##### Chain Filters
The chain filters feature is only available for Redis and S3/Redis backends.

```python
>>>TestDocument.objects().filter({'no_subscriptions':3}).filter({'state':'NC'})
[<TestDocument: Kev:ec640abfd6>]
```
## Table Deployment

DocB features two ways to deploy tables to AWS (only one works with DynamoDB Local though).  

### Via CloudFormation

```python
from docb.loading import DocbHandler

handler = DocbHandler({
    'dynamodb':{
        'connection':{
            'table':'school'
        },
        'documents':['docb.testcase.Student'],
        'table_config':{
            'write_capacity':2,
            'read_capacity':3
        }
    }
})

# Build the SAM template
sam = handler.build_cf_template('resource_name', 'table_name', 'db_label')

# Deploys the SAM template to AWS via CloudFormation
sam.publish('stack_name')

```

### Via Boto3/AWS API

```python
from docb.loading import DocbHandler
from docb import (Document, CharProperty, IntegerProperty,
                 DateTimeProperty,BooleanProperty, FloatProperty,
                DateProperty)

handler = DocbHandler({
    'dynamodb':{
        'connection':{
            'table':'school'
        },
        'config':{
              'endpoint_url':'http://localhost:8000'
            },
        'documents':['docb.testcase.Student'],
        'table_config':{
            'write_capacity':2,
            'read_capacity':3
        }
    }
})


class Student(Document):
    first_name = CharProperty(required=True)
    last_name = CharProperty(required=True)
    slug = CharProperty(required=True,unique=True)
    email = CharProperty(required=True, unique=True)
    gpa = FloatProperty(global_index=True)
    hometown = CharProperty(required=True)
    high_school = CharProperty()
    class Meta:
        use_db = 'dynamodb'
        handler = handler

# Creates the table via AWS API        
Student().create_table()
```

### DynamoDB setup
#### Create a table
* **Table name** should be between 3 and 255 characters long. (A-Z,a-z,0-9,_,-,.)
* **Primary key** (partition key) should be equal to `_doc_type` and range should be ``_id``.

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


handler = DocbHandler({
    'dynamodb':{
        'connection':{
            'table':'school'
        },
        'config':{
              'endpoint_url':'http://localhost:8000'
            },
        'documents':['docb.testcase.Student'],
        'table_config':{
            'write_capacity':2,
            'read_capacity':3
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

**IMPORTANT:** These are **only** appropriate for small datasets. 

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
