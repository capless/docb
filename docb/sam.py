import sammy as sm
import docb.document
import docb.loading

# db = sm.DynamoDBTable(
#     name='loadlambddb',
#     TableName='loadlambddb',
#     KeySchema=[{'AttributeName':'_id','KeyType':'HASH'}],
#     GlobalSecondaryIndexes=[{'IndexName':'run_slug-index','KeySchema':[{'AttributeName':'run_slug','KeyType':'HASH'}],'Projection':{'ProjectionType':'ALL'},'ProvisionedThroughput':{'ReadCapacityUnits':5,'WriteCapacityUnits':5}}],
#     AttributeDefinitions=[{'AttributeName':'_id','AttributeType':'S'},{'AttributeName':'run_slug','AttributeType':'S'}],
#     ProvisionedThroughput={'ReadCapacityUnits':5,'WriteCapacityUnits':5}
# )


# class Deployer(object):
#
#     def __init__(self,klass):
#         self.klass
#         self.multi_table = False
#
#         if isinstance(self.klass,docb.loading.DocbHandler):



