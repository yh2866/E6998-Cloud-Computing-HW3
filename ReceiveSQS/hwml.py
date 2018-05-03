from __future__ import print_function

#import argparse
import json
#import pprint
#import requests
import sys
import urllib
import datetime
import time
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import csv
import boto3

AWS_ACCESS_KEY = ''
AWS_SECRET_KEY = ''
region = 'us-east-1'
service = 'es'
sqs = boto3.client('sqs')
sqsurl = 'https://sqs.us-east-1.amazonaws.com/188021121519/AI_SQS'

awsauth = AWS4Auth(AWS_ACCESS_KEY, AWS_SECRET_KEY, region, service)
#host = 'search-hw3ml-ze6zt6wltdkr2ojb5umicg4sne.us-east-1.es.amazonaws.com'
host = 'search-hw3-37vmmy4ekmfpsyl56wn6zisstq.us-east-1.es.amazonaws.com'
es = Elasticsearch(
    hosts = [{'host': host, 'port': 443}],
    http_auth = awsauth,
    use_ssl = True,
    verify_certs = True,
    connection_class = RequestsHttpConnection
)


def lambda_handler(content, context):
    messages = sqs.receive_message(QueueUrl=sqsurl, MaxNumberOfMessages=5)
    if 'Messages' in messages:
        print("queuelen", len(messages['Messages']))
        message_queue = messages['Messages']
        for message in message_queue:
            print(message['Body'])
            jsonmsg = json.loads(message['Body'])
            print(jsonmsg)
            print(type(jsonmsg))
            Location = jsonmsg['Location']
            Cuisine = jsonmsg['Cuisine']
            DiningTime = jsonmsg['DiningTime']
            DiningDate = jsonmsg['DiningDate']
            NumberOfPeople = jsonmsg['NumberOfPeople']
            PhoneNumber = jsonmsg['PhoneNumber']
            result = []
            res = es.search(index="predictions", body={"query":  {"match": {"Cuisine": Cuisine}}})
            for hit in res['hits']['hits']:
                #print(hit["_source"])
                item = hit["_source"]
                line = [item['BusinessId'],item['score']]
                result.append(line)
            #print (result)
            result = sorted(result,key=lambda x:x[1])[::-1][:5]
            print (result)
            dbclient = boto3.client('dynamodb')
            resmsg = 'Hello! Here are your {0} suggestions for {1} people.\n'.format(Cuisine,NumberOfPeople)
            initmsg = resmsg
            cnt=0
            for candidate in result:
                businessid = candidate[0]
                print (businessid)
            
                try:
                    response = dbclient.get_item(
                        TableName='yelp-restaurants',
                        Key={
                            'BusinessId': {'S':businessid},
                        }
                    )
                    print ("success")
                except:
                    continue
                else:
                    cnt +=1
                    item = response['Item']
                    print (item)
                    Name = item['Name']['S']
                    Address = item['Address']['S']
                    Rating = item['Rating']['S']
                    resmsg =resmsg + '{0}. {1} located at {2}, rating as {3}\n'.format(cnt,Name,Address,Rating)
            sns_client = boto3.client('sns')
            if initmsg != resmsg:
                sns_client.publish(
                    PhoneNumber = '+1' + PhoneNumber,
                    Message=resmsg
                    )
                print ("final success")
            else:
                sns_client.publish(
                    #PhoneNumber = '+1' + PhoneNumber,
                    PhoneNumber = '+13473344481',
                    Message='Sorry, we fail to get the result. Please try again with the appropriate requirements!'
                    )
                





                # next, we delete the message from the queue so no one else will process it again
            sqs.delete_message(QueueUrl=sqsurl, ReceiptHandle=message['ReceiptHandle'])
    else:
        print('Queue is now empty')
